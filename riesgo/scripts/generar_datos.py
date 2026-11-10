"""Genera los datos del tablero de gestión de riesgo: maquinaria importada con destino a la
Amazonía y su venta.

Fuentes obligatorias:
  1. DAM (CSV, una fila por serie; todos los regímenes y aduanas de destino del importador)
  2. CPE emitidos (TXT separado por «|», una fila por comprobante)
  3. Detalle de CPE emitidos (TXT separado por «|», una fila por ítem)

Fuentes opcionales:
  --domicilios    domicilio fiscal de los clientes (sale de extraer_domicilios.py, padrón reducido del RUC)
  --consulta-ruc  resultados de la consulta múltiple de RUC (actividad, fecha de inscripción, domicilio)
  --facturas-xml  XML (UBL 2.1) de los comprobantes del emisor: archivos, carpetas o ZIP
  --control-ia    cuaderno de control de la intendencia (xlsx/xlsm): diligencia, NCN, RI y traslados
  --trazabilidad  casos documentados a mano (CSV: cpe, serie_maquina, serie_motor, modelo,
                  ubicacion_entrega, direccion_entrega, fuente, nota)
  --transportistas lista simple de transportistas vigilados (TXT: un RUC por línea, opcionalmente
                  seguido del nombre). Entran en la «Lista del día» de guías de remisión.

Uso:
  python3 -I generar_datos.py DAMS.csv CPE_EMITIDOS.txt CPE_DETALLE.txt salida.json [opciones]

La unidad de seguimiento es la máquina (DAM y serie). Cada venta de maquinaria con indicios de
salida de la zona del beneficio es un caso. El caso reúne la venta, la cadena de comprobantes
(bajas, notas de crédito y reemisiones), la máquina enlazada por su número de serie, el control
de su DAM (tributos, NCN, regularización, RI y traslados) y las otras máquinas de la misma DAM.

Los archivos de origen y el JSON de salida contienen información con reserva tributaria: no se
versionan (ver .gitignore). El JSON se publica solo cifrado (ver cifrar.py).
"""
import argparse
import io
import json
import os
import re
import sys
import unicodedata
import zipfile
from datetime import date
from collections import Counter
from itertools import combinations

import pandas as pd

ADUANAS = {"118": "Marítima del Callao", "235": "Aérea y Postal del Callao", "271": "Tarapoto",
           "226": "Iquitos", "217": "Pucallpa", "280": "Puerto Maldonado", "262": "Desaguadero"}
DESTINOS = {"271": "Tarapoto", "217": "Pucallpa", "280": "Puerto Maldonado", "226": "Iquitos", "": "Sin aduana de destino"}
CANALES = {"V": "Verde", "D": "Naranja", "F": "Rojo"}
MOTIVOS_NC = {  # Catálogo 09 SUNAT
    "01": "Anulación de la operación", "02": "Anulación por error en el RUC",
    "03": "Corrección por error en la descripción", "04": "Descuento global",
    "05": "Descuento por ítem", "06": "Devolución total", "07": "Devolución por ítem",
    "08": "Bonificación", "09": "Disminución en el valor", "10": "Otros conceptos",
    "11": "Ajustes de operaciones de exportación", "12": "Ajustes afectos al IVAP",
    "13": "Ajustes – montos y/o fechas de pago",
}
NC_ANULA = {"01", "02", "03", "06"}      # notas de crédito que dejan sin efecto toda la factura
AFECTACION = {"10": "Gravado", "11": "Gravado (retiro)", "20": "Exonerado", "21": "Exonerado (transferencia gratuita)",
              "30": "Inafecto", "40": "Exportación"}
LINEAS = {"FR": "Repuestos", "FS": "Servicio técnico", "FP": "Maquinaria", "FV": "Otros ingresos"}
HS_MAQ = {"8429", "8701", "8502", "8408", "8426", "8427", "8430", "8474", "8704", "8705"}
MENOR = {"USD": 10000, "PEN": 34000}   # valor de venta mínimo de un caso: debajo están anticipos, accesorios e implementos
TASA_IMP = 0.18      # IGV 16 % + IPM 2 % sobre el valor en aduana: lo que se paga al trasladar a la ZTC
CAT_MERC = {         # tipo de mercancía del cuaderno de traslados → tipos de máquina compatibles
    "MAQUINARIA AMARILLA": {"Excavadora", "Retroexcavadora", "Cargador frontal", "Minicargador", "Motoniveladora",
                            "Rodillo compactador", "Tractor de orugas"},
    "MAQUINARIA AGRICOLA": {"Tractor agrícola", "Implemento agrícola"},
    "MOTORES DIVERSOS": {"Motor diésel", "Motor marino", "Grupo electrógeno"},
}
MERCANCIA = {cat: m for m, cats in (("Maquinaria amarilla", ("Excavadora", "Retroexcavadora", "Cargador frontal", "Minicargador", "Motoniveladora",
                                                             "Rodillo compactador", "Tractor de orugas", "Martillo hidráulico")),
                                     ("Maquinaria agrícola", ("Tractor agrícola", "Implemento agrícola")),
                                     ("Motores y grupos electrógenos", ("Motor diésel", "Motor marino", "Grupo electrógeno"))) for cat in cats}
PUBLICO = re.compile(r"MUNICIPALIDAD|GOBIERNO REGIONAL|MINISTERIO|PROGRAMA |PROYECTO ESPECIAL|"
                     r"GERENCIA (SUB)?REGIONAL|GERENCIA TERRITORIAL|UNIVERSIDAD NACIONAL|EJERCITO|"
                     r"MARINA DE GUERRA|FUERZA AEREA|INSTITUTO NACIONAL|SERVICIO NACIONAL|"
                     r"PETROLEOS DEL PERU|SEGURO SOCIAL|ESSALUD|DIRECCION REGIONAL|UNIDAD EJECUTORA")
REVENDE = re.compile(r"VTA.*MAQUINARIA|VENTA.*MAQUINARIA|ALQUILER.*MAQUINARIA")
SIN_TRASLADO = {"NINGUNO", "NINGUNA", "NO", "SIN TRASLADO", "NO TIENE", "NO REGISTRA"}
PEND = {"REGISTRAR DILIGENCIA", "REGISTRAR RF", "EMITIR INFORME", "EMITIR RESOLUCION", "CON NOTIFICACION", "EMITIR NCN",
        "INGRESADA, SIN CONSOLIDAR"}
NS = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
      "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"}


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
    return None if x is None or pd.isna(x) else round(float(x), 2)


def fstr(x):
    return x.strftime("%Y-%m-%d") if x is not None and pd.notna(x) else ""


def claves_dam(x):
    """Números de DAM escritos a mano («118-2025-10-511887», «235-2017-10 14949») → aduana-año-régimen-número."""
    return [f"{a}-{b}-{c}-{int(d):06d}" for a, b, c, d in re.findall(r"(\d{3})-(\d{4})-(\d{2})[- ](\d{1,7})", str(x or ""))]


def leer_dams(ruta):
    m = pd.read_csv(ruta, dtype=str)
    for c in ["CNT_COMER", "MTO_FOBDOL", "MTO_FLETEDOL", "MTO_SEGDOL", "MTO_VALORADU"]:
        m[c] = pd.to_numeric(m[c])
    m["f"] = pd.to_datetime(m.FEC_DECLARACION)
    m["COD_REGIMEN"] = m.COD_REGIMEN.str.strip()
    m["dam"] = m.COD_ADUANA + "-" + m.ANN_PRESEN + "-" + m.COD_REGIMEN + "-" + m.NUM_DECLARACION.str.zfill(6)
    m["hs4"] = m.NUM_PARTNANDI.str[:4]
    m["cif_u"] = m.MTO_VALORADU / m.CNT_COMER
    m["conv"] = (m.COD_TIPCONVENIO.fillna("").str.strip() + "-" + m.COD_CONVENIO.fillna("").str.strip()).replace("-", "Sin beneficio")
    m["maq"] = m.hs4.isin(HS_MAQ) | (m.cif_u >= 15000)
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


# ---------------------------------------------------------------- XML de los comprobantes

def fuentes_xml(rutas):
    """(nombre, bytes) de cada XML: archivos sueltos, carpetas (recursivo) y ZIP, también ZIP dentro de ZIP."""
    def de_zip(z):
        for n in z.namelist():
            if n.lower().endswith(".xml"):
                yield n, z.read(n)
            elif n.lower().endswith(".zip"):
                try:
                    yield from de_zip(zipfile.ZipFile(io.BytesIO(z.read(n))))
                except zipfile.BadZipFile:
                    print(f"Aviso: {n} no es un ZIP válido", file=sys.stderr)
    for r in rutas or []:
        if os.path.isdir(r):
            for raiz, _, archivos in os.walk(r):
                for a in sorted(archivos):
                    p = os.path.join(raiz, a)
                    if a.lower().endswith(".xml"):
                        with open(p, "rb") as f:
                            yield p, f.read()
                    elif zipfile.is_zipfile(p):
                        yield from de_zip(zipfile.ZipFile(p))
                    elif a.lower().endswith((".7z", ".rar")):
                        print(f"Aviso: {p} está comprimido en {a.rsplit('.', 1)[-1]}; descomprímalo antes", file=sys.stderr)
        elif zipfile.is_zipfile(r):
            yield from de_zip(zipfile.ZipFile(r))
        elif os.path.isfile(r):
            with open(r, "rb") as f:
                yield r, f.read()


def leer_facturas_xml(rutas):
    """Lee los comprobantes en XML (UBL 2.1 de SUNAT). Devuelve:
    - items: una fila por ítem con la serie de la máquina y del motor que el emisor escribe en la descripción
    - docs: el comprobante completo (cabecera, partes, ítems, tributos, totales, pago y documento que modifica)
      para mostrarlo en el tablero
    - errores: archivos que no se pudieron leer."""
    import xml.etree.ElementTree as ET
    tipos = {"Invoice": "01", "CreditNote": "07", "DebitNote": "08"}
    filas, docs, errores, repetidos = [], {}, [], []
    for nombre, contenido in fuentes_xml(rutas):
        try:
            raiz = ET.fromstring(contenido)
        except ET.ParseError:
            errores.append(os.path.basename(nombre))
            continue
        tag = raiz.tag.split("}")[-1]
        if tag not in tipos:      # constancias de recepción (CDR) y otros XML
            continue

        def t(p, n=raiz):
            return ((n.findtext(p, default="", namespaces=NS) if n is not None else "") or "").strip()

        def num(p, n=raiz):
            v = t(p, n)
            try:
                return float(v) if v else None
            except ValueError:
                return None
        tipo = tipos[tag]
        cpe = f"{tipo}-{t('cbc:ID')}"
        if cpe in docs:
            repetidos.append(cpe)
            continue
        sup = raiz.find("cac:AccountingSupplierParty/cac:Party", NS)
        reg = sup.find("cac:PartyLegalEntity/cac:RegistrationAddress", NS) if sup is not None else None
        cli = raiz.find("cac:AccountingCustomerParty/cac:Party", NS)
        dcli = cli.find("cac:PostalAddress", NS) if cli is not None else None
        if (dcli is None or not t("cac:AddressLine/cbc:Line", dcli)) and cli is not None:
            dcli = cli.find("cac:PartyLegalEntity/cac:RegistrationAddress", NS)
        id_cli = cli.find("cac:PartyIdentification/cbc:ID", NS) if cli is not None else None
        lineas = []
        for ln in raiz.findall("cac:InvoiceLine", NS) + raiz.findall("cac:CreditNoteLine", NS) + raiz.findall("cac:DebitNoteLine", NS):
            cant = next((x for x in (ln.find(f"cbc:{q}Quantity", NS) for q in ("Invoiced", "Credited", "Debited")) if x is not None), None)
            desc = [d.text.strip() for d in ln.findall("cac:Item/cbc:Description", NS) if d.text and d.text.strip()]
            precio_con = next((num("cbc:PriceAmount", p) for p in ln.findall("cac:PricingReference/cac:AlternativeConditionPrice", NS)
                               if t("cbc:PriceTypeCode", p) == "01"), None)
            afect = t("cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:TaxExemptionReasonCode", ln)
            lineas.append({"n": t("cbc:ID", ln), "cant": float(cant.text) if cant is not None and cant.text else None,
                           "und": cant.get("unitCode", "") if cant is not None else "", "desc": desc,
                           "cod": t("cac:Item/cac:SellersItemIdentification/cbc:ID", ln),
                           "vu": num("cac:Price/cbc:PriceAmount", ln), "pu": precio_con, "valor": num("cbc:LineExtensionAmount", ln),
                           "igv": num("cac:TaxTotal/cbc:TaxAmount", ln), "afect": afect, "afect_t": AFECTACION.get(afect, "")})
            texto = norm(" / ".join(desc))
            busca = lambda pat: (re.search(pat, texto) or [None, ""])[1].strip()
            filas.append({"cpe": cpe, "f": t("cbc:IssueDate"), "mon": t("cbc:DocumentCurrencyCode"), "texto": " / ".join(desc),
                          "serie": busca(r"SERIE (?:DE )?MAQUINA[: ]*([A-Z0-9-]{5,20})") or busca(r"\bPIN[: ]*([A-Z0-9]{17})") or busca(r"\bVIN[: ]*([A-Z0-9]{17})"),
                          "motor": busca(r"SERIE (?:DE )?MOTOR[: ]*([A-Z0-9-]{5,20})"),
                          "modelo": busca(r"MODELO[: ]*([A-Z0-9.\- ]+?)(?: /|$)"), "marca": busca(r"MARCA[: ]*([A-Z0-9.\- ]+?)(?: /|$)"),
                          "anio": busca(r"ANO DE FABRICACION[: ]*(\d{4})"), "horas": busca(r"HORAS DE USO[: ]*([\d.,]+)"),
                          "afect": afect, "valor": num("cbc:LineExtensionAmount", ln)})
        pago = [{"id": t("cbc:PaymentMeansID", p), "monto": num("cbc:Amount", p), "f": t("cbc:PaymentDueDate", p)}
                for p in raiz.findall("cac:PaymentTerms", NS) if t("cbc:ID", p) == "FormaPago"]
        trib = [{"t": t("cac:TaxCategory/cac:TaxScheme/cbc:Name", s), "base": num("cbc:TaxableAmount", s), "monto": num("cbc:TaxAmount", s)}
                for s in raiz.findall("cac:TaxTotal/cac:TaxSubtotal", NS)]
        ref = raiz.find("cac:BillingReference/cac:InvoiceDocumentReference", NS)
        docs[cpe] = {
            "cpe": cpe, "tipo": tipo, "id": t("cbc:ID"), "f": t("cbc:IssueDate"), "hora": t("cbc:IssueTime"), "venc": t("cbc:DueDate"),
            "mon": t("cbc:DocumentCurrencyCode"), "oc": t("cac:OrderReference/cbc:ID"),
            "op": (raiz.find("cbc:InvoiceTypeCode", NS).get("listID", "") if raiz.find("cbc:InvoiceTypeCode", NS) is not None else ""),
            "emisor": {"ruc": t("cac:PartyIdentification/cbc:ID", sup), "nombre": t("cac:PartyLegalEntity/cbc:RegistrationName", sup),
                       "est": t("cbc:AddressTypeCode", reg), "dir": t("cac:AddressLine/cbc:Line", reg),
                       "lugar": ", ".join(x for x in (t("cbc:District", reg), t("cbc:CityName", reg), t("cbc:CountrySubentity", reg)) if x)},
            "cliente": {"doc": (id_cli.text or "").strip() if id_cli is not None else "", "tdoc": id_cli.get("schemeID", "") if id_cli is not None else "",
                        "nombre": t("cac:PartyLegalEntity/cbc:RegistrationName", cli), "dir": t("cac:AddressLine/cbc:Line", dcli),
                        "lugar": ", ".join(x for x in (t("cbc:District", dcli), t("cbc:CityName", dcli), t("cbc:CountrySubentity", dcli)) if x)},
            "notas": [n.text.strip() for n in raiz.findall("cbc:Note", NS) if n.text and n.text.strip()],
            "guias": [x.text.strip() for x in raiz.findall("cac:DespatchDocumentReference/cbc:ID", NS) if x.text],
            "pago": pago, "trib": trib, "lineas": lineas,
            "tot": {"valor": num("cac:LegalMonetaryTotal/cbc:LineExtensionAmount") or num("cac:RequestedMonetaryTotal/cbc:LineExtensionAmount"),
                    "igv": num("cac:TaxTotal/cbc:TaxAmount"), "dscto": num("cac:LegalMonetaryTotal/cbc:AllowanceTotalAmount"),
                    "total": num("cac:LegalMonetaryTotal/cbc:PayableAmount") or num("cac:RequestedMonetaryTotal/cbc:PayableAmount")},
            "ref": None if ref is None else {"id": t("cbc:ID", ref), "tipo": t("cbc:DocumentTypeCode", ref),
                                             "mot": t("cac:DiscrepancyResponse/cbc:ResponseCode"),
                                             "mot_t": t("cac:DiscrepancyResponse/cbc:Description")},
        }
        extra = {x.get("name"): (x.text or "").strip() for x in raiz.iter() if x.tag.split("}")[-1] == "Text" and x.get("name")}
        docs[cpe]["cliente"]["lugar_fac"] = extra.get("DisProDepCliente", "")
        docs[cpe]["emisor"]["sede"] = extra.get("DatosOfic", "")
    items = pd.DataFrame(filas, columns=["cpe", "f", "mon", "texto", "serie", "motor", "modelo", "marca", "anio", "horas", "afect", "valor"])
    return items, docs, errores, repetidos


# ---------------------------------------------------------------- cuaderno de control de la intendencia

def pares_traslado(num_dam, series):
    """(DAM, serie) de cada máquina de un traslado. La columna de series separa con «/» las series de cada DAM;
    si el traslado tiene una sola DAM, todas las series son suyas. Si no se puede asignar, devuelve []."""
    dams = claves_dam(num_dam)
    grupos = [g for g in (re.findall(r"\d+", x) for x in str(series or "").split("/")) if g]
    if len(dams) == 1:
        return [(dams[0], int(n)) for g in grupos for n in g]
    if dams and len(grupos) == len(dams):
        return [(d, int(n)) for d, g in zip(dams, grupos) for n in g]
    return []


def leer_control_ia(ruta, ruc):
    """Cuaderno de control de la intendencia (xlsx/xlsm), solo para el RUC indicado. Devuelve:
    - ctl: {dam: {"control": {...}, "ncn": [...], "ris": [...]}}
    - traslados: lista de expedientes de traslado con sus pares (DAM, serie)
    - meta: verificación del art. 2 y complejidad."""
    import openpyxl
    import warnings
    warnings.filterwarnings("ignore")
    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)

    def hoja(n):
        if n not in wb.sheetnames:
            return pd.DataFrame()
        rows = list(wb[n].iter_rows(values_only=True))
        h = next((i for i, r in enumerate(rows[:15]) if sum(isinstance(c, str) for c in r) >= 5), None)
        if h is None:
            return pd.DataFrame()
        cols = [str(c).strip() if c is not None else f"c{j}" for j, c in enumerate(rows[h])]
        return pd.DataFrame([r for r in rows[h + 1:] if any(c is not None for c in r)], columns=cols)
    txt = lambda v: "" if v is None or (not isinstance(v, str) and pd.isna(v)) else (v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else str(v).strip())
    num = lambda v: float(v) if isinstance(v, (int, float)) and v == v else None
    del_ruc = lambda df, col: df[df[col].astype(str).str.contains(ruc)] if len(df) and col in df else df.iloc[0:0]
    ctl = {}
    # ConsolidadoT primero; luego las hojas de cada especialista y la de ingreso, solo para DAM que aún no estén consolidadas
    fuentes = ["ConsolidadoT"] + [n for n in wb.sheetnames if n not in ("ConsolidadoT", "Ingreso de DAM")] + ["Ingreso de DAM"]
    for nombre in fuentes:
        ct = hoja(nombre)
        if not len(ct) or "Num_DAM" not in ct or "RUC_Importador" not in ct or "NroSolic_Reg" not in ct:
            continue
        for _, r in del_ruc(ct, "RUC_Importador").iterrows():
            for k in claves_dam(r.Num_DAM):
                if "control" in ctl.get(k, {}):
                    continue
                ctl.setdefault(k, {})["control"] = {
                    "tipo": txt(r.get("Tipo_DAM")), "dilig": txt(r.get("Resultado de la Diligencia_Aduana Destino")),
                    "fin": txt(r.get("Forma de Conclusion")), "ri": txt(r.get("Numero de la RI / RD")), "ri_f": txt(r.get("Fecha de RI / RD")),
                    "ciudad": txt(r.get("Ciudad_Mercancia") or r.get("Ciudad de la Mercancia")), "merc": txt(r.get("Tipo_Mercancia")),
                    "estado": txt(r.get("ESTADO ACTUAL")) or ("Ingresada, sin consolidar" if nombre == "Ingreso de DAM" else ""),
                    "igv": num(r.get("Regulariza_IGV")), "ipm": num(r.get("Regulariza_IPM")), "adv": num(r.get("Regulariza_ADValorem")),
                    "f_rf": txt(r.get("Fecha_Recon_Fisico"))[:10], "f_dil": txt(r.get("Fecha_Dilig_Dest"))[:10]}
    h1 = hoja("Hoja1")
    for _, r in h1.iterrows() if len(h1) else []:
        for k in set(claves_dam(r.get("DAM")) + claves_dam(r.get("Detalle Asunto"))):
            if k in ctl:
                ctl[k].setdefault("ris", []).append({"ri": txt(r.get("Nro Documento definitivo")), "asunto": txt(r.get("Detalle Asunto")),
                                                     "pdf": txt(r.get("CONTIENE AUTORIZA"))})
    meta = {"art2": [], "complejidad": None}
    vistos = set()
    for _, r in del_ruc(hoja("ConsolidadoA2"), "RUC_Importador").iterrows():
        inf = txt(r.get("Nro_Informe_Art.2"))
        if inf in vistos:
            continue
        vistos.add(inf)
        meta["art2"].append({"periodo": txt(r.get("Periodo_Verificacion")), "informe": inf, "f": txt(r.get("Fecha_Inform_Art2")),
                             "resultado": txt(r.get("RESULTADO")), "aduana": txt(r.get("Aduana_Jurisdiccion"))})
    if "Complejidad" in wb.sheetnames:
        filas_c = list(wb["Complejidad"].iter_rows(values_only=True))
        media = next((r[1] for r in filas_c if r and r[0] and "Media global" in str(r[0])), None)
        for r in filas_c:
            vals = [c for c in r if c is not None]
            for j, c in enumerate(vals[:-2]):
                if str(c).strip() == ruc and isinstance(vals[j + 1], (int, float)):
                    meta["complejidad"] = {"valor": round(float(vals[j + 1]), 3), "n": int(vals[j + 2]) if isinstance(vals[j + 2], (int, float)) else None,
                                           "media": round(float(media), 3) if isinstance(media, (int, float)) else None}
    for _, r in del_ruc(hoja("NCN"), "RUC_Importador").iterrows():
        for k in claves_dam(r.Num_DAM):
            ctl.setdefault(k, {}).setdefault("ncn", []).append({
                "ri": txt(r.get("Num_Res")), "ri_f": txt(r.get("Fecha RI")), "peco": txt(r.get("N_NCN_PECO")), "amaz": txt(r.get("N_NCN_AMAZONIA")),
                "f": txt(r.get("F_Emision_NCN")), "total": num(r.get("TOTAL")), "anulada": "ANULAD" in txt(r.get("OBSERVACIONES")).upper()})
    traslados = []
    for _, r in del_ruc(hoja("Traslados"), "Doc_Solicitante").iterrows():
        traslados.append({"exp": txt(r.get("N_Expediente")), "f": txt(r.get("Fecha_Expediente"))[:10], "tipo": txt(r.get("Tipo_Traslado")),
                          "merc": txt(r.get("Tipo_Mercancia")), "cant": num(r.get("Cantidad_Trasladada")),
                          "monto": num(r.get("Monto_Pagado_Garantizado")), "doc": txt(r.get("Tipo_Documento")), "ndoc": txt(r.get("N_Documento")),
                          "ri": txt(r.get("Num_Res")), "ri_f": txt(r.get("Fecha_res"))[:10], "res": txt(r.get("Resultado")).capitalize(),
                          "dams": claves_dam(r.get("Num_DAM")), "pares": pares_traslado(r.get("Num_DAM"), r.get("Series_DAM"))})
    return ctl, traslados, meta


def leer_consultas(ruta):
    """Libro de consultas completado por el equipo (ver consultas_xlsx.py). Devuelve:
    - dam: {dam: {"control": {...}, "ncn": [...], "fuente": ...}} con el control informado por la IA de destino
    - series: {cpe: {...}} con la DAM ubicada para una serie que no estaba en las DAM del periodo
    - pin: [{exp, dam, serie, pin, motor}] de las DAM anteriores al periodo con traslados; pin_filas: filas por traslado"""
    import openpyxl
    import warnings
    warnings.filterwarnings("ignore")
    wb = openpyxl.load_workbook(ruta, data_only=True, read_only=True)

    def filas(nombre):
        if nombre not in wb.sheetnames:
            return []
        rows = list(wb[nombre].iter_rows(values_only=True))
        if not rows:
            return []
        cab = [str(c or "").strip() for c in rows[0]]
        return [dict(zip(cab, r)) for r in rows[1:] if any(v not in (None, "") for v in r)]
    txt = lambda v: "" if v is None else (v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else str(v).strip())

    def fch(v):
        if hasattr(v, "strftime"):
            return v.strftime("%Y-%m-%d")
        m_ = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", txt(v))
        return f"{m_[3]}-{int(m_[2]):02d}-{int(m_[1]):02d}" if m_ else txt(v)[:10]

    def num(v):
        if isinstance(v, (int, float)):
            return float(v)
        t_ = txt(v).replace("S/", "").replace("USD", "").replace(",", "").strip()
        return float(t_) if re.fullmatch(r"\d+(\.\d+)?", t_) else None
    out = {"dam": {}, "series": {}, "pin": [], "pin_filas": Counter()}
    llenar = ("Modalidad", "Monto de tributos", "Estado de la solicitud", "Resultado de la diligencia", "Fecha del reconocimiento físico",
              "Fecha de conclusión", "RI o RD", "NCN", "Traslado (expediente y fecha)", "Observaciones")
    for r in filas("DAM otras intendencias"):
        dam = (claves_dam(r.get("DAM")) or [""])[0]
        if not dam or not any(txt(r.get(c_)) for c_ in llenar):
            continue
        modal, sol = txt(r.get("Modalidad")), txt(r.get("Estado de la solicitud"))
        mon = {"S/": "PEN", "USD": "USD"}.get(txt(r.get("Moneda")).upper(), "") or \
            ("PEN" if norm(modal) == "CANCELADA" else "USD" if norm(modal).startswith("GARANTIA") else "")
        control = {"tipo": modal, "dilig": txt(r.get("Resultado de la diligencia")), "fin": "", "ri": txt(r.get("RI o RD")),
                   "ri_f": fch(r.get("Fecha de la RI")), "estado": "", "igv": None, "ipm": None, "adv": None,
                   "trib_total": num(r.get("Monto de tributos")), "mon": mon,
                   "reg_txt": {"PENDIENTE": "Pendiente de regularización", "EN TRAMITE": "Pendiente de regularización", "CONCLUIDA": "Concluida"}.get(norm(sol), sol),
                   "f_rf": fch(r.get("Fecha del reconocimiento físico")), "f_dil": fch(r.get("Fecha de conclusión")),
                   "tras_txt": txt(r.get("Traslado (expediente y fecha)")), "obs": txt(r.get("Observaciones"))}
        ncn = [{"ri": control["ri"], "ri_f": control["ri_f"], "peco": "", "amaz": txt(r.get("NCN")), "f": fch(r.get("Fecha de la NCN")),
                "total": num(r.get("Monto de la NCN (S/)")), "anulada": False}] if txt(r.get("NCN")) else []
        out["dam"][dam] = {"control": control, "ncn": ncn, "fuente": "Consulta del equipo a la intendencia de destino"}
    for r in filas("Series por ubicar"):
        fac = txt(r.get("Factura"))
        if fac and (txt(r.get("Resultado de la búsqueda")) or txt(r.get("DAM encontrada"))):
            out["series"]["01-" + fac] = {"resultado": txt(r.get("Resultado de la búsqueda")) or "DAM encontrada", "dam": txt(r.get("DAM encontrada")),
                                          "serie": txt(r.get("Serie de la DAM")), "intendencia": txt(r.get("Intendencia de destino")),
                                          "modalidad": txt(r.get("Modalidad")), "estado": txt(r.get("Estado de la solicitud")), "obs": txt(r.get("Observaciones"))}
    for r in filas("DAM 2024 de traslados"):
        exp_ = txt(r.get("Traslado"))
        out["pin_filas"][exp_] += 1
        if txt(r.get("PIN o serie de la máquina en la DAM")):
            out["pin"].append({"exp": exp_, "dam": txt(r.get("DAM")), "serie": txt(r.get("Serie de la DAM")),
                               "pin": txt(r.get("PIN o serie de la máquina en la DAM")), "motor": txt(r.get("Serie del motor en la DAM"))})
    return out


# ---------------------------------------------------------------- domicilio fiscal y actividad

def ruc_valido(ruc):
    """RUC peruano: prefijo 10, 15, 16, 17 o 20 y dígito verificador (módulo 11)."""
    if not re.fullmatch(r"(10|15|16|17|20)\d{9}", ruc or ""):
        return False
    dv = 11 - sum(p * int(d) for p, d in zip((5, 4, 3, 2, 7, 6, 5, 4, 3, 2), ruc)) % 11
    return {10: 0, 11: 1}.get(dv, dv) == int(ruc[10])


def leer_transportistas(ruta):
    """Lista simple de transportistas vigilados: un RUC por línea, opcionalmente seguido del nombre
    (separado por espacio, coma, punto y coma, barra vertical, tabulación o guion). Se ignoran las
    líneas vacías, los comentarios (#), los RUC repetidos y los no válidos (se avisa el número de línea)."""
    if not ruta:
        return []
    texto = None
    for cod in ("utf-8-sig", "latin-1"):
        try:
            with open(ruta, encoding=cod) as f:
                texto = f.read()
            break
        except UnicodeDecodeError:
            continue
    out, vistos = [], set()
    for i, ln in enumerate((texto or "").splitlines(), 1):
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        m = re.match(r"^(?:RUC\W*)?(\d{11})(?:\s*[;,|\t-]\s*|\s+|$)(.*)$", ln, re.I)
        if not m or not ruc_valido(m.group(1)):
            print(f"AVISO transportistas: línea {i} ignorada (no empieza con un RUC válido de 11 dígitos)")
            continue
        if m.group(1) in vistos:
            continue
        vistos.add(m.group(1))
        out.append({"ruc": m.group(1), "nombre": m.group(2).strip().strip('"').strip()})
    return out


def leer_consulta_ruc(rutas):
    """Resultados de la consulta múltiple de RUC de SUNAT (ZIP o TXT separados por «|»)."""
    partes = []
    for r in rutas or []:
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


# ---------------------------------------------------------------- tablero

def main(a):
    mt = leer_dams(a.dams)
    m = mt[mt.COD_REGIMEN == "10"].copy()        # importación para el consumo
    dep70 = mt[mt.COD_REGIMEN == "70"].copy()    # depósito aduanero: solo para la historia de la máquina
    exp40 = mt[mt.COD_REGIMEN == "40"].copy()    # exportación definitiva
    e = leer_cpe(a.cpe)
    dl = leer_detalle(a.detalle)
    ruc_imp = str(m.NUM_DOCIDENT.iloc[0]).strip()
    desde = min(m.f.min(), e.f.min()).normalize()
    k8 = lambda x: x[-8:] if isinstance(x, str) and len(x) >= 8 else ""
    dia = pd.Timedelta(days=1)

    # ---------- DAM y máquinas importadas ----------
    dec = m.groupby("dam").agg(f=("f", "first"), ad=("COD_ADUANA", "first"), dest=("dest", "first"), canal=("CANAL", "first"),
                               series=("NUM_SECSERIE", "size"), cif=("MTO_VALORADU", "sum"), nmaq=("maq", "sum"),
                               conv=("conv", lambda s: ", ".join(sorted(set(s))))).reset_index()
    mq = datos_maquina(m[m.maq])
    mq["s"] = mq.NUM_SECSERIE.astype(int)
    mq = mq.sort_values(["f", "dam", "s"])
    mq["key"] = mq.dam + "#" + mq.s.astype(str)
    mq["k8"] = mq.id.map(k8)
    dep_k8 = {}
    if len(dep70):
        for _, s in datos_maquina(dep70[dep70.maq]).sort_values("f").iterrows():
            if k8(s.id) and k8(s.id) not in dep_k8:
                dep_k8[k8(s.id)] = {"dam": s.dam, "f": fstr(s.f)}
    exportaciones = []
    if len(exp40):
        x40 = exp40.drop_duplicates(["dam", "DES_COMER"]).copy()
        x40["pin"] = x40.DES_COMER.str.extract(r"PIN[: ]*([A-Z0-9]{17})", expand=False).fillna("")
        x40["motor_x"] = x40.DES_COMER.str.extract(r"MOTOR[: ]*([A-Z0-9]{8,12})", expand=False).fillna("")
        x40["modelo_x"] = x40.DES_COMER.str.extract(r"MOD[.:]*\s*([A-Z0-9.]+?)(?:PIN|\s|,|$)", expand=False).fillna("")
        for _, s in x40.sort_values("f").iterrows():
            exportaciones.append({"dam": s.dam, "f": fstr(s.f), "ad": s.COD_ADUANA, "desc": norm(s.DES_COMER)[:80], "modelo": s.modelo_x,
                                  "pin": s.pin, "motor": s.motor_x, "fob": r2(s.MTO_FOBDOL), "maq": None, "venta": None})
    exp_k8 = {k8(x["pin"]): x for x in exportaciones if k8(x["pin"])}

    # ---------- Control de la intendencia: DAM, NCN y traslados ----------
    ctl, tras_todos, meta_ctl = leer_control_ia(a.control_ia, ruc_imp) if a.control_ia else ({}, [], {"art2": [], "complejidad": None})
    cons = leer_consultas(a.consultas) if a.consultas else {"dam": {}, "series": {}, "pin": [], "pin_filas": Counter()}
    for k, x in cons["dam"].items():
        if "control" not in ctl.get(k, {}):
            ctl[k] = x
    dams_periodo = set(dec.dam)
    tr = [t for t in tras_todos if t["f"] >= fstr(desde) or set(t["dams"]) & dams_periodo]
    claves_maq = set(mq.key)
    cif_key = dict(zip(mq.key, mq.MTO_VALORADU))
    cat_key = dict(zip(mq.key, mq["cat"]))
    tras_maq, tras_dam = {}, {}
    for i, t in enumerate(tr):
        t["i"] = i
        t["salida"] = norm(t["tipo"]) == "ZTE A ZTC"           # «ZTE a ZTE pasando por ZTC» es tránsito, no salida
        t["pago"] = "garantizado" if "FIANZA" in norm(t["doc"]) else "pagado"
        t["maqs"] = [f"{d}#{s}" for d, s in t["pares"] if f"{d}#{s}" in claves_maq]
        t["es_maq"] = bool(t["maqs"]) or bool(re.search(r"MAQUINARIA|MOTOR", norm(t["merc"])))
        t["obs"] = []
        for k in t["maqs"]:
            tras_maq.setdefault(k, []).append(i)
        for d in t["dams"]:
            tras_dam.setdefault(d, []).append(i)
    # Monto del traslado = 18 % del valor en aduana de la serie, en soles: sirve para detectar series mal registradas
    ratios = {t["i"]: t["monto"] / (cif_key[t["maqs"][0]] * TASA_IMP) for t in tr
              if t["monto"] and len(t["maqs"]) == 1 and t["cant"] == 1 and "LIQUIDACION" in norm(t["doc"]) and t["salida"]}
    tc = float(pd.Series(list(ratios.values())).median()) if len(ratios) >= 3 else None
    for t in tr:
        r = ratios.get(t["i"])
        if tc and r and abs(r / tc - 1) > 0.10:
            t["obs"].append(f"El monto (S/ {t['monto']:,.0f}) no cuadra con el 18 % del CIF de la serie registrada (unos S/ {cif_key[t['maqs'][0]] * TASA_IMP * tc:,.0f})")
    por_par = {}
    for t in tr:
        for k in t["maqs"]:
            por_par.setdefault(k, []).append(t["exp"])
    for t in tr:
        otros = sorted({x for k in t["maqs"] for x in por_par[k] if x != t["exp"]})
        if otros:
            t["obs"].append(f"Misma DAM y serie que el expediente {', '.join(x.split('-')[-1] for x in otros)}")
    # Expedientes repetidos (misma DAM, serie y RI): cuenta uno solo, el que cuadra con el 18 % del CIF
    grupos = {}
    for t in tr:
        if t["maqs"]:
            grupos.setdefault((tuple(sorted(t["maqs"])), t["ri"]), []).append(t)
    for g_ in grupos.values():
        g_.sort(key=lambda t: abs(ratios.get(t["i"], tc or 1) / (tc or 1) - 1))
        for t in g_[1:]:
            t["dup"] = True
    tras_salida = [t for t in tr if t["es_maq"] and t["salida"] and t["f"] >= fstr(desde) and not t.get("dup")]
    cat_t = {t["i"]: ({cat_key[k] for k in t["maqs"]} or CAT_MERC.get(norm(t["merc"]), set())) for t in tr}

    def control_dam(k):
        x = ctl.get(k)
        if not x:
            return None
        c = x.get("control", {})
        pend = c["reg_txt"] == "Pendiente de regularización" if c.get("reg_txt") else norm(c.get("estado", "")) in PEND
        dg = norm(c.get("dilig", ""))
        ncn = [n for n in x.get("ncn", []) if not n["anulada"]]
        trib = {q: c.get(q) for q in ("igv", "ipm", "adv")}
        total = c.get("trib_total") or sum(v or 0 for v in trib.values())
        return {"tipo": c.get("tipo", ""), "mon": c.get("mon") or {"CANCELADA": "PEN", "GARANTIA 160": "USD"}.get(norm(c.get("tipo", "")), ""),
                "trib": {**trib, "total": r2(total) if total else None}, "fuente": x.get("fuente", ""),
                "tras_txt": c.get("tras_txt", ""), "obs": c.get("obs", ""),
                "reg": c.get("reg_txt") or ("Sin registro de diligencia" if not c else "Pendiente de regularización" if pend else "Concluida"),
                "res": "" if pend or not c else "No conforme" if dg.startswith("NO CONFORME") else "Conforme" if dg.startswith("CONFORME") else "",
                "fin": "" if pend else c.get("fin", ""), "ri": "" if pend else c.get("ri", ""), "ri_f": "" if pend else c.get("ri_f", ""),
                "f_rf": "" if pend else c.get("f_rf", ""), "f_dil": "" if pend else c.get("f_dil", ""),
                "ncn": [{"ri": n["ri"], "ri_f": n["ri_f"], "f": n["f"][:10], "total": r2(n["total"]), "ncn": n["amaz"] or n["peco"]} for n in ncn],
                "ncn_total": r2(sum(n["total"] or 0 for n in ncn)),
                "ris": [{"ri": r["ri"], "pdf": r["pdf"]} for r in x.get("ris", [])], "tras": tras_dam.get(k, [])}

    # ---------- Ventas de maquinaria y cadena de comprobantes ----------
    det_fp = dl[dl.num_serie_cpe.str.startswith("FP")].groupby("cpe").des_detalle_item.apply(
        lambda s: " + ".join(str(x).strip() for x in s if isinstance(x, str))).rename("desc")
    vm = e[e.linea == "Maquinaria"].merge(det_fp, left_on="cpe", right_index=True, how="left")
    vm["desc"] = vm.desc.fillna("").replace("", "(sin detalle)")
    vm["cat"] = vm.desc.map(cat_maquina)
    vm["usado"] = vm.desc.map(norm).str.contains(r"\bUSAD[OA]S?\b")
    facs = vm[vm.tipo == "01"]
    vig = facs[facs.estado == "0"]
    ncs = vm[(vm.tipo == "07") & (vm.estado == "0")]
    fx, facturas, xml_err, xml_rep = leer_facturas_xml(a.facturas_xml)
    por_cpe = vm.set_index("cpe")

    # Nota de crédito → factura que modifica: exacta con el XML de la NC; si no, por cliente, moneda y monto
    # (la factura anterior a la NC; la del mismo día solo si no hay otra, porque suele ser la reemisión)
    nc_ref, anulada_por = {}, {}
    for _, n in ncs.sort_values("f").iterrows():
        r = (facturas.get(n.cpe) or {}).get("ref")
        if r and f"01-{r['id']}" in por_cpe.index:
            nc_ref[n.cpe] = (f"01-{r['id']}", "XML de la nota de crédito")
        else:
            c = vig[(vig.doc == n.doc) & (vig.moneda == n.moneda) & (vig.f <= n.f) & ((n.f - vig.f).dt.days <= 365)
                    & ((vig.vv - n.vv).abs() <= (vig.vv * 0.005).clip(lower=1)) & ~vig.cpe.isin(list(anulada_por))]
            antes = c[c.f < n.f]
            c = antes if len(antes) else c
            if len(c):
                nc_ref[n.cpe] = (c.sort_values("f").cpe.iloc[-1], "mismo cliente, moneda y monto")
        if n.cpe in nc_ref and n.tipo_ref in NC_ANULA:
            anulada_por[nc_ref[n.cpe][0]] = n.cpe
    # Anticipos: la factura final descuenta lo ya facturado (valor + IGV − total). Una máquina, no dos.
    anticipo_de, anticipos = {}, {}
    vivas = vig[~vig.cpe.isin(list(anulada_por))]
    for _, fz in vivas[(vivas.vv + vivas.igv - vivas.total) > 1].sort_values("f").iterrows():
        dsc = fz.vv + fz.igv - fz.total
        c = vivas[(vivas.doc == fz.doc) & (vivas.moneda == fz.moneda) & (vivas.f <= fz.f) & (vivas.cpe != fz.cpe)
                  & ((fz.f - vivas.f).dt.days <= 365) & (vivas.vv <= dsc + 1) & ~vivas.cpe.isin(list(anticipo_de))].sort_values("f").tail(12)
        elegidas = None
        for n_ in (1, 2, 3):
            elegidas = next((g for g in combinations(c.itertuples(), n_) if abs(sum(x.vv for x in g) - dsc) <= 1), None)
            if elegidas:
                break
        if elegidas:
            anticipos[fz.cpe] = [x.cpe for x in elegidas]
            for x in elegidas:
                anticipo_de[x.cpe] = fz.cpe
    usadas = set()

    def reemision(o, f0, f1, mismo=True):
        c = vig[(vig.moneda == o.moneda) & (vig.cpe != o.name) & (vig.f >= f0) & (vig.f <= f1) & ~vig.cpe.isin(list(usadas))]
        c = c[(c.doc == o.doc)] if mismo else c[(c.doc != o.doc)]
        c = c[((c.vv - o.vv).abs() <= (0.10 if mismo else 0.02) * o.vv) & ((c["cat"] == o["cat"]) | (c["cat"] == "Otros") | (o["cat"] == "Otros"))]
        if not len(c):
            return None
        return c.assign(_d=(c.vv - o.vv).abs(), _t=(c.f - o.f).abs()).sort_values(["_d", "_t"]).iloc[0]
    cadenas = []
    anuladas = [(cpe, "Baja", None) for cpe in facs[facs.estado == "2"].sort_values("f").cpe] + \
               [(cpe, "Nota de crédito", nc) for cpe, nc in sorted(anulada_por.items(), key=lambda x: por_cpe.loc[x[1]].f)]
    for cpe, via, nc in anuladas:
        o = por_cpe.loc[cpe]
        fn = por_cpe.loc[nc].f if nc else o.f
        r = reemision(o, max(o.f, fn - 15 * dia), fn + 30 * dia)
        otro = None
        if r is not None:
            usadas.add(r.cpe)
        else:
            otro = reemision(o, fn - 3 * dia, fn + 30 * dia, mismo=False)
        cambio = "" if r is None else "con→sin" if o.igv > 0 and r.igv == 0 else "sin→con" if o.igv == 0 and r.igv > 0 else ""
        cadenas.append({"orig": cpe, "orig_f": fstr(o.f), "orig_igv": r2(o.igv), "via": via, "nc": nc or "",
                        "nc_f": fstr(por_cpe.loc[nc].f) if nc else "", "mot": por_cpe.loc[nc].tipo_ref if nc else "",
                        "enlace": nc_ref[nc][1] if nc else "", "reem": r.cpe if r is not None else "", "reem_f": fstr(r.f) if r is not None else "",
                        "reem_igv": r2(r.igv) if r is not None else None, "cambio": cambio,
                        "dias": int((r.f - fn).days) if r is not None else None, "otro": otro.cpe if otro is not None else ""})
    previa = {c["reem"]: c for c in cadenas if c["reem"]}

    def cadena_de(cpe):
        pasos, vistos = [], set()
        while cpe in previa and cpe not in vistos:
            vistos.add(cpe)
            pasos.insert(0, previa[cpe])
            cpe = previa[cpe]["orig"]
        return pasos
    # Máquinas vendidas: facturas vigentes que no se anularon con NC ni son anticipos de otra factura
    vend = vig[~vig.cpe.isin(list(anulada_por)) & ~vig.cpe.isin(list(anticipo_de))]

    # ---------- Domicilio fiscal y actividad de los compradores ----------
    dom = cargar_domicilios(a.domicilios, a.ubigeos, a.consulta_ruc) if a.domicilios else None
    info = dom.to_dict("index") if dom is not None else {}
    CAMPOS = ("zona", "departamento", "provincia", "distrito", "eruc", "condicion", "direccion", "actividad", "finsc")

    def domicilio(doc, tcli):
        if tcli == "No domiciliado":
            return {c: "" for c in CAMPOS} | {"zona": "Extranjero"}
        r = info.get(doc) or {}
        d = {c: r.get(c, "") for c in CAMPOS}
        d["zona"] = d["zona"] or "Sin dato"
        d["lugar"] = ", ".join(x for x in (d["distrito"], d["provincia"], d["departamento"]) if x)
        return d
    compradores = vend.groupby("doc").agg(nombre=("nombre", lambda s: s.value_counts().index[0]), tcli=("tcli", "first"),
                                          n=("cpe", "size"), primera=("f", "min"), ult=("f", "max")).reset_index()
    cli = {}
    for _, c in compradores.iterrows():
        d = domicilio(c.doc, c.tcli)
        dias_insc = (c.primera - pd.Timestamp(d["finsc"])).days if d["finsc"] else None
        cli[c.doc] = {"ruc": c.doc, "nombre": c.nombre, "tipo": c.tcli, **{k: d.get(k, "") for k in ("zona", "lugar", "direccion", "eruc", "condicion", "actividad", "finsc")},
                      "dep": d.get("departamento", "") or {"Extranjero": "Extranjero"}.get(d["zona"], "Sin dato"),
                      "rev": bool(REVENDE.search(norm(d["actividad"]))), "dias_insc": dias_insc,
                      "nuevo": dias_insc is not None and 0 <= dias_insc <= 180,
                      "no_habido": bool((d["eruc"] and d["eruc"] != "ACTIVO") or (d["condicion"] and d["condicion"] != "HABIDO")),
                      "n": int(c.n), "primera": fstr(c.primera), "ult": fstr(c.ult)}
    zona_doc = {k: v["zona"] for k, v in cli.items()}

    # ---------- Venta → máquina por número de serie (XML de la factura o caso documentado) ----------
    seriales = {}
    for _, it in fx[fx.serie != ""].iterrows():
        seriales.setdefault(it.cpe, []).append({"serie": it.serie, "motor": it.motor, "modelo": it.modelo, "anio": it.anio,
                                                "horas": it.horas, "afect": it.afect, "fuente": "XML de la factura"})
    manual = pd.read_csv(a.trazabilidad, dtype=str).fillna("") if a.trazabilidad else pd.DataFrame()
    entrega = {}
    if len(manual):
        buscar = ubicador(a.ubigeos)
        for _, c in manual.iterrows():
            if c.get("serie_maquina") and c.cpe not in seriales:
                seriales[c.cpe] = [{"serie": c.serie_maquina, "motor": c.get("serie_motor", ""), "modelo": c.get("modelo", ""), "anio": "",
                                    "horas": "", "afect": "", "fuente": c.get("fuente", "") or "Caso documentado"}]
            p = [x.strip() for x in str(c.get("ubicacion_entrega", "")).split(",")]
            ub = buscar(p[2], p[1], p[0]) if len(p) == 3 else None
            if c.get("ubicacion_entrega"):
                entrega[c.cpe] = {"lugar": c.ubicacion_entrega, "dir": c.get("direccion_entrega", ""), "zona": ub.zona if ub is not None else "Sin dato",
                                  "fuente": c.get("fuente", ""), "nota": c.get("nota", "")}
    buscar_u = ubicador(a.ubigeos)
    lugar_fac = {}
    for cpe, d_ in facturas.items():
        p_ = [x.strip() for x in d_["cliente"].get("lugar_fac", "").split("-")]
        if len(p_) >= 3 and all(p_[-2:]) and p_[0]:
            dist = "-".join(p_[:-2])
            ub = buscar_u(p_[-1], p_[-2], dist)
            lugar_fac[cpe] = {"lugar": f"{dist}, {p_[-2]}, {p_[-1]}" if ub is not None else ", ".join(x.strip(" .") for x in p_ if x.strip(" .")),
                              "zona": ub.zona if ub is not None else "Sin dato"}
    sedes = {}
    for d_ in facturas.values():
        if d_["emisor"].get("sede"):
            sedes.setdefault(d_["id"].split("-")[0], Counter())[d_["emisor"]["sede"]] += 1
    sede_de = {k: v.most_common(1)[0][0] for k, v in sedes.items()}
    lugar_sede = lambda x: (", ".join(y.strip().title() for y in x.split(" - ")[-2:]) if " - " in x else x).replace(" De ", " de ")
    venta_maq, maq_venta = {}, {}
    for cpe, lista in seriales.items():
        for s in lista:
            x = mq[mq.id.str.endswith(s["serie"])] if len(s["serie"]) >= 5 else mq.iloc[0:0]
            if not len(x) and len(s["motor"]) >= 5:
                x = mq[mq.motor == s["motor"]]
            s["maq"] = x.key.iloc[0] if len(x) else None
            if s["maq"]:
                venta_maq.setdefault(cpe, []).append(s["maq"])
                maq_venta.setdefault(s["maq"], []).append(cpe)

    # ---------- Exportación de lo vendido a no domiciliados ----------
    exp_venta = {}
    for _, s in vend[vend.tdoc == "0"].sort_values("f").iterrows():
        cand = [x for x in exportaciones if not x["venta"] and 0 <= (pd.Timestamp(x["f"]) - s.f).days <= 90]
        if cand:
            cand[0]["venta"] = s.cpe
            exp_venta[s.cpe] = cand[0]

    # ---------- Traslados de maquinaria → venta probable (por tipo de máquina y fecha) ----------
    # Cada traslado se asigna a tantas ventas como máquinas traslada; cada venta, a un solo traslado.
    # Prioridad: venta exportada (no domiciliado con DAM de exportación), luego la más cercana en días.
    prob_venta, candidatos = {}, []
    for t in tr:
        t["venta"] = sorted({c for k in t["maqs"] for c in maq_venta.get(k, [])})   # venta de su máquina por número de serie
    resueltos = {t["i"] for t in tras_salida if t["venta"]}
    for t in tras_salida:
        if t["i"] in resueltos:
            continue
        tf = pd.Timestamp(t["f"])
        libres = vend[~vend.cpe.isin(list(venta_maq))]
        for _, x in libres[libres["cat"].isin(cat_t[t["i"]]) & ((libres.f - tf).dt.days.abs() <= 30)].iterrows():
            z = zona_doc.get(x.doc, "")
            if z in ("ZTC", "Extranjero") or x.igv > 0:
                dias = int((x.f - tf).days)
                candidatos.append((abs(dias) - (100 if x.cpe in exp_venta else 0) - (5 if z == "ZTC" else 0), t["i"], x.cpe, dias))
    cupo = {t["i"]: max(1, len(t["maqs"]) or int(t["cant"] or 1)) for t in tras_salida}
    for t in tr:
        t["prob"] = []
    for _, i, cpe, dias in sorted(candidatos):
        if cupo[i] > 0 and cpe not in prob_venta:
            cupo[i] -= 1
            prob_venta[cpe] = i
            tr[i]["prob"].append({"cpe": cpe, "dias": dias})
    limpio = lambda x: re.sub(r"[^A-Z0-9]", "", norm(x))
    coincide = lambda a_, b_: bool(a_ and b_) and (a_.endswith(b_) or b_.endswith(a_) or (min(len(a_), len(b_)) >= 8 and a_[-8:] == b_[-8:]))
    tras_ext = {}
    for t in tras_salida:
        pins = [limpio(p["pin"]) for p in cons["pin"] if p["exp"] == t["exp"]]
        if not pins:
            continue
        hall = {p["cpe"] for p in t["prob"] if any(coincide(pin, limpio(s["serie"])) for pin in pins for s in seriales.get(p["cpe"], []))}
        completo = len(pins) >= cons["pin_filas"].get(t["exp"], 0)
        for p in list(t["prob"]):
            if p["cpe"] in hall or completo:
                t["prob"].remove(p)
                prob_venta.pop(p["cpe"], None)
        for cpe in hall:
            tras_ext[cpe] = t["i"]
        t["venta"] = sorted(set(t["venta"]) | hall)
        t["pin_ext"] = [p["pin"] for p in cons["pin"] if p["exp"] == t["exp"]]
    # Anulaciones y reemisiones que coinciden con un traslado de maquinaria a la ZTC: la venta probable del traslado
    # es parte de la cadena, o la NC o la reemisión caen a 7 días o menos del traslado (mismo tipo de máquina y con indicio de salida)
    for c in cadenas:
        o = por_cpe.loc[c["orig"]]
        salida_c = zona_doc.get(o.doc, "") in ("ZTC", "Extranjero") or (c["orig_igv"] or 0) > 0 or (c["reem_igv"] or 0) > 0
        fechas = [pd.Timestamp(x) for x in (c["nc_f"], c["reem_f"]) if x] or [pd.Timestamp(c["orig_f"])]
        c["tras"] = [t["i"] for t in tras_salida if prob_venta.get(c["reem"]) == t["i"] or prob_venta.get(c["orig"]) == t["i"]
                     or {c["orig"], c["reem"]} & set(t["venta"])
                     or (t["i"] not in resueltos and c["reem"] not in venta_maq and o["cat"] in cat_t[t["i"]] and salida_c
                         and any(abs((pd.Timestamp(t["f"]) - x).days) <= 7 for x in fechas))]
        s_o = {x["serie"] for x in seriales.get(c["orig"], [])}
        s_r = {x["serie"] for x in seriales.get(c["reem"], [])}
        c["misma_serie"] = ", ".join(sorted(s_o & s_r)) if s_o and s_r else ""
        c["otra_serie"] = bool(s_o and s_r and not s_o & s_r)

    ctl_cache = {k: control_dam(k) for k in set(mq.dam) | set(ctl) if k in dams_periodo}

    # ---------- Casos: una venta de maquinaria con indicios ----------
    conv_key = dict(zip(mq.key, mq.conv))
    TEXTO = {"ztc": "Comprador domiciliado fuera de la ZTE", "igv": "Vendida con IGV", "cambio": "Reemitida sin IGV tras anular la factura con IGV",
             "entrega": "Entregada fuera de la ZTE (según la factura)", "nodom": "Vendida a no domiciliado sin DAM de exportación",
             "exp": "Vendida a no domiciliado, con DAM de exportación", "nuevo": "Comprador con RUC reciente",
             "no_habido": "Comprador no habido o con RUC no activo", "anul_tras": "Anulación o reemisión el día de un traslado de maquinaria",
             "dom_ztc": "Al comprar figuraba en la ZTE; hoy está domiciliado fuera",
             "ncn_post": "Tributos devueltos con NCN después de la venta", "rf_post": "Reconocimiento físico conforme después de la venta"}
    casos = []
    for _, v in vend.sort_values("f").iterrows():
        c_ = cli.get(v.doc, {})
        z_hoy = c_.get("zona", "Sin dato")
        lug = lugar_fac.get(v.cpe)
        z = lug["zona"] if lug and lug["zona"] in ("ZTE", "ZTC") else z_hoy
        ch = cadena_de(v.cpe)
        ent = entrega.get(v.cpe)
        ex = exp_venta.get(v.cpe)
        mot = [k for k, ok in (
            ("ztc", z == "ZTC"), ("dom_ztc", z == "ZTE" and z_hoy == "ZTC"), ("igv", v.igv > 0), ("cambio", any(x["cambio"] == "con→sin" for x in ch)),
            ("entrega", bool(ent and ent["zona"] == "ZTC")), ("nodom", v.tdoc == "0" and not ex), ("exp", v.tdoc == "0" and bool(ex)),
            ("nuevo", bool(c_.get("nuevo")) and (v.f - pd.Timestamp(c_["finsc"])).days <= 180),
            ("no_habido", bool(c_.get("no_habido"))), ("anul_tras", any(x["tras"] for x in ch))) if ok]
        if not mot:
            continue
        maqs = venta_maq.get(v.cpe, [])
        t_conf = sorted({i for k in maqs for i in tras_maq.get(k, []) if tr[i]["salida"]} | ({tras_ext[v.cpe]} if v.cpe in tras_ext else set()))
        cd_m = [ctl_cache.get(k.split("#")[0]) for k in maqs]
        tras_inf = [cd["tras_txt"] for cd in cd_m if cd and cd.get("tras_txt") and norm(cd["tras_txt"]) not in SIN_TRASLADO]
        sin_tras_inf = bool(maqs) and all(cd and cd.get("fuente") and norm(cd.get("tras_txt", "")) in SIN_TRASLADO for cd in cd_m)
        ext = cons["series"].get(v.cpe) if not maqs else None
        t_trans = sorted({i for k in maqs for i in tras_maq.get(k, []) if not tr[i]["salida"]})
        sin_benef = bool(maqs) and all(conv_key[k] == "Sin beneficio" for k in maqs)
        t_prob = [] if maqs or v.cpe not in prob_venta else [prob_venta[v.cpe]]
        dests = sorted({k.split("#")[0] for k in maqs})
        dest_m = sorted({mq.loc[mq.key == k, "dest"].iloc[0] for k in maqs})
        salida = bool({"ztc", "igv", "cambio", "entrega", "nodom"} & set(mot))
        menor = v.vv < MENOR.get(v.moneda, 0) and not {"cambio", "nodom"} & set(mot)
        post = []
        if salida and not sin_benef:
            for k in maqs:
                cd = ctl_cache.get(k.split("#")[0])
                if not cd or cd["reg"] != "Concluida":
                    continue
                dias = lambda f: (pd.Timestamp(f) - v.f).days
                if cd["f_rf"] and dias(cd["f_rf"]) > 0:
                    post.append({"t": "rf", "f": cd["f_rf"], "dias": dias(cd["f_rf"]), "res": cd["res"]})
                if cd["f_dil"] and dias(cd["f_dil"]) > 0:
                    post.append({"t": "dil", "f": cd["f_dil"], "dias": dias(cd["f_dil"]), "res": cd["res"]})
                for n in cd["ncn"]:
                    if n["f"] and dias(n["f"]) > 0:
                        post.append({"t": "ncn", "f": n["f"], "dias": dias(n["f"]), "total": n["total"], "ncn": n["ncn"]})
        mot += [k for k, ok in (("ncn_post", any(p["t"] == "ncn" for p in post)), ("rf_post", any(p["t"] == "rf" for p in post))) if ok]
        if menor:
            continue
        xml = v.cpe in facturas
        if salida and sin_benef:
            nivel, estado = (("Baja", "Coherente: importada sin beneficio y vendida con IGV") if v.igv > 0 else
                             ("Media", "Importada sin beneficio: revisar el IGV de la venta") if z == "ZTC" else ("Baja", "Importada sin beneficio"))
        elif salida and (t_conf or tras_inf):
            nivel, estado = "Baja", "Regularizada: traslado autorizado" if t_conf else "Regularizada: traslado informado en la consulta"
        elif salida and maqs and (all(d == "271" for d in dest_m) or sin_tras_inf):
            nivel, estado = "Alta", ("Confirmada: tributos devueltos después de la venta" if "ncn_post" in mot else
                                     "Confirmada: reconocimiento físico después de la venta" if "rf_post" in mot else
                                     "Confirmada: solo tiene un traslado de tránsito" if t_trans else "Confirmada: sin traslado autorizado")
        elif salida and maqs:
            nivel, estado = "Alta", f"DAM con destino {', '.join(DESTINOS.get(d, d) for d in dest_m)}: verificar con esa intendencia"
        elif salida and t_prob:
            nivel, estado = "Media", "Traslado probable: confirmar la serie"
        elif salida and ext:
            r_ = norm(ext["resultado"])
            if r_.startswith(("IMPORTADA POR OTRO", "COMPRA LOCAL")):
                nivel, estado = "Media", f"Serie ubicada: {ext['resultado'].lower()} (sin beneficio de este importador)"
            elif r_.startswith("DAM ENCONTRADA") and norm(ext["modalidad"]).startswith("SIN DESGRAVACION"):
                nivel, estado = "Baja", "Coherente: importada sin beneficio (según la consulta)"
            elif r_.startswith("DAM ENCONTRADA"):
                nivel, estado = "Alta", f"DAM ubicada en la consulta: {ext['dam'] or 's/n'}" + (f" ({ext['intendencia']})" if ext["intendencia"] else "")
            else:
                nivel, estado = "Alta", "Serie no encontrada en la consulta"
        elif salida:
            nivel, estado = "Alta", ("Serie fuera de las DAM del periodo" if v.cpe in seriales else
                                     "El XML no indica la serie de la máquina" if v.cpe in facturas else "Por confirmar: falta el XML")
        elif {"nuevo", "no_habido", "anul_tras", "dom_ztc"} & set(mot):
            nivel, estado = "Media", ("Domicilio actual fuera de la ZTE: ubicar la máquina" if "dom_ztc" in mot else
                                      "Revisar al comprador" if not ch else "Revisar la cadena de comprobantes")
        else:
            nivel, estado = "Baja", ("Coherente: traslado y exportación, confirmados por serie" if t_conf and "exp" in mot else
                                     "Coherente: traslado y exportación" if t_prob else "Coherente: exportada" if "exp" in mot else "Seguimiento")
        casos.append({"cpe": v.cpe, "f": fstr(v.f), "ruc": v.doc, "cli": v.nombre, "nivel": nivel, "estado": estado, "mot": mot,
                      "motivo": " · ".join(TEXTO[k] for k in mot), "mon": v.moneda, "vv": r2(v.vv), "igv": r2(v.igv), "tot": r2(v.total),
                      "zona": z, "zona_hoy": z_hoy, "lugar_fac": lug["lugar"] if lug else "", "zona_fac": lug["zona"] if lug else "",
                      "sede": lugar_sede((facturas.get(v.cpe) or {}).get("emisor", {}).get("sede") or sede_de.get(v.serie, "")),
                      "desc": v.desc, "cat": v["cat"], "merc": MERCANCIA.get(v["cat"], "Otros"), "maqs": maqs, "dams": dests, "series": seriales.get(v.cpe, []),
                      "cadena": ch, "anticipos": anticipos.get(v.cpe, []), "tras": t_conf, "transito": t_trans, "dam_ext": ext, "post": post if nivel == "Alta" else [], "tras_prob": t_prob, "exp": ex["dam"] if ex else "", "entrega": ent, "xml": xml})

    # ---------- Indicadores de cada máquina y de cada caso ----------
    maquinas = []
    for _, s in mq.iterrows():
        c = ctl_cache.get(s.dam)
        ex = exp_k8.get(s.k8)
        if ex:
            ex["maq"] = s.key
        t_ = tras_maq.get(s.key, [])
        mk = [k for k, ok in (("usada", s.usada), ("dep", s.k8 in dep_k8), ("exp", bool(ex)),
                              ("tras", any(tr[i]["salida"] for i in t_)), ("pend", bool(c and c["reg"] == "Pendiente de regularización")),
                              ("dnc", bool(c and c["res"] == "No conforme")), ("ncn", bool(c and c["ncn"])),
                              ("venta", s.key in maq_venta)) if ok]
        maquinas.append({"k": s.key, "dam": s.dam, "s": int(s.s), "f": fstr(s.f), "dest": s.dest, "canal": s.CANAL, "conv": s.conv,
                         "cat": s["cat"], "merc": MERCANCIA.get(s["cat"], "Otros"), "marca": s.marca, "modelo": s.modelo, "anio": s.anio, "pin": s.id, "motor": s.motor,
                         "usada": bool(s.usada), "horas": s.horas, "cant": r2(s.CNT_COMER), "cif": r2(s.MTO_VALORADU), "hs": s.NUM_PARTNANDI,
                         "dep": dep_k8.get(s.k8), "exp": {"dam": ex["dam"], "f": ex["f"], "ad": ex["ad"]} if ex else None,
                         "tras": t_, "ventas": maq_venta.get(s.key, []), "mk": mk})
    maq_por_k = {x["k"]: x for x in maquinas}
    for c in casos:
        cl_ = cli.get(c["ruc"], {})
        mm = [maq_por_k[k] for k in c["maqs"]]
        cc = [ctl_cache.get(x["dam"]) for x in mm]
        c["mk"] = [k for k, ok in (
            ("igv", (c["igv"] or 0) > 0), ("ztc", c["zona"] == "ZTC"), ("zte", c["zona"] == "ZTE"), ("ext", c["zona"] == "Extranjero"),
            ("mudo", "dom_ztc" in c["mot"]),
            ("pub", cl_.get("tipo") == "Entidad pública"), ("pn", cl_.get("tipo") == "Persona natural"), ("rev", bool(cl_.get("rev"))),
            ("anul", bool(c["cadena"])), ("xml", c["xml"]), ("traza", bool(mm)), ("usada", any(x["usada"] for x in mm)),
            ("pend", any(x and x["reg"] == "Pendiente de regularización" for x in cc)), ("dnc", any(x and x["res"] == "No conforme" for x in cc)),
            ("ncn", any(x and x["ncn"] for x in cc)), ("post", any(p["t"] in ("rf", "ncn") for p in c["post"])), ("tras", bool(c["tras"])), ("trasp", bool(c["tras_prob"])), ("exp", bool(c["exp"]))) if ok]
        acc = []
        if not c["xml"] and not c["series"]:
            acc.append("Descargar el XML de la factura del portal del emisor para obtener la serie de la máquina y del motor.")
        elif not c["series"]:
            acc.append("El XML no trae la serie de la máquina: pedirla al emisor (guía de remisión, acta de entrega o ficha técnica).")
        elif not mm:
            s0 = c["series"][0]
            t0 = tr[c["tras_prob"][0]] if c["tras_prob"] else None
            acc.append(f"Buscar la DAM por la serie {s0.get('serie') or 's/d'} y el motor {s0.get('motor') or 's/d'}: no está entre las DAM del importador "
                       f"del periodo (importada antes o comprada en el país)."
                       + (f" Compárela con la DAM {', '.join(t0['dams'])} del traslado {t0['exp']}." if t0 else ""))
        if "dom_ztc" in c["mot"]:
            acc.append(f"Al comprar figuraba en {c['lugar_fac']} (según la factura) y hoy su domicilio fiscal está en {cl_.get('lugar') or 'la ZTC'}: "
                       "ubicar la máquina (visita, guías de remisión o información de terceros).")
        if c["estado"].startswith("Importada sin beneficio"):
            acc.append(f"La máquina se importó sin beneficio (DAM {', '.join(x['dam'] for x in mm)}): no hay tributos aduaneros por regularizar. "
                       "La venta sin IGV a un comprador de fuera de la ZTE es materia de tributos internos.")
        for p in c["post"]:
            if p["t"] == "ncn":
                acc.insert(0, f"Evaluar dejar sin efecto la NCN {p['ncn']} por S/ {p['total']:,.0f}: se emitió {p['dias']} días después de vender la máquina "
                              "a un comprador de fuera de la ZTE.")
            elif p["t"] == "rf":
                acc.insert(0, f"Revisar el acta del reconocimiento físico del {p['f'][8:10]}/{p['f'][5:7]}/{p['f'][:4]}: la máquina ya se había vendido "
                              f"a un comprador de fuera de la ZTE {p['dias']} días antes.")
        for i in c.get("transito", []):
            acc.append(f"La máquina tiene el traslado {tr[i]['exp']} de tránsito (ZTE a ZTE pasando por la ZTC), pero se vendió a un comprador "
                       "de fuera de la ZTE: verificar su destino final.")
        for x, k in zip(mm, cc):
            if c["nivel"] == "Alta" and x["dest"] == "271" and not c.get("transito"):
                acc.append(f"Requerir el sustento de la salida de la ZTE de la máquina {x['pin'] or x['k']} (DAM {x['dam']} serie {x['s']}): no tiene traslado "
                           f"autorizado. Tributos estimados de la serie: USD {x['cif'] * TASA_IMP:,.0f} (18 % del CIF).")
            elif c["nivel"] == "Alta":
                acc.append(f"La DAM {x['dam']} tiene destino {DESTINOS.get(x['dest'], x['dest'])}: consultar en el sistema su control en destino y "
                           "sus traslados (está en el Excel de consultas a otras intendencias, en Resumen).")
        if "cambio" in c["mot"]:
            x = next(p for p in c["cadena"] if p["cambio"] == "con→sin")
            acc.append(f"Pedir el sustento de la {'baja' if x['via'] == 'Baja' else 'nota de crédito ' + x['nc']} de {x['orig']} (con IGV) y de su reemisión sin IGV.")
        if {"ztc", "entrega"} & set(c["mot"]):
            acc.append("Verificar dónde opera la máquina: visita, guías de remisión de la venta o información de terceros.")
        if c["tras_prob"]:
            acc.append("Confirmar con el XML si la máquina vendida es la del traslado probable (misma DAM y serie).")
        if "nuevo" in c["mot"] or "no_habido" in c["mot"]:
            acc.append("Verificar la existencia y la actividad del comprador (RUC reciente o no habido).")
        c["acc"] = acc
    orden = {"Alta": 0, "Media": 1, "Baja": 2}
    prio_estado = lambda s: (0 if s.startswith("Confirmada: tributos") else 1 if s.startswith("Confirmada: reconocimiento") else
                             2 if s.startswith("Confirmada") else 3 if s.startswith("DAM con destino") else 4 if s.startswith("Serie")
                             else 5 if s.startswith("El XML") else 6)
    casos.sort(key=lambda c: (orden[c["nivel"]], prio_estado(c["estado"]), -(c["tot"] or 0) * (3.4 if c["mon"] == "USD" else 1)))

    # ---------- Clientes compradores de maquinaria ----------
    for doc, c in cli.items():
        mios = vend[vend.doc == doc]
        cs = [x for x in casos if x["ruc"] == doc]
        c.update({"usd": r2(mios[mios.moneda == "USD"].vv.sum()), "pen": r2(mios[mios.moneda == "PEN"].vv.sum()),
                  "n_igv": int((mios.igv > 0).sum()), "alta": sum(x["nivel"] == "Alta" for x in cs), "media": sum(x["nivel"] == "Media" for x in cs),
                  "cpes": mios.sort_values("f").cpe.tolist()})
    ventas = []
    caso_de = {c["cpe"]: c["nivel"] for c in casos}
    for _, s in vm.sort_values("f").iterrows():
        est = "Dada de baja" if s.estado == "2" else "Anulada por NC" if s.cpe in anulada_por else "Vigente"
        ventas.append({"cpe": s.cpe, "f": fstr(s.f), "ruc": s.doc, "cli": s.nombre, "desc": s.desc, "cat": s["cat"], "mon": s.moneda,
                       "vv": r2(s.vv), "igv": r2(s.igv), "tot": r2(s.total), "est": est, "mot": s.tipo_ref if s.tipo == "07" else "",
                       "ref": nc_ref.get(s.cpe, ("", ""))[0], "nc": anulada_por.get(s.cpe, ""), "nivel": caso_de.get(s.cpe, "")})

    # ---------- Patrones ----------
    fecha_txt = lambda x: f"{x[8:10]}/{x[5:7]}/{x[:4]}" if x else "s/f"
    pl = lambda n, uno, varios: f"{n} {uno if n == 1 else varios}"
    modelo_key = dict(zip(mq.key, mq.modelo))
    maq_modelo = lambda k: modelo_key.get(k, "")
    pat = []
    con_post = [c for c in casos if c["post"]]
    if con_post:
        it = []
        for c in con_post:
            ncn = [p for p in c["post"] if p["t"] == "ncn"]
            rf = [p for p in c["post"] if p["t"] == "rf"]
            lugar = cli.get(c["ruc"], {}).get("lugar", "")
            base = f"{c['cpe'][3:]}: vendida el {fecha_txt(c['f'])} a {c['cli'][:40].strip()}{' (' + lugar + ')' if lugar else ''}"
            if ncn:
                it.append(base + "; NCN " + ", ".join(f"{p['ncn']} por S/ {p['total']:,.0f} el {fecha_txt(p['f'])} ({p['dias']} días después)" for p in ncn))
            if rf:
                it.append(base + "; reconocimiento físico " + (rf[0]["res"].lower() or "") + f" el {fecha_txt(rf[0]['f'])} ({pl(rf[0]['dias'], 'día', 'días')} después)")
        n_dil = sum(1 for c in casos if c["estado"].startswith("Confirmada") and c["post"])
        n_conf = sum(1 for c in casos if c["estado"].startswith("Confirmada"))
        total_ncn = sum(p["total"] or 0 for c in con_post for p in c["post"] if p["t"] == "ncn")
        pat.append({"id": "post", "nivel": "Alta", "t": "Beneficio concluido después de vender la máquina fuera de la ZTE",
                    "items": it, "txt": f"En {n_dil} de {n_conf} ventas confirmadas por número de serie, la diligencia en destino se concluyó o la NCN se emitió después de la venta"
                                        + (f"; se devolvieron S/ {total_ncn:,.0f} con NCN emitidas después de vender" if total_ncn else "")
                                        + ". Revise cómo se verificó cada máquina y evalúe dejar sin efecto la conclusión, la liberación de la garantía o la NCN.",
                    "filtro": {"mk": "post"}})
    zt = vend[vend.doc.map(lambda d: zona_doc.get(d, "")) == "ZTC"]
    n_mudo = sum(1 for c in casos if "dom_ztc" in c["mot"])
    if len(zt):
        top = zt.groupby("doc").size().sort_values(ascending=False)
        pat.append({"id": "ztc", "nivel": "Alta", "t": "Ventas de maquinaria a compradores de fuera de la ZTE",
                    "txt": f"{len(zt)} ventas de maquinaria a {zt.doc.nunique()} compradores con domicilio fiscal actual en la ZTC"
                           + (f" ({n_mudo} figuraban en la ZTE en su factura)" if n_mudo else "") + f"; {int((zt.igv == 0).sum())} sin IGV "
                           f"(venta exonerada a quien no está en la zona) y {int((zt.igv > 0).sum())} con IGV. Concentración: "
                           + "; ".join(f"{cli[d]['nombre']} ({n})" for d, n in top.head(4).items()) + ".",
                    "filtro": {"mot": "ztc"}})
    alta_sal = [c for c in casos if {"ztc", "igv", "cambio", "entrega", "nodom"} & set(c["mot"]) and "sin beneficio" not in c["estado"]]
    n_sb = sum(1 for c in casos if "sin beneficio" in c["estado"])
    n_ts = len(tras_salida)
    if alta_sal:
        pat.append({"id": "tras", "nivel": "Alta", "t": "Pocos traslados para tantas ventas con indicios de salida",
                    "txt": f"{len(alta_sal)} ventas de maquinaria con indicios de salida de la ZTE"
                           + (f" (sin contar {n_sb} de máquinas importadas sin beneficio)" if n_sb else "")
                           + f" frente a {n_ts} traslados de maquinaria a la ZTC autorizados "
                           f"en el periodo ({sum(len(t['maqs']) or int(t['cant'] or 0) for t in tras_salida)} máquinas). "
                           f"{sum(c['nivel'] == 'Alta' for c in casos)} casos de nivel alto siguen sin un traslado que los respalde.",
                    "filtro": {"nivel": "Alta"}})
    if tras_salida:
        def maq_tras(t):
            return ", ".join(cat_key[k].lower() + " " + maq_modelo(k) for k in t["maqs"]) or \
                pl(int(t["cant"] or 1), "máquina", "máquinas") + " de " + t["merc"].lower()

        def venta_tras(t):
            if t["venta"]:
                return ", ".join(f"{x[3:]} {cli.get(por_cpe.loc[x].doc, {}).get('nombre', '')[:28].strip()} (por serie)" for x in t["venta"])
            return ", ".join(f"{p['cpe'][3:]} {cli.get(por_cpe.loc[p['cpe']].doc, {}).get('nombre', '')[:28].strip()} (probable, {p['dias']:+d} d)"
                             for p in t["prob"]) or "sin venta enlazada"
        pat.append({"id": "probables", "nivel": "Info", "t": "Cada traslado de maquinaria y su venta",
                    "items": [f"{t['exp'].split('-')[-1]} del {fecha_txt(t['f'])} ({maq_tras(t)}) → {venta_tras(t)}" for t in tras_salida],
                    "txt": "«Por serie»: la factura (XML) lleva la serie de la máquina del traslado. «Probable»: propuesta por tipo de máquina y fecha "
                           "(días de la venta respecto del traslado), por confirmar con el XML.",
                    "filtro": {"mk": "tras"}})
    sb = [c for c in casos if c["estado"].startswith(("Coherente: importada sin beneficio", "Importada sin beneficio"))]
    if sb:
        con_igv = [c for c in sb if (c["igv"] or 0) > 0]
        sin_igv = [c for c in sb if not (c["igv"] or 0) > 0]
        pat.append({"id": "sin_benef", "nivel": "Info", "t": "Máquinas importadas sin beneficio de la Amazonía",
                    "txt": f"{pl(len(sb), 'venta enlazada por serie corresponde', 'ventas enlazadas por serie corresponden')} a máquinas importadas sin destino amazónico "
                           f"(tributos pagados al importar): no hay riesgo aduanero de salida. {len(con_igv)} se vendieron con IGV (coherente)"
                           + (f"; {len(sin_igv)} se vendieron sin IGV a compradores de fuera de la ZTE ("
                              + ", ".join(sorted({c['cli'] for c in sin_igv})) + "): revisar el IGV de esas ventas (tributos internos)." if sin_igv else "."),
                    "filtro": {"estado": sin_igv[0]["estado"] if sin_igv else con_igv[0]["estado"]}})
    mudos = [c for c in casos if "dom_ztc" in c["mot"]]
    if mudos:
        por_cli = {}
        for c in mudos:
            por_cli.setdefault(c["ruc"], []).append(c)
        pat.append({"id": "mudos", "nivel": "Media", "t": "Compradores que figuraban en la ZTE al comprar y hoy están fuera",
                    "items": [f"{cs[0]['cli'][:40].strip()}: {pl(len(cs), 'venta', 'ventas')} ({', '.join(c['cpe'][3:] for c in cs)}) con domicilio en "
                              f"{', '.join(sorted({c['lugar_fac'] for c in cs}))} según la factura; hoy en {cli.get(k, {}).get('lugar', 'la ZTC')}"
                              + (f"; RUC inscrito el {fecha_txt(cli[k]['finsc'])}" if cli.get(k, {}).get("finsc", "") >= cs[0]["f"][:4] else "")
                              for k, cs in por_cli.items()],
                    "txt": "El domicilio del padrón es el de hoy; el de la factura, el del momento de la venta. Si el comprador se mudó, conviene ubicar la máquina.",
                    "filtro": {"mk": "mudo"}})
    exps = [c for c in casos if "exp" in c["mot"]]
    if exps or any("nodom" in c["mot"] for c in casos):
        pat.append({"id": "exp", "nivel": "Info", "t": "Ventas al exterior: flujo coherente",
                    "txt": f"{len(exps)} ventas de maquinaria a no domiciliados tienen DAM de exportación en los 90 días siguientes"
                           + (f"; {sum(1 for c in exps if c['tras_prob'] or c['tras'])} además con traslado a la ZTC autorizado días antes"
                              + (f" ({sum(1 for c in exps if c['tras'])} confirmados por la serie de la factura)" if any(c['tras'] for c in exps) else "")
                              if exps else "")
                           + (f". Sin exportación: {sum('nodom' in c['mot'] for c in casos)}." if any('nodom' in c['mot'] for c in casos) else ". Ninguna venta a no domiciliados quedó sin exportación."),
                    "filtro": {"mot": "exp"}})
    coinc = [c for c in cadenas if c["tras"]]
    if coinc:
        txts = []
        for c in coinc:
            ts = [tr[i] for i in c["tras"]]
            txts.append(f"{c['orig'][3:]} → {('NC ' + c['nc'][3:] + ' → ') if c['nc'] else 'baja → '}{c['reem'][3:] or 'sin reemisión'} "
                        f"({fecha_txt(c['nc_f'] or c['reem_f'])}): " + "; ".join(
                            f"traslado {t['exp'].split('-')[-1]} del {fecha_txt(t['f'])} ({', '.join(cat_key[k].lower() + ' ' + maq_modelo(k) for k in t['maqs']) or t['merc'].lower()})"
                            + (f", venta probable {', '.join(p['cpe'][3:] for p in t['prob'])}" if t["prob"] else "") for t in ts))
        pat.append({"id": "anul_tras", "nivel": "Media", "t": "Anulación cerca de un traslado de maquinaria",
                    "txt": "; ".join(txts) + ". Con los XML de estas facturas se confirma qué máquina recibió cada comprador.",
                    "filtro": {"mot": "anul_tras"}})
    bj = [c for c in cadenas if c["via"] == "Baja"]
    nc_a = [c for c in cadenas if c["via"] != "Baja"]
    con_sin = [c for c in cadenas if c["cambio"] == "con→sin"]
    nc_re = sum(1 for c in nc_a if c["reem"])
    nc_otro = sum(1 for c in nc_a if not c["reem"] and c["otro"])
    med_b = pd.Series([c["dias"] for c in bj if c["dias"] is not None])
    con_sin_txt = "; ".join(c["orig"][3:] + " → " + c["reem"][3:] + (", misma máquina " + c["misma_serie"] + " según los XML" if c["misma_serie"] else "")
                            for c in con_sin)
    pat.append({"id": "hipotesis", "nivel": "Info", "t": "Anulaciones de facturas de maquinaria: ¿ligadas al traslado?",
                "items": [f"{pl(len(bj), 'factura dada de baja', 'facturas dadas de baja')}: {sum(1 for c in bj if c['reem'])} reemitidas al mismo cliente por el mismo valor "
                          f"(mediana: {pl(int(med_b.median()) if len(med_b) else 0, 'día', 'días')}).",
                          f"{pl(len(nc_a), 'anulada con nota de crédito', 'anuladas con nota de crédito')}: {nc_re} reemitidas al mismo cliente, {nc_otro} vendidas a otro "
                          f"cliente por el mismo tipo y valor y {len(nc_a) - nc_re - nc_otro} sin reemisión (anticipos que se consolidan en otra factura o ventas canceladas).",
                          f"Pasaron de con IGV a sin IGV: {len(con_sin)}{' (' + con_sin_txt + ')' if con_sin else ''}.",
                          f"Coinciden con un traslado de maquinaria: {len(coinc)}{' (' + ', '.join((c['reem'] or c['orig'])[3:] for c in coinc) + ')' if coinc else ''}."],
                "txt": f"La mayoría son correcciones del comprobante: la hipótesis no se sostiene en general, pero merece revisión en "
                       f"{pl(len(set(c['reem'] or c['orig'] for c in con_sin + coinc)), 'caso puntual', 'casos puntuales')}.",
                "filtro": {"mk": "anul"}})
    if seriales:
        con_serie = [c for c in casos if c["series"] or c["maqs"]]
        CATEG = (("Confirmada", "Confirmadas sin traslado de salida (DAM con destino Tarapoto)"),
                 ("DAM con destino", "De DAM con destino a otra intendencia amazónica"),
                 ("Serie fuera", "Con una serie que no está en las DAM del importador del periodo"),
                 ("Traslado probable", "Con traslado probable por confirmar"),
                 ("Regularizada", "Regularizadas con traslado autorizado"),
                 ("Coherente: importada sin beneficio", "Importadas sin beneficio y vendidas con IGV (coherente)"),
                 ("Importada sin beneficio", "Importadas sin beneficio y vendidas sin IGV fuera de la ZTE"))
        cuenta = {}
        for c in con_serie:
            et = next((t for k, t in CATEG if c["estado"].startswith(k)), c["estado"])
            cuenta.setdefault(et, []).append(c["cpe"][3:])
        conf = [c for c in casos if c["estado"].startswith("Confirmada")]
        pat.append({"id": "serie", "nivel": "Alta" if conf else "Info", "t": "Trazabilidad por número de serie",
                    "items": [f"{k}: {len(cuenta[k])} ({', '.join(cuenta[k][:9])}{'…' if len(cuenta[k]) > 9 else ''})"
                              for k in [t for _, t in CATEG] + [x for x in cuenta if x not in [t for _, t in CATEG]] if k in cuenta],
                    "txt": f"{pl(len(facturas), 'XML leído', 'XML leídos')}; {len(venta_maq)} ventas enlazadas con su DAM por la serie de la máquina o del motor.",
                    "filtro": {"mk": "traza"}})
    pend_d = [k for k, c in ctl_cache.items() if c and c["reg"] == "Pendiente de regularización" and k in set(mq.dam)]
    if pend_d:
        mp = [x for x in maquinas if x["dam"] in set(pend_d)]
        pat.append({"id": "pend", "nivel": "Info", "t": "Máquinas en DAM pendientes de regularización",
                    "txt": f"{len(pend_d)} DAM con maquinaria siguen pendientes de regularización en el control de la IA ({len(mp)} series, "
                           f"CIF USD {sum(x['cif'] for x in mp):,.0f}). Si una de ellas se vendió fuera de la ZTE, el beneficio no debe concluirse.",
                    "maq": {"mk": "pend"}})
    dnc = [k for k, c in ctl_cache.items() if c and c["res"] == "No conforme" and k in set(mq.dam)]
    if dnc:
        pat.append({"id": "dnc", "nivel": "Media", "t": "Diligencias no conformes en maquinaria",
                    "txt": f"{len(dnc)} DAM con maquinaria tuvieron diligencia en destino no conforme: "
                           + "; ".join(f"{k} ({', '.join(sorted({x['cat'].lower() + ' ' + x['modelo'] for x in maquinas if x['dam'] == k}))})" for k in dnc) + ".",
                    "maq": {"mk": "dnc"}})

    # ---------- Calidad de los datos ----------
    ftxt = lambda x: fecha_txt(fstr(x))
    n_dif = sum(1 for k, l in lugar_fac.items() if l["zona"] in ("ZTE", "ZTC") and cli.get((facturas[k]["cliente"]["doc"]), {}).get("zona") in ("ZTE", "ZTC")
                and l["zona"] != cli[facturas[k]["cliente"]["doc"]]["zona"])
    con_dom = sum(1 for c in cli.values() if c["zona"] in ("ZTE", "ZTC"))
    n_menor = int(sum(1 for _, v in vend.iterrows() if v.vv < MENOR.get(v.moneda, 0)))
    pn_sd = sum(c["n"] for c in cli.values() if c["zona"] == "Sin dato" and c["tipo"] == "Persona natural")
    est_xml = {}
    for d in facturas.values():
        est_xml.setdefault(d["id"].split("-")[0], set()).add(d["emisor"]["est"])
    multi_est = {k: sorted(v) for k, v in est_xml.items() if len(v) > 1}
    g160 = [(k, c) for k, c in ctl_cache.items() if c and c["mon"] == "USD" and c["trib"]["igv"]]
    g160_ok = sum(1 for k, c in g160 if abs(c["trib"]["igv"] / dec.set_index("dam").cif.get(k, float("nan")) - 0.16) < 0.005)
    nc_inf = [c for c in cadenas if c["via"] != "Baja"]
    ncs_anula = ncs[ncs.tipo_ref.isin(NC_ANULA)]
    sin_271 = sorted({x["dam"] for x in maquinas if x["dest"] != "271"})
    obs_tras = []
    for g_ in grupos.values():
        if len(g_) > 1:
            k0 = g_[0]["maqs"][0]
            obs_tras.append(f"Expedientes {' y '.join(t['exp'].split('-')[-1] for t in g_)}: misma DAM y serie ({k0.replace('#', ', serie ')}) y misma RI "
                            f"{g_[0]['ri'].split('-SUNAT')[0]}" + "".join(f"; el monto de {t['exp'].split('-')[-1]} (S/ {t['monto']:,.0f}) no cuadra con el 18 % del CIF"
                                                                      for t in g_ if any(o.startswith('El monto') for o in t['obs'])) + ". Se cuenta uno solo")
    for t in tr:
        if not t.get("dup") and not any(t in g_ for g_ in grupos.values() if len(g_) > 1) and any(o.startswith("El monto") for o in t["obs"]):
            obs_tras.append(f"Expediente {t['exp'].split('-')[-1]}: {t['obs'][0].lower()}")
    calidad = {
        "confiable": [
            {"t": "DAM de importación", "d": f"{dec.dam.nunique():,} DAM y {len(m):,} series del régimen 10 ({ftxt(m.f.min())} a {ftxt(m.f.max())}); "
                                             f"{len(maquinas):,} series de maquinaria. Depósito ({dep70.dam.nunique()} DAM) y exportación ({exp40.dam.nunique()} DAM) solo para la historia de cada máquina."},
            {"t": "Comprobantes emitidos", "d": f"{len(e):,} CPE y {len(dl):,} ítems de detalle ({ftxt(e.f.min())} a {ftxt(e.f.max())}); {len(vm):,} de la serie de maquinaria."},
        ] + ([{"t": "Sede emisora", "d": "Según los XML, cada serie corresponde a una sede: " + "; ".join(f"{k} {lugar_sede(v)}" for k, v in sorted(sede_de.items())) + "."}]
             if sede_de else []) + ([{"t": "XML de los comprobantes", "d": f"{len(facturas)} comprobantes leídos (UBL 2.1): {pl(sum(d['tipo'] == '01' for d in facturas.values()), 'factura', 'facturas')}"
                                                       f" y {pl(sum(d['tipo'] == '07' for d in facturas.values()), 'nota de crédito', 'notas de crédito')}"
                                                       + (f"; {len(xml_rep)} archivos repetidos se leyeron una sola vez" if xml_rep else "")
                                                       + f". {len(venta_maq)} ventas enlazadas con su DAM por la serie."}] if facturas else [])
          + ([{"t": "Consultas del equipo", "d": f"Libro de consultas a otras intendencias: control de {len(cons['dam'])} DAM, "
                                                   f"{len(cons['series'])} series ubicadas y {len(cons['pin'])} PIN de DAM anteriores al periodo."}]
             if cons["dam"] or cons["series"] or cons["pin"] else [])
          + ([{"t": "Cuaderno de control de la IA", "d": f"{sum(1 for k in ctl if k in dams_periodo)} DAM del periodo, {sum(len([n for n in x.get('ncn', []) if not n['anulada']]) for k, x in ctl.items() if k in dams_periodo)} NCN, "
                                                          f"{len(tr)} expedientes de traslado y RI con su PDF."}] if ctl else [])
          + ([{"t": "Domicilio fiscal y actividad", "d": f"Padrón reducido del RUC{' al ' + fecha_txt(str(dom.fecha_padron.iloc[0])) if dom is not None and 'fecha_padron' in dom and len(dom) else ''} "
                                                          f"y consulta múltiple de RUC: {con_dom} de {len(cli)} compradores de maquinaria ubicados en la ZTE o la ZTC."}] if dom is not None else []),
        "limites": [
            {"t": "Domicilio a la fecha del padrón", "d": "Es el vigente hoy: puede diferir del que tenía el comprador al comprar y del lugar donde opera la máquina. "
                                                            f"Cuando hay XML se usa el distrito impreso en la factura: en {n_dif} de {len(lugar_fac)} facturas está en otra zona que el domicilio actual."},
            {"t": "Personas naturales sin domicilio", "d": f"La consulta pública no muestra su domicilio: {pn_sd} ventas de maquinaria a personas naturales quedan sin zona."},
            {"t": "Venta y máquina sin XML", "d": "Sin el XML solo se puede proponer un traslado probable por tipo de máquina y fecha; el enlace firme es por número de serie."},
        ] + ([{"t": "Factura que anula cada nota de crédito", "d": f"{len(nc_inf)} de {len(ncs_anula)} notas de crédito de anulación enlazadas con su factura"
                                                                     + (f" ({n_x} por su XML, el resto por cliente, moneda y monto)." if (n_x := sum(1 for c in nc_inf if c['enlace'].startswith('XML'))) else
                                                                        " por cliente, moneda y monto; con el XML de la nota de crédito el enlace es exacto.")}] if len(ncs_anula) else [])
          + ([{"t": "Anticipos", "d": f"{len(anticipo_de)} facturas de anticipo se unieron con la factura final que las descuenta: cuentan como una sola máquina."}] if anticipo_de else [])
          + ([{"t": "Comprobantes menores", "d": f"{n_menor} facturas de la serie de maquinaria por menos de USD {MENOR['USD']:,} o S/ {MENOR['PEN']:,} "
                                                  f"(accesorios, implementos o pagos parciales) no forman casos."}] if n_menor else [])
          + ([{"t": "Control solo de destino Tarapoto", "d": f"El cuaderno cubre las DAM con destino 271. {len(sin_271)} DAM con maquinaria tienen otro destino "
                                                              f"(sobre todo Pucallpa) y no tienen datos de control aquí."}] if ctl else [])
          + ([{"t": "Diligencias pendientes", "d": "Se muestran solo como «pendiente de regularización»: el estado y el plazo del reconocimiento físico suelen ser falta de registro."}] if ctl else [])
          + ([{"t": "Moneda de los tributos", "d": f"DAM canceladas en soles (confirmado). Garantía 160 en dólares: {g160_ok} de {len(g160)} DAM tienen un IGV igual al 16 % del CIF en USD."}] if g160 else [])
          + ([{"t": "Registros de traslado a revisar", "d": ". ".join(obs_tras) + "."}] if obs_tras else [])
          + ([{"t": "XML que no se pudieron leer", "d": f"{len(xml_err)}: {', '.join(xml_err[:10])}{' y otros' if len(xml_err) > 10 else ''}. Vuelva a descargarlos."}] if xml_err else []),
        "descartado": [
            {"t": "Sede inferida por el domicilio de los clientes", "d": "Se reemplazó por la sede que figura en los XML; se retiró la alerta de venta a otra circunscripción."},
            {"t": "Valoración y clasificación arancelaria", "d": "Valores unitarios atípicos y números de parte en varias subpartidas: no apuntan a la salida de la zona y daban muchos falsos positivos."},
            {"t": "Repuestos y servicios", "d": f"Con IGV ({int(((e.tipo == '01') & (e.estado == '0') & (e.igv > 0) & e.linea.isin(['Repuestos', 'Servicio técnico'])).sum()):,} facturas) o a no domiciliados: montos bajos y operación normal."},
            {"t": "Volumen de compras", "d": "Un cliente con 3 o más máquinas no es un indicio por sí solo; el número de máquinas queda como dato en Clientes."},
            {"t": "Maquinaria usada y diligencias pendientes como alertas", "d": "Pasan a ser indicadores de la máquina y de su DAM."},
            {"t": "Estadísticas generales", "d": "Canal de control, fletes, subpartidas, ventas de repuestos y servicios: no ayudan a seguir la máquina."},
        ],
    }

    # ---------- Comprobantes por descargar (XML) ----------
    # 1: casos de nivel alto sin XML; 2: traslados probables por confirmar; 3: comprobantes de cadenas ligadas a un traslado o a un cambio de IGV
    pendientes = []
    def pendiente(cpe, prio, por):
        if cpe and cpe not in facturas and not any(p["cpe"] == cpe for p in pendientes):
            s_ = por_cpe.loc[cpe]
            pendientes.append({"cpe": cpe, "f": fstr(s_.f), "tot": r2(s_.total), "mon": s_.moneda, "cli": s_.nombre, "prio": prio, "por": por})
    for c in casos:
        if c["nivel"] == "Alta":
            pendiente(c["cpe"], 1, "Caso de nivel alto")
    for c in casos:
        if c["estado"].startswith("Traslado probable"):
            pendiente(c["cpe"], 2, "Confirmar el traslado probable")
    for c in coinc + con_sin:
        for x in (c["orig"], c["nc"], c["reem"]):
            pendiente(x, 3, "Cadena de anulación ligada a un traslado o a un cambio de IGV")
    for c in casos:
        if c["tras_prob"] and c["nivel"] == "Baja":
            pendiente(c["cpe"], 3, "Opcional: confirmar por serie el traslado de una exportación")

    # ---------- Salida ----------
    dams = {}
    for k in sorted(set(mq.dam)):
        d = dec[dec.dam == k].iloc[0]
        dams[k] = {"f": fstr(d.f), "ad": d.ad, "dest": d.dest, "canal": d.canal, "conv": d.conv, "series": int(d.series), "nmaq": int(d.nmaq),
                   "cif": r2(d.cif), "ctl": ctl_cache.get(k), "maqs": mq[mq.dam == k].key.tolist()}
    vend_z = {z: int(sum(1 for d in vend.doc if zona_doc.get(d, "Sin dato") == z)) for z in ("ZTE", "ZTC", "Extranjero", "Sin dato")}
    datos = {
        "meta": {"contribuyente": m.NOM_RAZONSOCIAL.iloc[0], "ruc": ruc_imp, "desde": fstr(desde)[:7], "hasta": fstr(max(m.f.max(), e.f.max()))[:7],
                 "generado": date.today().isoformat(), "portal": a.portal or "", "dam_hasta": fstr(m.f.max()), "cpe_hasta": fstr(e.f.max()),
                 "aduanas": ADUANAS, "destinos": DESTINOS, "canales": CANALES, "motivos": MOTIVOS_NC, "texto": TEXTO,
                 "padron": str(dom.fecha_padron.iloc[0]) if dom is not None and "fecha_padron" in dom and len(dom) else "", "xml_err": xml_err},
        "kpi": {"maq_series": len(maquinas), "maq_uds": int(mq.CNT_COMER.sum()), "maq_cif": r2(mq.MTO_VALORADU.sum()), "maq_dams": int(mq.dam.nunique()),
                "por_dest": [{"cod": k, "series": int((mq.dest == k).sum()), "dams": int(mq[mq.dest == k].dam.nunique()),
                              "ctl": int(sum(1 for d in set(mq[mq.dest == k].dam) if ctl_cache.get(d)))} for k in mq.dest.value_counts().index],
                "vend": int(len(vend)), "vend_z": vend_z, "vend_igv": int((vend.igv > 0).sum()), "anuladas": len(anulada_por), "bajas": len(bj),
                "casos": {n: sum(c["nivel"] == n for c in casos) for n in ("Alta", "Media", "Baja")},
                "alta_sin_xml": sum(1 for c in casos if c["nivel"] == "Alta" and not c["xml"]),
                "tras_salida": n_ts, "tras_maq": sum(len(t["maqs"]) or int(t["cant"] or 0) for t in tras_salida),
                "pend_dams": len(pend_d), "pend_series": sum(1 for x in maquinas if x["dam"] in set(pend_d)),
                "ncn_total": r2(sum(c["ncn_total"] or 0 for c in ctl_cache.values() if c)),
                "ncn_dams": sum(1 for c in ctl_cache.values() if c and c["ncn"]), "tc": r2(tc)},
        "maquinas": maquinas, "dams": dams, "traslados": tr, "casos": casos, "ventas": ventas, "cadenas": cadenas,
        "clientes": cli, "facturas": facturas, "patrones": pat, "calidad": calidad, "pendientes": pendientes,
        "exportaciones": [x for x in exportaciones if x["maq"] or x["venta"]], "control": {"art2": meta_ctl.get("art2", []), "complejidad": meta_ctl.get("complejidad")},
        "transportistas": leer_transportistas(a.transportistas),
    }
    with open(a.salida, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))
    n = datos["kpi"]["casos"]
    print(f"OK {a.salida}: {len(casos)} casos (alta {n['Alta']}, media {n['Media']}, baja {n['Baja']}); {len(maquinas)} máquinas; "
          f"{len(cli)} compradores; {len(facturas)} XML; {len(pendientes)} comprobantes por descargar; "
          f"{len(datos['transportistas'])} transportistas vigilados")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for x in ("dams", "cpe", "detalle", "salida"):
        ap.add_argument(x)
    ap.add_argument("--domicilios")
    ap.add_argument("--ubigeos", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "referencias", "ubigeo_zte.csv"))
    ap.add_argument("--portal", help="URL del portal público de comprobantes del emisor (va cifrada dentro de los datos)")
    ap.add_argument("--consulta-ruc", nargs="*", default=[], help="Resultados de la consulta múltiple de RUC de SUNAT (ZIP o TXT)")
    ap.add_argument("--trazabilidad", help="CSV de casos: cpe, serie_maquina, serie_motor, modelo, ubicacion_entrega (DISTRITO, PROVINCIA, DEPARTAMENTO), direccion_entrega, fuente, nota")
    ap.add_argument("--facturas-xml", nargs="*", default=[], help="XML de comprobantes del emisor (archivos, carpetas o ZIP)")
    ap.add_argument("--consultas", help="Libro de consultas a otras intendencias completado por el equipo (ver consultas_xlsx.py)")
    ap.add_argument("--control-ia", help="Cuaderno de control de la intendencia (xlsx/xlsm): control en destino, NCN, RI y traslados")
    ap.add_argument("--transportistas", help="Transportistas vigilados (TXT: un RUC por línea, opcionalmente con el nombre); entran en la «Lista del día» de guías")
    main(ap.parse_args())
