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
           "226": "Iquitos", "217": "Pucallpa"}
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
    return m


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


def cargar_domicilios(r_dom, r_ubi):
    """Admite ubigeo o, si falta, departamento/provincia/distrito por nombre; y la actividad económica."""
    d = pd.read_csv(r_dom, dtype=str).fillna("")
    d.columns = [norm(c).lower().replace(" ", "_") for c in d.columns]
    u = pd.read_csv(r_ubi, dtype=str).fillna("")
    u = u[u.ubigeo.str.fullmatch(r"\d{6}")]
    for c in ["ubigeo", "departamento", "provincia", "distrito", "estado", "condicion", "direccion", "actividad"]:
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


def main(r_dams, r_cpe, r_det, salida, r_dom=None, r_ubi=None):
    m = leer_dams(r_dams)
    e = leer_cpe(r_cpe)
    dl = leer_detalle(r_det)

    meses = pd.period_range(min(m.f.min(), e.f.min()), max(m.f.max(), e.f.max()), freq="M").strftime("%Y-%m").tolist()

    # ---------------- Importaciones ----------------
    dec = m.groupby("dam").agg(
        fecha=("f", "first"), aduana=("COD_ADUANA", "first"), destino=("COD_ADUDEST", "first"),
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
                                    "dev": round(dev * 100, 1), "canal": s.CANAL})

    # Clasificación: un mismo número de parte en más de una subpartida
    clas = p.groupby("DES_COMER").agg(hs=("NUM_PARTNANDI", lambda s: sorted(set(s))), n=("dam", "size"),
                                      dams=("dam", "nunique"), cif=("MTO_VALORADU", "sum"))
    clas = clas[clas.hs.str.len() > 1].sort_values("n", ascending=False)

    # ---------------- Maquinaria importada ----------------
    mq = m[m.maq].copy()
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
    dom = cargar_domicilios(r_dom, r_ubi) if r_dom else None
    info = dom.to_dict("index") if dom is not None else {}
    VACIO = {"zona": "", "departamento": "", "provincia": "", "distrito": "", "eruc": "", "condicion": "", "direccion": "", "actividad": ""}

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
    for _, s in vm[(vm.tipo == "01") & (vm.estado == "0") & (vm.tdoc == "0")].iterrows():
        alerta("Alta", "Maquinaria vendida a no domiciliado", s.cpe, s.f.strftime("%Y-%m-%d"), s.nombre, s.doc,
               f"{s.desc} · verificar DAM de exportación o reexportación", s.vv, s.moneda)
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

    # ---------------- Salida ----------------
    datos = {
        "meta": {
            "contribuyente": m.NOM_RAZONSOCIAL.iloc[0], "ruc": m.NUM_DOCIDENT.iloc[0],
            "domicilios": sorted(m.DIR_PARTIC.dropna().unique().tolist()),
            "desde": meses[0], "hasta": meses[-1], "generado": date.today().isoformat(),
            "dam_desde": m.f.min().strftime("%Y-%m-%d"), "dam_hasta": m.f.max().strftime("%Y-%m-%d"),
            "cpe_desde": e.f.min().strftime("%Y-%m-%d"), "cpe_hasta": e.f.max().strftime("%Y-%m-%d"),
            "n_dam": int(m.dam.nunique()), "n_series": int(len(m)), "n_cpe": int(len(e)), "n_det": int(len(dl)),
            "aduanas": ADUANAS, "canales": CANALES, "motivos": MOTIVOS_NC,
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
            "resumen": resumen_maq, "mensual": maq_mes, "puntos": puntos,
            "imp": [{"dam": s.dam, "serie": int(s.NUM_SECSERIE), "f": s.f.strftime("%Y-%m-%d"), "canal": s.CANAL, "hs": s.NUM_PARTNANDI,
                     "cat": s["cat"], "marca": s.marca, "modelo": s.modelo, "anio": s.anio, "id": s.id, "motor": s.motor,
                     "usada": bool(s.usada), "horas": s.horas,
                     "cant": int(s.CNT_COMER), "fob": r2(s.MTO_FOBDOL), "cif": r2(s.MTO_VALORADU), "conv": s.conv}
                    for _, s in mq.sort_values("f").iterrows()],
            "ventas": [{"cpe": s.cpe, "f": s.f.strftime("%Y-%m-%d"), "ruc": s.doc, "cli": s.nombre, "tcli": s.tcli, "desc": s.desc,
                        "cat": s["cat"], "mon": s.moneda, "vv": r2(s.vv), "igv": r2(s.igv), "tot": r2(s.total),
                        "est": s.estado, "mot": s.tipo_ref if s.tipo == "07" else "", "usado": bool(s.usado),
                        "zona": s.zona, "lugar": s.lugar, "dep": s.departamento, "cond": s.condicion, "eruc": s.eruc, "act": s.actividad}
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
                          "eruc": s.eruc, "cond": s.condicion, "dir": s.direccion, "act": s.actividad} for _, s in cl.iterrows()],
        },
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
    a = ap.parse_args()
    main(a.dams, a.cpe, a.detalle, a.salida, a.domicilios, a.ubigeos)
