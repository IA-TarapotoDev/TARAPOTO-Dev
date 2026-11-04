"""Genera el JSON del tablero de gestión de riesgo a partir de tres fuentes:

  1. DAM de importación (CSV, una fila por serie)
  2. CPE emitidos (TXT separado por "|", una fila por comprobante)
  3. Detalle de CPE emitidos (TXT separado por "|", una fila por ítem)

Uso:
  python3 -I generar_datos.py DAMS.csv CPE_EMITIDOS.txt CPE_DETALLE.txt salida.json \
      [--domicilios domicilios.csv] [--ubigeos ../referencias/ubigeo_zte.csv]

domicilios.csv sale de extraer_domicilios.py (padrón reducido del RUC). Con él, cada cliente
se ubica por el ubigeo de su domicilio fiscal en la ZTE o en la ZTC (ver zona_ubigeo.py).

Los archivos de origen y el JSON de salida contienen información con reserva
tributaria: no se versionan (ver .gitignore). El JSON se publica solo cifrado
(ver cifrar.py).
"""
import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import date

import pandas as pd

ADUANAS = {"118": "Marítima del Callao", "235": "Aérea y Postal del Callao", "271": "Tarapoto",
           "226": "Iquitos", "217": "Pucallpa", "280": "Puerto Maldonado", "262": "Desaguadero"}
DESTINOS = {"271": "Tarapoto", "217": "Pucallpa", "280": "Puerto Maldonado", "226": "Iquitos", "": "Sin aduana de destino"}
DEST_CIRC = {"271": "IA TARAPOTO", "226": "IA IQUITOS", "217": "IA PUCALLPA", "280": "IA PUERTO MALDONADO"}
REGIMENES = {"10": "Importación para el consumo", "40": "Exportación definitiva", "70": "Depósito aduanero"}
CANALES = {"V": "Verde", "D": "Naranja", "F": "Rojo"}
MOTIVOS_NC = {  # Catálogo 09 SUNAT
    "01": "Anulación de la operación", "02": "Anulación por error en el RUC",
    "03": "Corrección por error en la descripción", "04": "Descuento global",
    "05": "Descuento por ítem", "06": "Devolución total", "07": "Devolución por ítem",
    "08": "Bonificación", "09": "Disminución en el valor", "10": "Otros conceptos",
    "11": "Ajustes de operaciones de exportación", "12": "Ajustes afectos al IVAP",
    "13": "Ajustes – montos y/o fechas de pago",
}
LINEAS = {"FR": "Repuestos", "FS": "Servicio técnico", "FP": "Maquinaria", "FV": "Otros ingresos"}
HS_MAQ = {"8429", "8701", "8502", "8408", "8426", "8427", "8430", "8474", "8704", "8705"}
PUBLICO = re.compile(r"MUNICIPALIDAD|GOBIERNO REGIONAL|MINISTERIO|PROGRAMA |PROYECTO ESPECIAL|"
                     r"GERENCIA (SUB)?REGIONAL|GERENCIA TERRITORIAL|UNIVERSIDAD NACIONAL|EJERCITO|"
                     r"MARINA DE GUERRA|FUERZA AEREA|INSTITUTO NACIONAL|SERVICIO NACIONAL|"
                     r"PETROLEOS DEL PERU|SEGURO SOCIAL|ESSALUD|DIRECCION REGIONAL|UNIDAD EJECUTORA")


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.upper()).strip()


def cat_maquina(desc):
    d = norm(desc)
    reglas = [
        ("RETROEXCAVADORA", "Retroexcavadora"), ("EXCAVADORA", "Excavadora"),
        ("MINICARGADOR", "Minicargador"), ("CARGADOR", "Cargador frontal"),
        ("MOTONIVELADORA", "Motoniveladora"), ("RODILLO", "Rodillo compactador"),
        ("TRACTOR AGRIC", "Tractor agrícola"), ("TRACTOR", "Tractor de orugas"),
        ("GRUPO ELECTROGENO", "Grupo electrógeno"), ("MOTOR MARINO", "Motor marino"), ("MOTOR", "Motor diésel"),
        ("MARTILLO", "Martillo hidráulico"), ("RASTRA", "Implemento agrícola"),
        ("ROTOVATOR", "Implemento agrícola"), ("CORTADORA", "Implemento agrícola"),
        ("DISTRIBUIDOR DE CAL", "Implemento agrícola"),
    ]
    for clave, cat in reglas:
        if clave in d:
            return cat
    return "Otros"


def tipo_cliente(tdoc, doc, nombre):
    if tdoc == "0":
        return "No domiciliado"
    if PUBLICO.search(norm(nombre)):
        return "Entidad pública"
    if str(doc).startswith("10"):
        return "Persona natural"
    return "Empresa"


def r2(x):
    return None if pd.isna(x) else round(float(x), 2)


def leer_dams(ruta):
    m = pd.read_csv(ruta, dtype=str)
    for c in ["CNT_COMER", "MTO_FOBDOL", "MTO_FLETEDOL", "MTO_SEGDOL", "MTO_VALORADU"]:
        m[c] = pd.to_numeric(m[c])
    m["f"] = pd.to_datetime(m.FEC_DECLARACION)
    m["dam"] = m.COD_ADUANA + "-" + m.ANN_PRESEN + "-" + m.COD_REGIMEN + "-" + m.NUM_DECLARACION.str.zfill(6)
    m["hs4"] = m.NUM_PARTNANDI.str[:4]
    m["cif_u"] = m.MTO_VALORADU / m.CNT_COMER
    m["fob_u"] = m.MTO_FOBDOL / m.CNT_COMER
    m["conv"] = (m.COD_TIPCONVENIO.fillna("").str.strip() + "-" + m.COD_CONVENIO.fillna("").str.strip()).replace("-", "Sin beneficio")
    m["maq"] = m.hs4.isin(HS_MAQ) | (m.cif_u >= 15000)
    m["COD_REGIMEN"] = m.COD_REGIMEN.str.strip()
    m["dest"] = m.COD_ADUDEST.fillna("").str.strip()
    return m


def datos_maquina(mq):
    """Tipo, marca, modelo e identificadores (PIN/VIN/serie, motor, año, horas) de cada serie de maquinaria."""
    mq = mq.copy()
    mq["cat"] = mq.DES_COMER.map(cat_maquina)
    partes = mq.DES_COMER.str.split(",")
    mq["marca"] = partes.str[1].str.strip()
    mq["modelo"] = partes.str[2].str.strip()
    txt = (mq.DES_FORMAPRESEN.fillna("") + " " + mq.DES_MATECOMP.fillna("") + " " + mq.DES_USOAPLIC.fillna("") + " " + mq.DES_OTROSCARAC.fillna(""))
    mq["pin"] = txt.str.extract(r"PIN(?: NUMBER)?[#: ]*\*?([A-Z0-9]{17})\*?", expand=False)
    vin = txt.str.extract(r"VIN[#: ]*([A-Z0-9]{17})", expand=False)
    sn = txt.str.extract(r"(?:SERIAL(?: NUMBER)?|S/N|SERIE|UNIQUE ID)[#: ]*([A-Z0-9]{8,20})", expand=False)
    mq["id"] = mq.pin.fillna(vin).fillna(sn).fillna("")
    mq["anio"] = txt.str.extract(r"A[ÑN]O DE (?:FABRIC?ACION|MANUFACTURA)[: ]*(\d{4})", expand=False).fillna("")
    mq["motor"] = txt.str.extract(r"(?:ENG(?:INE)?(?: S/N| NUMBER| #)?|NUMERO DE MOTOR)[: ]*([A-Z0-9]{8,12})", expand=False).fillna("")
    mq["horas"] = txt.str.extract(r"HOURS[: ]*([\d.,]+)\s*HRS", expand=False).fillna("")
    mq["usada"] = txt.str.contains(r"\bUSED\b|\bUSAD[OA]\b", regex=True) | (
        pd.to_numeric(mq.anio, errors="coerce") <= mq.f.dt.year - 2)
    return mq


def leer_cpe(ruta):
    e = pd.read_csv(ruta, sep="|", encoding="latin-1", dtype=str, index_col=False).iloc[:, :14]
    e.columns = ["ruc", "tipo", "serie", "nro", "tipo_ref", "tdoc", "doc", "nombre", "moneda",
                 "vv", "igv", "total", "fecha", "estado"]
    for c in ["vv", "igv", "total"]:
        e[c] = pd.to_numeric(e[c])
    e["f"] = pd.to_datetime(e.fecha, format="%m/%d/%Y")
    e["linea"] = e.serie.str[:2].map(LINEAS).fillna("Otra")
    e["cpe"] = e.tipo + "-" + e.serie + "-" + e.nro
    e["nombre"] = e.nombre.str.replace(r"\s+", " ", regex=True).str.strip()
    e["tcli"] = [tipo_cliente(t, d, n) for t, d, n in zip(e.tdoc, e.doc, e.nombre)]
    return e


def leer_detalle(ruta):
    dl = pd.read_csv(ruta, sep="|", encoding="latin-1", dtype=str, index_col=False)
    dl["cpe"] = dl.cod_cpe + "-" + dl.num_serie_cpe + "-" + dl.num_cpe
    dl["q"] = pd.to_numeric(dl.num_cant_item)
    return dl


def ubicador(r_ubi):
    """Devuelve una función (departamento, provincia, distrito) -> fila del ubigeo (o None)."""
    u = pd.read_csv(r_ubi, dtype=str).fillna("")
    u = u[u.ubigeo.str.fullmatch(r"\d{6}")]
    k = lambda x: " ".join(re.sub(r"[^A-Z ]", " ", norm(x)).split())
    por_3 = {(k(r.departamento), k(r.provincia), k(r.distrito)): r for r in u.itertuples()}
    por_2 = {}
    for r in u.itertuples():
        por_2.setdefault((k(r.departamento), k(r.distrito)), []).append(r)
    def buscar(dep, prov, dist):
        r = por_3.get((k(dep), k(prov), k(dist)))
        if r is None:
            c = por_2.get((k(dep), k(dist)), [])
            r = c[0] if len(c) == 1 else None
        return r
    return buscar


def leer_facturas_xml(rutas):
    """Lee comprobantes electrónicos en XML (UBL 2.1 de SUNAT): archivos, carpetas o ZIP.
    Devuelve una fila por ítem con la serie de la máquina y del motor que el emisor escribe en la descripción."""
    import io
    import zipfile
    import xml.etree.ElementTree as ET
    ns = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
          "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"}
    fuentes = []
    for r in rutas or []:
        if os.path.isdir(r):
            fuentes += [os.path.join(r, f) for f in sorted(os.listdir(r)) if f.lower().endswith(".xml")]
        elif zipfile.is_zipfile(r):
            z = zipfile.ZipFile(r)
            fuentes += [io.BytesIO(z.read(n)) for n in z.namelist() if n.lower().endswith(".xml")]
        else:
            fuentes.append(r)
    filas = []
    for f in fuentes:
        raiz = ET.parse(f).getroot()
        tipo_doc = {"Invoice": "01", "CreditNote": "07", "DebitNote": "08"}.get(raiz.tag.split("}")[-1], "01")
        t = lambda p, n=raiz: (n.findtext(p, default="", namespaces=ns) or "").strip()
        cli = raiz.find("cac:AccountingCustomerParty/cac:Party", ns)
        dir_cli = cli.find("cac:PostalAddress", ns) if cli is not None else None
        if dir_cli is None and cli is not None:
            dir_cli = cli.find("cac:PartyLegalEntity/cac:RegistrationAddress", ns)
        td = lambda p: t(p, dir_cli) if dir_cli is not None else ""
        base = {"cpe": f"{tipo_doc}-{t('cbc:ID')}", "f": t("cbc:IssueDate"), "mon": t("cbc:DocumentCurrencyCode"),
                "oc": t("cac:OrderReference/cbc:ID"), "est_cod": t("cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cac:RegistrationAddress/cbc:AddressTypeCode"),
                "ruc_cli": t("cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID"),
                "dir": td("cac:AddressLine/cbc:Line"), "dist": td("cbc:District"), "prov": td("cbc:CityName"), "dep": td("cbc:CountrySubentity"),
                "guias": ", ".join(x.text or "" for x in raiz.findall("cac:DespatchDocumentReference/cbc:ID", ns)),
                "igv_doc": t("cac:TaxTotal/cbc:TaxAmount"), "total": t("cac:LegalMonetaryTotal/cbc:PayableAmount")}
        for ln in raiz.findall("cac:InvoiceLine", ns) + raiz.findall("cac:CreditNoteLine", ns):
            desc = [x.text or "" for x in ln.findall("cac:Item/cbc:Description", ns)]
            texto = " / ".join(d.strip() for d in desc if d.strip())
            busca = lambda pat: (re.search(pat, norm(texto)) or [None, ""])[1]
            filas.append({**base, "desc": texto,
                          "serie": busca(r"SERIE (?:DE )?MAQUINA[: ]*([A-Z0-9-]{5,20})") or busca(r"\bPIN[: ]*([A-Z0-9]{17})") or busca(r"\bVIN[: ]*([A-Z0-9]{17})"),
                          "motor": busca(r"SERIE (?:DE )?MOTOR[: ]*([A-Z0-9-]{5,20})"), "modelo": busca(r"MODELO[: ]*([A-Z0-9.\- ]+?)(?: /|$)"),
                          "anio": busca(r"ANO DE FABRICACION[: ]*(\d{4})"), "horas": busca(r"HORAS DE USO[: ]*([\d.,]+)"),
                          "exencion": t("cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:TaxExemptionReasonCode", ln),
                          "valor": t("cbc:LineExtensionAmount", ln)})
    return pd.DataFrame(filas)


def leer_consulta_ruc(rutas):
    """Resultados de la consulta múltiple de RUC de SUNAT (ZIP o TXT separados por «|»)."""
    import io
    import zipfile
    partes = []
    for r in rutas or []:
        fuentes = []
        if zipfile.is_zipfile(r):
            z = zipfile.ZipFile(r)
            fuentes = [io.BytesIO(z.read(m)) for m in z.namelist() if m.lower().endswith(".txt")]
        else:
            fuentes = [r]
        for f in fuentes:
            t = pd.read_csv(f, sep="|", encoding="latin-1", dtype=str, index_col=False).fillna("")
            t.columns = [norm(c) for c in t.columns]
            t = t[[c for c in t.columns if c and not c.startswith("UNNAMED")]]
            t = t.apply(lambda col: col.str.strip().replace({"-": ""}))
            partes.append(t)
    if not partes:
        return pd.DataFrame(columns=["ruc"])
    t = pd.concat(partes, ignore_index=True)
    col = lambda *ns: next((c for c in t.columns if any(c.startswith(n) for n in ns)), None)
    out = pd.DataFrame({"ruc": t[col("NUMERORUC", "RUC")]})
    for destino, nombres in {"departamento_c": ("DEPARTAMENTO",), "provincia_c": ("PROVINCIA",), "distrito_c": ("DISTRITO",),
                             "direccion_c": ("DIRECCION",), "actividad": ("PRINCIPAL",), "actividad2": ("SECUNDARIO 1",),
                             "finsc": ("FECHA DE INSCRIPCION",), "tipo_contrib": ("TIPO DE CONTRIBUYENTE",),
                             "estado_c": ("ESTADO DEL CONTRIBUYENTE",), "condicion_c": ("CONDICION DEL CONTRIBUYENTE",)}.items():
        c = col(*nombres)
        out[destino] = t[c] if c else ""
    out["finsc"] = pd.to_datetime(out.finsc, format="%d/%m/%Y", errors="coerce").dt.strftime("%Y-%m-%d").fillna("")
    return out.drop_duplicates("ruc", keep="last")


def cargar_domicilios(r_dom, r_ubi, consultas=None):
    """Admite ubigeo o, si falta, departamento/provincia/distrito por nombre; y la actividad económica.
    Completa con la consulta múltiple de RUC: actividad, fecha de inscripción y, si el padrón no lo trae, el domicilio."""
    d = pd.read_csv(r_dom, dtype=str).fillna("")
    d.columns = [norm(c).lower().replace(" ", "_") for c in d.columns]
    c = leer_consulta_ruc(consultas)
    if len(c):
        d = d.merge(c, on="ruc", how="outer").fillna("")
        for a, b in (("departamento", "departamento_c"), ("provincia", "provincia_c"), ("distrito", "distrito_c"), ("direccion", "direccion_c"),
                     ("estado", "estado_c"), ("condicion", "condicion_c")):
            if a not in d:
                d[a] = ""
            sin = (d.get("ubigeo", "") == "") if a in ("departamento", "provincia", "distrito") else (d[a] == "")
            d.loc[sin, a] = d.loc[sin, b]
        d = d.drop(columns=[x for x in d.columns if x.endswith("_c")])
    u = pd.read_csv(r_ubi, dtype=str).fillna("")
    u = u[u.ubigeo.str.fullmatch(r"\d{6}")]
    for c in ["ubigeo", "departamento", "provincia", "distrito", "estado", "condicion", "direccion", "actividad", "actividad2", "finsc", "tipo_contrib"]:
        if c not in d:
            d[c] = ""
    d["ubigeo"] = d.ubigeo.str.strip().str.zfill(6).where(d.ubigeo.str.strip() != "", "")
    k = lambda x: re.sub(r"[^A-Z ]", " ", norm(x)).split()
    clave = lambda *xs: " | ".join(" ".join(k(x)) for x in xs)
    por_3 = {clave(a, b, c): g for g, a, b, c in zip(u.ubigeo, u.departamento, u.provincia, u.distrito)}
    por_2 = {}
    for g, a, c in zip(u.ubigeo, u.departamento, u.distrito):
        por_2.setdefault(clave(a, c), []).append(g)
    def ubigeo_por_nombre(r):
        if r.ubigeo or not r.distrito:
            return r.ubigeo
        g = por_3.get(clave(r.departamento, r.provincia, r.distrito))
        if g:
            return g
        c = por_2.get(clave(r.departamento, r.distrito), [])
        return c[0] if len(c) == 1 else ""
    d["ubigeo"] = [ubigeo_por_nombre(r) for r in d.itertuples()]
    d = d.drop(columns=["departamento", "provincia", "distrito"])
    d = d.merge(u, on="ubigeo", how="left").fillna("").rename(columns={"estado": "eruc"})
    d.loc[d.ubigeo == "", ["departamento", "provincia", "distrito", "zona"]] = ""
    d["zona"] = d.zona.where(d.zona != "", "Sin dato")
    return d.drop_duplicates("ruc").set_index("ruc")


def mes(s):
    return s.dt.strftime("%Y-%m")


def main(r_dams, r_cpe, r_det, salida, r_dom=None, r_ubi=None, portal=None, consultas=None, r_traz=None, r_xml=None):
    mt = leer_dams(r_dams)
    m = mt[mt.COD_REGIMEN == "10"].copy()        # importación para el consumo: base de todos los totales
    dep70 = mt[mt.COD_REGIMEN == "70"].copy()    # depósito aduanero: fuera de totales, solo para la cadena
    exp40 = mt[mt.COD_REGIMEN == "40"].copy()    # exportación definitiva
    e = leer_cpe(r_cpe)
    dl = leer_detalle(r_det)

    meses = pd.period_range(min(m.f.min(), e.f.min()), max(m.f.max(), e.f.max()), freq="M").strftime("%Y-%m").tolist()

    # ---------------- Importaciones ----------------
    dec = m.groupby("dam").agg(
        fecha=("f", "first"), aduana=("COD_ADUANA", "first"), destino=("dest", "first"),
        canal=("CANAL", "first"), series=("NUM_SECSERIE", "size"), fob=("MTO_FOBDOL", "sum"),
        flete=("MTO_FLETEDOL", "sum"), seguro=("MTO_SEGDOL", "sum"), cif=("MTO_VALORADU", "sum"),
        maq=("maq", "sum"), conv=("conv", lambda s: ", ".join(sorted(set(s)))),
    ).reset_index().sort_values("fecha")
    dec["flete_pct"] = dec.flete / dec.fob * 100

    imp_mes = []
    for mm in meses:
        x = m[mes(m.f) == mm]
        imp_mes.append({"m": mm, "maq": r2(x[x.maq].MTO_VALORADU.sum()), "otros": r2(x[~x.maq].MTO_VALORADU.sum()),
                        "dams": int(x.dam.nunique()), "uds_maq": int(x[x.maq].CNT_COMER.sum())})

    canal = dec.groupby("canal").agg(n=("dam", "size"), cif=("cif", "sum")).reindex(["V", "D", "F"]).fillna(0)
    conv = m.groupby("conv").agg(series=("dam", "size"), cif=("MTO_VALORADU", "sum")).sort_values("cif", ascending=False)
    aduana = dec.groupby("aduana").agg(n=("dam", "size"), cif=("cif", "sum"), flete_med=("flete_pct", "median"))

    part = m.groupby("NUM_PARTNANDI").agg(series=("dam", "size"), uds=("CNT_COMER", "sum"), cif=("MTO_VALORADU", "sum"),
                                          ej=("DES_COMER", lambda s: s.value_counts().index[0]),
                                          dams=("dam", "nunique")).sort_values("cif", ascending=False)
    part["pct"] = part.cif / part.cif.sum() * 100

    def vista(x):
        dx = dec[dec.dam.isin(set(x.dam))]
        pm = []
        for mm in meses:
            y = x[mes(x.f) == mm]
            pm.append({"m": mm, "maq": r2(y[y.maq].MTO_VALORADU.sum()), "otros": r2(y[~y.maq].MTO_VALORADU.sum()),
                       "dams": int(y.dam.nunique()), "uds_maq": int(y[y.maq].CNT_COMER.sum())})
        cn = dx.groupby("canal").agg(n=("dam", "size"), cif=("cif", "sum")).reindex(["V", "D", "F"]).fillna(0)
        cv = x.groupby("conv").agg(series=("dam", "size"), cif=("MTO_VALORADU", "sum")).sort_values("cif", ascending=False)
        ad = dx.groupby("aduana").agg(n=("dam", "size"), cif=("cif", "sum"), flete_med=("flete_pct", "median"))
        pt = x.groupby("NUM_PARTNANDI").agg(series=("dam", "size"), uds=("CNT_COMER", "sum"), cif=("MTO_VALORADU", "sum"),
                                            ej=("DES_COMER", lambda s: s.value_counts().index[0]), dams=("dam", "nunique")).sort_values("cif", ascending=False)
        pt["pct"] = pt.cif / max(pt.cif.sum(), 1e-9) * 100
        return {
            "mensual": pm,
            "canal": [{"c": k, "n": int(v.n), "cif": r2(v.cif)} for k, v in cn.iterrows()],
            "convenio": [{"k": k, "series": int(v.series), "cif": r2(v.cif)} for k, v in cv.iterrows()],
            "aduana": [{"cod": k, "n": int(v.n), "cif": r2(v.cif), "flete_med": r2(v.flete_med)} for k, v in ad.iterrows()],
            "partidas": [{"hs": k, "ej": v.ej, "series": int(v.series), "dams": int(v.dams), "uds": r2(v.uds), "cif": r2(v.cif), "pct": r2(v.pct)}
                         for k, v in pt.head(40).iterrows()],
            "kpi": {"cif": r2(x.MTO_VALORADU.sum()), "n_dam": int(x.dam.nunique()), "n_series": int(len(x)),
                    "cif_maq": r2(x[x.maq].MTO_VALORADU.sum()), "uds_maq": int(x[x.maq].CNT_COMER.sum()),
                    "cif_lib": r2(x[x.COD_TIPCONVENIO == "C"].MTO_VALORADU.sum()), "dam_verde": int((dx.canal == "V").sum())},
        }
    orden_dest = [k for k in ["271", "217", "280", "226", ""] if (m.dest == k).any()]
    vistas = {"todas": vista(m)} | {(k or "sin"): vista(m[m.dest == k]) for k in orden_dest}
    destinos = [{"k": k or "sin", "cod": k, "t": DESTINOS.get(k, k), **vistas[k or "sin"]["kpi"]} for k in orden_dest]
    otros_reg = mt[mt.COD_REGIMEN != "10"].groupby("COD_REGIMEN").agg(dams=("dam", "nunique"), series=("dam", "size"), cif=("MTO_VALORADU", "sum"))

    # Descripción comercial sin número de parte / modelo (S/M)
    m["sm"] = m.DES_COMER.str.contains(r",\s*S/M\s*$", regex=True)
    sm = m[m.sm & ~m.maq]
    sm_marca = sm.assign(marca=sm.DES_COMER.str.split(",").str[1].str.strip()).groupby("marca").agg(
        series=("dam", "size"), cif=("MTO_VALORADU", "sum"), dams=("dam", "nunique")).sort_values("cif", ascending=False)

    # Valor unitario: dispersión del FOB unitario de un mismo número de parte
    p = m[~m.maq & ~m.sm].copy()
    g = p.groupby("DES_COMER")
    disp = g.agg(n=("fob_u", "size"), med=("fob_u", "median"), mn=("fob_u", "min"), mx=("fob_u", "max"),
                 dams=("dam", "nunique"), cif=("MTO_VALORADU", "sum"))
    disp = disp[(disp.n >= 3) & (disp.dams >= 2)]
    disp["ratio"] = disp.mx / disp.mn
    disp = disp[disp.ratio >= 1.5].sort_values("ratio", ascending=False)
    disp_series = []
    for item, row in disp.iterrows():
        x = p[p.DES_COMER == item]
        for _, s in x.iterrows():
            dev = s.fob_u / row.med - 1
            if abs(dev) >= 0.3:
                disp_series.append({"item": item, "dam": s.dam, "serie": int(s.NUM_SECSERIE), "fecha": s.f.strftime("%Y-%m-%d"),
                                    "hs": s.NUM_PARTNANDI, "cant": r2(s.CNT_COMER), "fob_u": r2(s.fob_u), "med": r2(row.med),
                                    "dev": round(dev * 100, 1), "canal": s.CANAL, "dest": s.dest})

    # Clasificación: un mismo número de parte en más de una subpartida
    clas = p.groupby("DES_COMER").agg(hs=("NUM_PARTNANDI", lambda s: sorted(set(s))), n=("dam", "size"),
                                      dams=("dam", "nunique"), cif=("MTO_VALORADU", "sum"))
    clas = clas[clas.hs.str.len() > 1].sort_values("n", ascending=False)

    # ---------------- Maquinaria importada ----------------
    mq = datos_maquina(m[m.maq])
    dq = datos_maquina(dep70[dep70.maq]) if len(dep70) else mq.iloc[0:0]
    clave_id = lambda x: x[-8:] if x else ""
    mq["k"] = mq.id.map(clave_id)
    dq["k"] = dq.id.map(clave_id)
    dpk = dq[dq.k != ""].sort_values("f").drop_duplicates("k").set_index("k")
    mq["dep_dam"] = mq.k.map(dpk.dam).fillna("")
    mq["dep_f"] = mq.k.map(dpk.f.dt.strftime("%Y-%m-%d")).fillna("")
    nac = mq[mq.k != ""].sort_values("f").drop_duplicates("k").set_index("k")
    corte = mt.f.max()
    deposito = []
    for _, s in dq.sort_values("f").drop_duplicates(["dam", "NUM_SECSERIE"]).iterrows():
        n = nac.loc[s.k] if s.k and s.k in nac.index else None
        deposito.append({"dam": s.dam, "serie": int(s.NUM_SECSERIE), "f": s.f.strftime("%Y-%m-%d"), "canal": s.CANAL, "cat": s["cat"],
                         "marca": s.marca, "modelo": s.modelo, "id": s.id, "cif": r2(s.MTO_VALORADU),
                         "nac_dam": n.dam if n is not None else "", "nac_f": n.f.strftime("%Y-%m-%d") if n is not None else "",
                         "nac_dest": n.dest if n is not None else "", "nac_conv": n.conv if n is not None else "",
                         "dias": int(((n.f if n is not None else corte) - s.f).days)})
    # Exportaciones (régimen 40): la descripción trae PIN, serie y motor
    exportaciones = []
    if len(exp40):
        x40 = exp40.drop_duplicates(["dam", "DES_COMER"]).copy()
        x40["pin"] = x40.DES_COMER.str.extract(r"PIN[: ]*([A-Z0-9]{17})", expand=False).fillna("")
        x40["k"] = x40.pin.map(clave_id)
        x40["motor"] = x40.DES_COMER.str.extract(r"MOTOR[: ]*([A-Z0-9]{8,12})", expand=False).fillna("")
        x40["modelo"] = x40.DES_COMER.str.extract(r"MOD[.:]*\s*([A-Z0-9.]+?)(?:PIN|\s|,|$)", expand=False).fillna("")
        for _, s in x40.sort_values("f").iterrows():
            o = nac.loc[s.k] if s.k and s.k in nac.index else None
            exportaciones.append({"dam": s.dam, "f": s.f.strftime("%Y-%m-%d"), "ad": s.COD_ADUANA, "desc": s.DES_COMER[:60].strip(),
                                  "modelo": s.modelo, "pin": s.pin, "motor": s.motor, "fob": r2(s.MTO_FOBDOL),
                                  "obs": s.DES_OTROSCARAC.strip() if isinstance(s.DES_OTROSCARAC, str) else "",
                                  "imp_dam": o.dam if o is not None else "", "imp_f": o.f.strftime("%Y-%m-%d") if o is not None else "",
                                  "imp_dest": o.dest if o is not None else "", "imp_conv": o.conv if o is not None else "",
                                  "venta": ""})

    # ---------------- Ventas ----------------
    vig = e[e.estado == "0"]
    fac = vig[vig.tipo == "01"]
    nc = vig[vig.tipo == "07"]
    ven_mes = []
    for mm in meses:
        x = fac[mes(fac.f) == mm]
        y = nc[mes(nc.f) == mm]
        ven_mes.append({"m": mm, "usd": r2(x[x.moneda == "USD"].vv.sum()), "pen": r2(x[x.moneda == "PEN"].vv.sum()),
                        "nc_usd": r2(y[y.moneda == "USD"].vv.sum()), "nc_pen": r2(y[y.moneda == "PEN"].vv.sum()),
                        "n": int(len(x))})
    lineas = []
    for l in ["Repuestos", "Servicio técnico", "Maquinaria", "Otros ingresos"]:
        x = fac[fac.linea == l]
        y = nc[nc.linea == l]
        lineas.append({"l": l, "n": int(len(x)), "usd": r2(x[x.moneda == "USD"].vv.sum()), "pen": r2(x[x.moneda == "PEN"].vv.sum()),
                       "nc_n": int(len(y)), "nc_usd": r2(y[y.moneda == "USD"].vv.sum()), "nc_pen": r2(y[y.moneda == "PEN"].vv.sum()),
                       "igv_n": int((x.igv > 0).sum())})
    ncm = nc.groupby("tipo_ref").apply(lambda x: pd.Series({
        "n": len(x), "usd": x[x.moneda == "USD"].vv.sum(), "pen": x[x.moneda == "PEN"].vv.sum(),
        "maq": int((x.linea == "Maquinaria").sum())}), include_groups=False).sort_values("n", ascending=False)
    anul = e[e.estado == "2"]

    # Clientes
    cl = vig.groupby("doc").apply(lambda x: pd.Series({
        "nombre": x.nombre.value_counts().index[0], "tipo": x.tcli.iloc[0],
        "n": int((x.tipo == "01").sum()),
        "usd": x[(x.tipo == "01") & (x.moneda == "USD")].vv.sum(), "pen": x[(x.tipo == "01") & (x.moneda == "PEN")].vv.sum(),
        "nc_n": int((x.tipo == "07").sum()),
        "nc_usd": x[(x.tipo == "07") & (x.moneda == "USD")].vv.sum(), "nc_pen": x[(x.tipo == "07") & (x.moneda == "PEN")].vv.sum(),
        "maq": int(((x.tipo == "01") & (x.linea == "Maquinaria")).sum()),
        "igv_n": int(((x.tipo == "01") & (x.igv > 0)).sum()),
        "ult": x.f.max().strftime("%Y-%m-%d"),
    }), include_groups=False).reset_index().sort_values("usd", ascending=False)
    dom = cargar_domicilios(r_dom, r_ubi, consultas) if r_dom else None
    info = dom.to_dict("index") if dom is not None else {}
    VACIO = {"zona": "", "departamento": "", "provincia": "", "distrito": "", "eruc": "", "condicion": "", "direccion": "", "actividad": "", "finsc": "", "circunscripcion": ""}

    def domicilio(doc, tcli):
        if tcli == "No domiciliado":
            return {**VACIO, "zona": "Extranjero"}
        if dom is None:
            return VACIO
        r = info.get(doc)
        return {k: (r.get(k, "") if r else "") for k in VACIO} | {"zona": r["zona"] if r else "Sin dato"}

    def lugar(r):
        return ", ".join(x for x in (r["distrito"], r["provincia"], r["departamento"]) if x)

    dcl = pd.DataFrame([domicilio(d, t) for d, t in zip(cl.doc, cl.tipo)], index=cl.index)
    cl = pd.concat([cl, dcl], axis=1)
    tot_usd = cl.usd.sum()
    top10 = cl.head(10).usd.sum() / tot_usd * 100
    hhi = float(((cl.usd / tot_usd * 100) ** 2).sum())

    # ---------------- Maquinaria vendida ----------------
    det_fp = dl[dl.num_serie_cpe.str.startswith("FP")].groupby("cpe").des_detalle_item.apply(lambda s: " + ".join(s)).rename("desc")
    vm = e[e.linea == "Maquinaria"].merge(det_fp, left_on="cpe", right_index=True, how="left")
    vm["desc"] = vm.desc.fillna("(sin detalle)")
    vm["cat"] = vm.desc.map(cat_maquina)
    vm["usado"] = vm.desc.map(norm).str.contains(r"\bUSAD[OA]S?\b")
    vm = pd.concat([vm, pd.DataFrame([domicilio(d, t) for d, t in zip(vm.doc, vm.tcli)], index=vm.index)], axis=1)
    vm["lugar"] = [lugar(r) for _, r in vm.iterrows()]
    # Establecimiento emisor inferido por el número de la serie (FP03 → 03) según el domicilio de sus clientes
    u_ref = pd.read_csv(r_ubi, dtype=str).fillna("")
    circ_prov = (u_ref.groupby(["departamento", "provincia"]).circunscripcion.agg(lambda x: x.value_counts().index[0]).to_dict()
                 if "circunscripcion" in u_ref else {})
    establecimientos = {}
    if dom is not None:
        ex = e[["serie", "doc"]].assign(dig=e.serie.str[2:]).merge(dom[["departamento", "provincia"]], left_on="doc", right_index=True, how="inner")
        ex = ex[ex.departamento != ""]
        for dig, g in ex.groupby("dig"):
            top = g.groupby(["departamento", "provincia"]).size().sort_values(ascending=False)
            (dpt, prv), n = top.index[0], int(top.iloc[0])
            circ = circ_prov.get((dpt, prv), "")
            establecimientos[dig] = {"dig": dig, "dep": dpt, "prov": prv, "pct": round(n / len(g) * 100, 1), "n": int(len(g)),
                                     "circ": circ, "dest": next((k for k, v in DEST_CIRC.items() if v == circ), "")}
    vm["est"] = vm.serie.str[2:].map(lambda d: establecimientos.get(d, {}).get("prov", ""))
    vm["est_circ"] = vm.serie.str[2:].map(lambda d: establecimientos.get(d, {}).get("circ", ""))
    fvm = vm[(vm.tipo == "01") & (vm.estado == "0")]
    por_dep = []
    if dom is not None:
        x = fvm.assign(dep=fvm.departamento.where(fvm.departamento != "", fvm.zona.replace({"Sin dato": "Sin dato en el padrón"})))
        for dep, g in x.groupby("dep"):
            por_dep.append({"dep": dep, "zte": int((g.zona == "ZTE").sum()), "ztc": int((g.zona == "ZTC").sum()),
                            "otro": int((~g.zona.isin(["ZTE", "ZTC"])).sum()), "n": int(len(g)),
                            "usd": r2(g[g.moneda == "USD"].vv.sum()), "pen": r2(g[g.moneda == "PEN"].vv.sum()),
                            "igv": int((g.igv > 0).sum())})
        por_dep.sort(key=lambda r: -r["n"])

    cats = ["Retroexcavadora", "Excavadora", "Minicargador", "Cargador frontal", "Motoniveladora", "Rodillo compactador",
            "Tractor agrícola", "Tractor de orugas", "Grupo electrógeno", "Motor diésel", "Motor marino", "Martillo hidráulico",
            "Implemento agrícola", "Otros"]
    resumen_maq = []
    for c in cats:
        i = mq[mq.cat == c]
        fv = vm[(vm.cat == c) & (vm.tipo == "01") & (vm.estado == "0")]
        nv = vm[(vm.cat == c) & (vm.tipo == "07") & (vm.estado == "0") & vm.tipo_ref.isin(["01", "06"])]
        fu = fv[(fv.moneda == "USD") & ~fv.usado]
        if len(i) == 0 and len(fv) == 0:
            continue
        i_nueva = i[~i.usada]
        cif_med = i_nueva.cif_u.median() if len(i_nueva) else None
        venta_med = fu.vv.median() if len(fu) else None
        resumen_maq.append({"cat": c, "imp": int(i.CNT_COMER.sum()), "imp_cif": r2(i.MTO_VALORADU.sum()), "cif_med": r2(cif_med),
                            "vend": int(len(fv)), "anul": int(len(nv)), "neto": int(len(fv) - len(nv)),
                            "venta_med": r2(venta_med), "n_usd": int(len(fu)),
                            "ratio": r2(venta_med / cif_med) if cif_med and venta_med and len(i_nueva) >= 3 and len(fu) >= 3 and c != "Otros" else None,
                            "imp_usada": int(i.usada.sum()),
                            "igv": int((fv.igv > 0).sum()), "pub": int((fv.tcli == "Entidad pública").sum())})

    maq_mes = []
    for mm in meses:
        maq_mes.append({"m": mm, "imp": int(mq[mes(mq.f) == mm].CNT_COMER.sum()),
                        "vend": int(len(vm[(mes(vm.f) == mm) & (vm.tipo == "01") & (vm.estado == "0")]))})

    # Precio de venta vs CIF (USD, unidades nuevas)
    puntos = []
    for _, s in vm[(vm.tipo == "01") & (vm.estado == "0") & (vm.moneda == "USD") & ~vm.usado].iterrows():
        puntos.append({"cat": s["cat"], "vv": r2(s.vv), "cpe": s.cpe, "cli": s.nombre, "f": s.f.strftime("%Y-%m-%d")})

    # Re-facturación: un mismo cliente con NC de anulación/devolución en maquinaria
    nc_maq = vm[(vm.tipo == "07") & (vm.estado == "0") & vm.tipo_ref.isin(["01", "06"])]

    # ---------------- Alertas ----------------
    alertas = []

    def alerta(nivel, tipo, ref, fecha, contraparte, ruc, detalle, monto=None, moneda=""):
        alertas.append({"nivel": nivel, "tipo": tipo, "ref": ref, "fecha": fecha, "cp": contraparte, "ruc": ruc,
                        "det": detalle, "monto": r2(monto) if monto is not None else None, "mon": moneda})

    for _, s in vm[(vm.tipo == "01") & (vm.estado == "0") & (vm.igv > 0)].iterrows():
        alerta("Alta", "Maquinaria vendida con IGV", s.cpe, s.f.strftime("%Y-%m-%d"), s.nombre, s.doc,
               f"{s.desc} · IGV {s.igv:,.2f} · cliente: {s.tcli}" +
               (f" · domicilio fiscal en {s.zona}" + (f" ({s.lugar})" if s.lugar else "") if dom is not None else ""), s.vv, s.moneda)
    if dom is not None:
        for _, s in fvm[fvm.zona == "ZTC"].iterrows():
            alerta("Alta", "Maquinaria vendida a cliente domiciliado fuera de la ZTE", s.cpe, s.f.strftime("%Y-%m-%d"), s.nombre, s.doc,
                   f"{s.desc} · domicilio fiscal: {s.lugar} · {'con' if s.igv > 0 else 'sin'} IGV · {s.direccion}", s.vv, s.moneda)
        for _, s in cl[(cl.maq > 0) & (((cl.eruc != "") & (cl.eruc != "ACTIVO")) | ((cl.condicion != "") & (cl.condicion != "HABIDO")))].iterrows():
            alerta("Media", "Comprador de maquinaria no habido o con RUC no activo", s.doc, s.ult, s.nombre, s.doc,
                   f"RUC {s.eruc or 's/d'} · domicilio {s.condicion or 's/d'} · {int(s.maq)} máquinas · {lugar(s) or s.zona}", s.usd, "USD")
    usadas_exp = set()
    for _, s in vm[(vm.tipo == "01") & (vm.estado == "0") & (vm.tdoc == "0")].sort_values("f").iterrows():
        cand = [x for x in exportaciones if x["dam"] not in usadas_exp and 0 <= (pd.Timestamp(x["f"]) - s.f).days <= 90]
        if cand:
            x = cand[0]; usadas_exp.add(x["dam"]); x["venta"] = s.cpe
            alerta("Baja", "Maquinaria vendida a no domiciliado", s.cpe, s.f.strftime("%Y-%m-%d"), s.nombre, s.doc,
                   f"{s.desc} · DAM de exportación probable {x['dam']} del {pd.Timestamp(x['f']):%d/%m/%Y} por {ADUANAS.get(x['ad'], x['ad'])} "
                   f"(FOB USD {x['fob']:,.2f}, modelo {x['modelo']}, PIN {x['pin']}) · confirmar por número de serie", s.vv, s.moneda)
        else:
            alerta("Alta", "Maquinaria vendida a no domiciliado", s.cpe, s.f.strftime("%Y-%m-%d"), s.nombre, s.doc,
                   f"{s.desc} · sin DAM de exportación en el periodo · verificar exportación o reexportación", s.vv, s.moneda)
    if dom is not None:
        otra = fvm[(fvm.zona == "ZTE") & (fvm.circunscripcion != "") & (fvm.est_circ != "") & (fvm.circunscripcion != fvm.est_circ)]
        for _, s in otra.iterrows():
            alerta("Media", "Máquina vendida a cliente de otra circunscripción amazónica", s.cpe, s.f.strftime("%Y-%m-%d"), s.nombre, s.doc,
                   f"{s.desc} · vendida desde el establecimiento de {s.est.title()} ({s.est_circ}) a cliente domiciliado en {s.lugar} "
                   f"({s.circunscripcion}) · establecimiento inferido por la serie", s.vv, s.moneda)
    for _, s in mq[mq.usada].iterrows():
        alerta("Media", "Maquinaria usada importada", f"{s.dam} serie {int(s.NUM_SECSERIE)}", s.f.strftime("%Y-%m-%d"),
               f"{s['cat']} {s.marca} {s.modelo}", "",
               f"Año de fabricación {s.anio or 's/d'}" + (f" · {s.horas} horas" if s.horas else "") +
               f" · {s.id} · canal {CANALES.get(s.CANAL, s.CANAL)} · revisar valor declarado", s.MTO_VALORADU, "USD")
    for _, s in nc_maq.iterrows():
        alerta("Media", "Venta de maquinaria anulada o devuelta", s.cpe, s.f.strftime("%Y-%m-%d"), s.nombre, s.doc,
               f"NC motivo {s.tipo_ref} ({MOTIVOS_NC.get(s.tipo_ref, '')}) · {s.desc} · verificar destino final de la unidad", s.vv, s.moneda)
    for _, s in vm[(vm.tipo == "01") & (vm.estado == "2")].iterrows():
        alerta("Media", "Factura de maquinaria dada de baja", s.cpe, s.f.strftime("%Y-%m-%d"), s.nombre, s.doc,
               f"{s.desc}", s.vv, s.moneda)
    if dom is not None:
        primera = fvm.groupby("doc").f.min()
        for _, s in cl[(cl.maq > 0) & (cl.finsc != "")].iterrows():
            if s.doc not in primera:
                continue
            dias = (primera[s.doc] - pd.Timestamp(s.finsc)).days
            if 0 <= dias <= 180:
                alerta("Media", "Comprador de maquinaria con RUC reciente", s.doc, primera[s.doc].strftime("%Y-%m-%d"), s.nombre, s.doc,
                       f"RUC inscrito el {pd.Timestamp(s.finsc):%d/%m/%Y}; primera compra de maquinaria {dias} días después · {int(s.maq)} máquinas · "
                       f"actividad: {s.actividad or 's/d'}", s.usd, "USD")
    bajas_igv = e[(e.tipo == "01") & (e.estado == "2") & (e.igv > 0)]
    vig_sin = e[(e.tipo == "01") & (e.estado == "0") & (e.igv == 0)]
    reem = bajas_igv.merge(vig_sin, on=["doc", "moneda"], suffixes=("_b", "_r"))
    reem = reem[((reem.vv_b - reem.vv_r).abs() < 1) & (reem.f_r >= reem.f_b) & ((reem.f_r - reem.f_b).dt.days <= 30)]
    reem = reem[(reem.linea_b == "Maquinaria") | (reem.igv_b >= 100)]  # umbral de materialidad fuera de maquinaria
    reem = reem.sort_values("f_r").drop_duplicates("cpe_b")
    for _, s in reem.iterrows():
        alerta("Alta" if s.linea_b == "Maquinaria" else "Media", "Factura con IGV dada de baja y reemitida sin IGV", s.cpe_r, s.f_r.strftime("%Y-%m-%d"),
               s.nombre_b, s.doc, f"{s.cpe_b} del {s.f_b:%d/%m/%Y} con IGV {s.moneda} {s.igv_b:,.2f}, dada de baja; reemitida como {s.cpe_r} "
               f"del {s.f_r:%d/%m/%Y} sin IGV · línea {s.linea_b}", s.vv_r, s.moneda)
    reemitidas = dict(zip(reem.cpe_r, zip(reem.cpe_b, reem.f_b.dt.strftime("%Y-%m-%d"), reem.igv_b)))

    # Trazabilidad por número de serie (casos documentados con la factura del emisor)
    casos = []
    fx = leer_facturas_xml(r_xml)
    xml_cpes = set(fx.cpe) if len(fx) else set()
    filas_traz = pd.read_csv(r_traz, dtype=str).fillna("") if r_traz else pd.DataFrame(columns=["cpe"])
    for col in ["cpe", "serie_maquina", "serie_motor", "modelo", "ubicacion_entrega", "direccion_entrega", "fuente", "nota"]:
        if col not in filas_traz:
            filas_traz[col] = ""
    if len(fx):
        maq_x = fx[fx.serie != ""]
        auto = pd.DataFrame({
            "cpe": maq_x.cpe, "serie_maquina": maq_x.serie, "serie_motor": maq_x.motor, "modelo": maq_x.modelo,
            "ubicacion_entrega": [", ".join(x for x in (a, b, c) if x) if a and b and c else "" for a, b, c in zip(maq_x.dist, maq_x.prov, maq_x.dep)],
            "direccion_entrega": maq_x.dir,
            "fuente": "XML de la factura" + maq_x.est_cod.map(lambda x: f" · establecimiento {x}" if x else "")
                      + maq_x.oc.map(lambda x: f" · orden de compra {x}" if x else "") + maq_x.guias.map(lambda x: f" · guías {x}" if x else ""),
            "nota": maq_x.desc + maq_x.exencion.map(lambda x: {"10": " · gravada (código 10)", "20": " · exonerada (código 20)", "30": " · inafecta (código 30)"}.get(x, f" · afectación {x}" if x else ""))})
        manual = set(filas_traz.cpe)
        filas_traz = pd.concat([filas_traz, auto[~auto.cpe.isin(manual)]], ignore_index=True).fillna("")
    if len(filas_traz):
        buscar = ubicador(r_ubi)
        t = filas_traz
        for _, c in t.iterrows():
            venta = vm[vm.cpe == c.cpe]
            s = venta.iloc[0] if len(venta) else None
            imp = mq[(c.serie_maquina != "") & mq.id.str.endswith(c.serie_maquina)]
            if not len(imp) and c.serie_motor:
                imp = mq[mq.motor == c.serie_motor]
            i = imp.iloc[0] if len(imp) else None
            partes = [x.strip() for x in c.ubicacion_entrega.split(",")]
            ub = buscar(partes[2], partes[1], partes[0]) if len(partes) == 3 else None
            b = reemitidas.get(c.cpe)
            casos.append({
                "cpe": c.cpe, "serie": c.serie_maquina, "motor": c.serie_motor, "fuente": c.fuente, "nota": c.nota,
                "entrega": c.ubicacion_entrega, "entrega_dir": c.direccion_entrega, "entrega_zona": ub.zona if ub is not None else "Sin dato",
                "venta": None if s is None else {"f": s.f.strftime("%Y-%m-%d"), "cli": s.nombre, "ruc": s.doc, "mon": s.moneda, "vv": r2(s.vv),
                                                 "igv": r2(s.igv), "desc": s.desc, "zona": s.zona, "lugar": s.lugar},
                "baja": None if not b else {"cpe": b[0], "f": b[1], "igv": r2(b[2])},
                "entrega_circ": ub.circunscripcion if ub is not None and hasattr(ub, "circunscripcion") else "",
                "dam": None if i is None else {"dam": i.dam, "serie": int(i.NUM_SECSERIE), "f": i.f.strftime("%Y-%m-%d"), "canal": i.CANAL,
                                               "dest": i.dest, "dest_circ": DEST_CIRC.get(i.dest, ""), "dep_dam": i.dep_dam, "dep_f": i.dep_f,
                                               "conv": i.conv, "cif": r2(i.MTO_VALORADU), "anio": i.anio, "modelo": i.modelo,
                                               "dias": int((s.f - i.f).days) if s is not None else None},
                "cif_ref": r2(mq[(mq.modelo == (i.modelo if i is not None else c.get("modelo", ""))) & ~mq.usada].cif_u.median()) if (i is not None or c.get("modelo", "")) else None,
            })

    multi = cl[cl.maq >= 3]
    for _, s in multi.iterrows():
        alerta("Media", "Cliente con 3 o más máquinas", s.doc, s.ult, s.nombre, s.doc,
               f"{int(s.maq)} máquinas facturadas · {s.tipo} · verificar ubicación y uso en la zona", s.usd, "USD")
    for _, s in vig[(vig.tdoc == "0") & (vig.tipo == "01") & (vig.linea != "Maquinaria")].groupby("doc").agg(
            nombre=("nombre", "first"), n=("cpe", "size"), usd=("vv", "sum"), f=("f", "max")).reset_index().iterrows():
        alerta("Baja", "Ventas a no domiciliado", s.doc, s.f.strftime("%Y-%m-%d"), s.nombre, s.doc,
               f"{int(s.n)} CPE (repuestos, servicios u otros ingresos)", s.usd, "USD")
    for _, s in fac[(fac.igv > 0) & (fac.linea.isin(["Repuestos", "Servicio técnico"]))].iterrows():
        alerta("Baja", "Repuestos o servicios con IGV", s.cpe, s.f.strftime("%Y-%m-%d"), s.nombre, s.doc,
               f"Línea {s.linea} · IGV {s.igv:,.2f}", s.vv, s.moneda)
    for item, row in clas.iterrows():
        alerta("Media", "Mismo número de parte en varias subpartidas", item, "", "", "",
               f"Subpartidas: {', '.join(row.hs)} · {int(row.n)} series en {int(row.dams)} DAM", row.cif, "USD")
    for s in disp_series:
        if abs(s["dev"]) >= 50:
            alerta("Media", "Valor unitario atípico (mismo número de parte)", f"{s['dam']} serie {s['serie']}", s["fecha"], s["item"], "",
                   f"FOB unitario {s['fob_u']:,.2f} vs mediana {s['med']:,.2f} ({s['dev']:+.0f} %) · canal {CANALES.get(s['canal'], s['canal'])}",
                   s["fob_u"], "USD")
    orden = {"Alta": 0, "Media": 1, "Baja": 2}
    alertas.sort(key=lambda a: (orden[a["nivel"]], a["tipo"], a["fecha"] or ""))
    info_cpe = e.set_index("cpe")[["igv", "linea", "tcli", "doc"]].to_dict("index")
    zona_doc = dict(zip(cl.doc, cl.zona)) if "zona" in cl else {}
    tcli_doc = dict(zip(cl.doc, cl.tipo))
    trazados = {c["cpe"] for c in casos if c.get("dam")}
    for a in alertas:
        i = info_cpe.get(a["ref"])
        mk = []
        if i is not None:
            if i["igv"] > 0:
                mk.append("igv")
            mk.append({"Maquinaria": "maq", "Repuestos": "rep", "Servicio técnico": "ser", "Otros ingresos": "otr"}.get(i["linea"], ""))
        elif re.match(r"^\d{3}-\d{4}-\d{2}-", a["ref"]) or a["tipo"] in ("Mismo número de parte en varias subpartidas",):
            mk.append("imp")
        doc = a.get("ruc") or (i or {}).get("doc", "")
        z = zona_doc.get(doc, "")
        mk.append({"ZTE": "zte", "ZTC": "ztc", "Extranjero": "ext"}.get(z, ""))
        mk.append({"Entidad pública": "pub", "Persona natural": "pn"}.get(tcli_doc.get(doc, ""), ""))
        if a["ref"] in xml_cpes:
            mk.append("xml")
        if a["ref"] in trazados:
            mk.append("traza")
        if a["tipo"] == "Maquinaria vendida a no domiciliado" and a["nivel"] == "Baja":
            mk.append("exp")
        a["mk"] = [x for x in mk if x]
        a["igv"] = bool(i is not None and i["igv"] > 0)

    # ---------------- Salida ----------------
    datos = {
        "meta": {
            "contribuyente": m.NOM_RAZONSOCIAL.iloc[0], "ruc": m.NUM_DOCIDENT.iloc[0],
            "domicilios": sorted(m.DIR_PARTIC.dropna().unique().tolist()),
            "desde": meses[0], "hasta": meses[-1], "generado": date.today().isoformat(), "portal": portal or "",
            "dam_desde": m.f.min().strftime("%Y-%m-%d"), "dam_hasta": m.f.max().strftime("%Y-%m-%d"),
            "cpe_desde": e.f.min().strftime("%Y-%m-%d"), "cpe_hasta": e.f.max().strftime("%Y-%m-%d"),
            "n_dam": int(m.dam.nunique()), "n_series": int(len(m)), "n_cpe": int(len(e)), "n_det": int(len(dl)),
            "aduanas": ADUANAS, "canales": CANALES, "motivos": MOTIVOS_NC, "destinos": DESTINOS, "regimenes": REGIMENES,
        },
        "kpi": {
            "cif": r2(m.MTO_VALORADU.sum()), "fob": r2(m.MTO_FOBDOL.sum()), "flete": r2(m.MTO_FLETEDOL.sum()),
            "cif_maq": r2(mq.MTO_VALORADU.sum()), "uds_maq": int(mq.CNT_COMER.sum()), "maq_usada": int(mq.usada.sum()),
            "maq_verde_cif": r2(mq[mq.CANAL == "V"].MTO_VALORADU.sum()),
            "cif_lib": r2(m[m.COD_TIPCONVENIO == "C"].MTO_VALORADU.sum()),
            "dam_rojo": int((dec.canal == "F").sum()), "dam_naranja": int((dec.canal == "D").sum()), "dam_verde": int((dec.canal == "V").sum()),
            "fac_n": int((e.tipo == "01").sum()), "nc_n": int((e.tipo == "07").sum()), "anul_n": int(len(anul)),
            "anul_usd": r2(anul[anul.moneda == "USD"].total.sum()), "anul_pen": r2(anul[anul.moneda == "PEN"].total.sum()),
            "ven_usd": r2(fac[fac.moneda == "USD"].vv.sum()), "ven_pen": r2(fac[fac.moneda == "PEN"].vv.sum()),
            "nc_usd": r2(nc[nc.moneda == "USD"].vv.sum()), "nc_pen": r2(nc[nc.moneda == "PEN"].vv.sum()),
            "igv_n": int((fac.igv > 0).sum()), "igv_maq_n": int(((fac.igv > 0) & (fac.linea == "Maquinaria")).sum()),
            "igv_monto_usd": r2(fac[(fac.igv > 0) & (fac.moneda == "USD")].igv.sum()),
            "igv_monto_pen": r2(fac[(fac.igv > 0) & (fac.moneda == "PEN")].igv.sum()),
            "nodom_n": int((fac.tdoc == "0").sum()), "clientes": int(e.doc.nunique()),
            "top10": round(top10, 1), "hhi": round(hhi, 0),
            "maq_vend": int(((vm.tipo == "01") & (vm.estado == "0")).sum()),
            "maq_nc": int(len(nc_maq)),
            "sm_series": int(len(sm)), "sm_cif": r2(sm.MTO_VALORADU.sum()),
            "clas_n": int(len(clas)), "disp_n": int(len(disp)),
        },
        "dom": None if dom is None else {
            "fecha": (dom.fecha_padron.iloc[0] if len(dom) and "fecha_padron" in dom else ""),
            "rucs": int((cl.tipo != "No domiciliado").sum()), "encontrados": int(cl.zona.isin(["ZTE", "ZTC"]).sum()),
            "maq": {z: int((fvm.zona == z).sum()) for z in ["ZTE", "ZTC", "Extranjero", "Sin dato"]},
            "ztc_usd": r2(fvm[(fvm.zona == "ZTC") & (fvm.moneda == "USD")].vv.sum()),
            "ztc_pen": r2(fvm[(fvm.zona == "ZTC") & (fvm.moneda == "PEN")].vv.sum()),
            "ztc_igv": int(((fvm.zona == "ZTC") & (fvm.igv > 0)).sum()),
            "zte_igv": int(((fvm.zona == "ZTE") & (fvm.igv > 0)).sum()),
            "ztc_clientes": int(fvm[fvm.zona == "ZTC"].doc.nunique()),
            "sd_pn": int(((fvm.zona == "Sin dato") & (fvm.tcli == "Persona natural")).sum()),
            "pn_sin": int(((cl.tipo == "Persona natural") & (cl.zona == "Sin dato")).sum()),
            "por_dep": por_dep,
        },
        "imp": {
            "vistas": vistas, "destinos": destinos,
            "otros_reg": [{"reg": k, "t": REGIMENES.get(k, "Régimen " + k), "dams": int(v.dams), "series": int(v.series), "cif": r2(v.cif)}
                          for k, v in otros_reg.iterrows()],
            "mensual": imp_mes,
            "canal": [{"c": k, "n": int(v.n), "cif": r2(v.cif)} for k, v in canal.iterrows()],
            "convenio": [{"k": k, "series": int(v.series), "cif": r2(v.cif)} for k, v in conv.iterrows()],
            "aduana": [{"cod": k, "n": int(v.n), "cif": r2(v.cif), "flete_med": r2(v.flete_med)} for k, v in aduana.iterrows()],
            "partidas": [{"hs": k, "ej": v.ej, "series": int(v.series), "dams": int(v.dams), "uds": r2(v.uds), "cif": r2(v.cif), "pct": r2(v.pct)}
                         for k, v in part.head(40).iterrows()],
            "dams": [{"dam": s.dam, "f": s.fecha.strftime("%Y-%m-%d"), "ad": s.aduana, "dest": s.destino, "canal": s.canal,
                      "series": int(s.series), "fob": r2(s.fob), "flete": r2(s.flete), "seguro": r2(s.seguro), "cif": r2(s.cif),
                      "flete_pct": r2(s.flete_pct), "maq": int(s.maq), "conv": s.conv} for _, s in dec.iterrows()],
            "sm_marca": [{"marca": k, "series": int(v.series), "dams": int(v.dams), "cif": r2(v.cif)} for k, v in sm_marca.iterrows()],
            "disp": [{"item": k, "n": int(v.n), "dams": int(v.dams), "med": r2(v.med), "mn": r2(v.mn), "mx": r2(v.mx), "ratio": r2(v.ratio)}
                     for k, v in disp.iterrows()],
            "disp_series": disp_series,
            "clas": [{"item": k, "hs": v.hs, "n": int(v.n), "dams": int(v.dams), "cif": r2(v.cif)} for k, v in clas.iterrows()],
        },
        "maq": {
            "resumen": resumen_maq, "mensual": maq_mes, "puntos": puntos, "deposito": deposito, "exportaciones": exportaciones,
            "establecimientos": sorted(establecimientos.values(), key=lambda x: x["dig"]),
            "imp": [{"dam": s.dam, "serie": int(s.NUM_SECSERIE), "f": s.f.strftime("%Y-%m-%d"), "canal": s.CANAL, "hs": s.NUM_PARTNANDI,
                     "cat": s["cat"], "marca": s.marca, "modelo": s.modelo, "anio": s.anio, "id": s.id, "motor": s.motor,
                     "usada": bool(s.usada), "horas": s.horas, "dest": s.dest, "dep_dam": s.dep_dam, "dep_f": s.dep_f,
                     "cant": int(s.CNT_COMER), "fob": r2(s.MTO_FOBDOL), "cif": r2(s.MTO_VALORADU), "conv": s.conv}
                    for _, s in mq.sort_values("f").iterrows()],
            "ventas": [{"cpe": s.cpe, "f": s.f.strftime("%Y-%m-%d"), "ruc": s.doc, "cli": s.nombre, "tcli": s.tcli, "desc": s.desc,
                        "cat": s["cat"], "mon": s.moneda, "vv": r2(s.vv), "igv": r2(s.igv), "tot": r2(s.total),
                        "est": s.estado, "mot": s.tipo_ref if s.tipo == "07" else "", "usado": bool(s.usado),
                        "zona": s.zona, "lugar": s.lugar, "dep": s.departamento, "cond": s.condicion, "eruc": s.eruc, "act": s.actividad,
                        "est": s.est, "circ": s.circunscripcion}
                       for _, s in vm.sort_values("f").iterrows()],
        },
        "ventas": {
            "mensual": ven_mes, "lineas": lineas,
            "nc": [{"mot": k, "n": int(v.n), "usd": r2(v.usd), "pen": r2(v.pen), "maq": int(v.maq)} for k, v in ncm.iterrows()],
            "tcli": [{"t": k, "n": int(v.n), "usd": r2(v.usd), "pen": r2(v.pen), "maq": int(v.maq), "clientes": int(v.c)}
                     for k, v in cl.groupby("tipo").agg(n=("n", "sum"), usd=("usd", "sum"), pen=("pen", "sum"), maq=("maq", "sum"),
                                                        c=("doc", "size")).sort_values("usd", ascending=False).iterrows()],
            "clientes": [{"ruc": s.doc, "nombre": s.nombre, "tipo": s.tipo, "n": int(s.n), "usd": r2(s.usd), "pen": r2(s.pen),
                          "nc_n": int(s.nc_n), "nc_usd": r2(s.nc_usd), "nc_pen": r2(s.nc_pen), "maq": int(s.maq),
                          "igv_n": int(s.igv_n), "ult": s.ult, "zona": s.zona, "lugar": lugar(s), "dep": s.departamento,
                          "eruc": s.eruc, "cond": s.condicion, "dir": s.direccion, "act": s.actividad, "finsc": s.finsc} for _, s in cl.iterrows()],
        },
        "casos": casos,
        "xml_cpes": sorted(xml_cpes),
        "alertas": alertas,
    }
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))
    print(f"OK {salida}: {len(alertas)} alertas, {len(datos['ventas']['clientes'])} clientes, {len(datos['maq']['imp'])} máquinas importadas")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for a in ("dams", "cpe", "detalle", "salida"):
        ap.add_argument(a)
    ap.add_argument("--domicilios")
    ap.add_argument("--ubigeos", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "referencias", "ubigeo_zte.csv"))
    ap.add_argument("--portal", help="URL del portal público de comprobantes del emisor (va cifrada dentro de los datos)")
    ap.add_argument("--consulta-ruc", nargs="*", default=[], help="Resultados de la consulta múltiple de RUC de SUNAT (ZIP o TXT)")
    ap.add_argument("--trazabilidad", help="CSV de casos: cpe, serie_maquina, serie_motor, modelo, ubicacion_entrega (DISTRITO, PROVINCIA, DEPARTAMENTO), direccion_entrega, fuente, nota")
    ap.add_argument("--facturas-xml", nargs="*", default=[], help="XML de comprobantes del emisor (archivos, carpetas o ZIP)")
    a = ap.parse_args()
    main(a.dams, a.cpe, a.detalle, a.salida, a.domicilios, a.ubigeos, a.portal, a.consulta_ruc, a.trazabilidad, a.facturas_xml)
