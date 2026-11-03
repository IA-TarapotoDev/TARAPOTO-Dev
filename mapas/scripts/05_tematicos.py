# Asigna circunscripción aduanera (R.S. 000980 y modif.) y régimen tributario (Ley 27037) a cada distrito INEI
import geopandas as gpd, pandas as pd, warnings
warnings.filterwarnings("ignore")
B = "/home/user/data_base"
d = gpd.read_file(f"{B}/distritos_inei.gpkg")

def circ(r):
    dep, prov, dis = r.departamento, r.provincia, r.distrito
    if dep == "TUMBES" or (prov == "TALARA" and dis in ("MANCORA", "LOS ORGANOS")): return "IA TUMBES"
    if dep == "PIURA": return "IA PAITA"
    if dep == "CAJAMARCA":
        return "IA PAITA" if prov in ("SANTA CRUZ", "CHOTA", "CUTERVO", "SAN IGNACIO", "JAEN", "HUALGAYOC") else "IA SALAVERRY"
    if dep == "LAMBAYEQUE": return "IA CHICLAYO"
    if dep == "LA LIBERTAD": return "IA SALAVERRY"
    if dep == "ANCASH": return "IA CHIMBOTE"
    if (dep == "PASCO" and prov in ("PASCO", "DANIEL ALCIDES CARRION")) or \
       (dep == "LIMA" and prov in ("CAJATAMBO", "HUARAL", "OYON", "BARRANCA", "HUAURA")) or \
       (dep == "LIMA" and prov == "LIMA" and dis == "ANCON"): return "IA CHANCAY"
    if dep in ("LIMA", "CALLAO", "JUNIN", "PASCO"): return "IA MARÍTIMA DEL CALLAO"
    if dep in ("ICA", "AYACUCHO", "HUANCAVELICA"): return "IA PISCO"
    if dep == "AREQUIPA": return "IA MOLLENDO"
    if dep == "MOQUEGUA": return "IA ILO"
    if dep == "TACNA": return "IA TACNA"
    if dep == "PUNO": return "IA PUNO"
    if dep in ("CUSCO", "APURIMAC"): return "IA CUSCO"
    if dep == "MADRE DE DIOS": return "IA PUERTO MALDONADO"
    if dep in ("UCAYALI", "HUANUCO"): return "IA PUCALLPA"
    if dep in ("SAN MARTIN", "AMAZONAS"): return "IA TARAPOTO"
    if dep == "LORETO": return "IA TARAPOTO" if prov in ("ALTO AMAZONAS", "DATEM DEL MARAÑON") else "IA IQUITOS"
    return "?"

ZTE_DEP = {"LORETO", "MADRE DE DIOS", "UCAYALI", "AMAZONAS", "SAN MARTIN"}
# Ámbito según el anexo de SUNAT "Jurisdicción en la Ley de Promoción de la Amazonía – Ley N.° 27037, art. 3"
# (procedimiento RECA-PE.05.01); Cutervo se mantiene como ZTC por decisión del usuario.
ZTE_PROV = {("HUANUCO", "LEONCIO PRADO"), ("HUANUCO", "PUERTO INCA"), ("HUANUCO", "MARAÑON"), ("HUANUCO", "PACHITEA"),
            ("CAJAMARCA", "JAEN"), ("CAJAMARCA", "SAN IGNACIO"),
            ("PASCO", "OXAPAMPA"), ("JUNIN", "CHANCHAMAYO"), ("JUNIN", "SATIPO"), ("CUSCO", "LA CONVENCION")}
ZTE_DIS = {("HUAMALIES", "MONZON"), ("HUANCABAMBA", "EL CARMEN DE LA FRONTERA"), ("PATAZ", "ONGON"),
           ("HUANUCO", "HUANUCO"), ("HUANUCO", "AMARILIS"), ("HUANUCO", "PILLCO MARCA"), ("HUANUCO", "CHINCHAO"),
           ("HUANUCO", "CHURUBAMBA"), ("HUANUCO", "SANTA MARIA DEL VALLE"),
           ("AMBO", "AMBO"), ("AMBO", "CONCHAMARCA"), ("AMBO", "TOMAY KICHWA"),
           ("HUANTA", "SIVIA"), ("HUANTA", "AYAHUANCO"), ("LA MAR", "AYNA"), ("LA MAR", "SAN MIGUEL"), ("LA MAR", "SANTA ROSA"),
           ("TAYACAJA", "HUACHOCOLPA"), ("TAYACAJA", "TINTAY PUNCU"),
           ("CALCA", "YANATILE"), ("PAUCARTAMBO", "KOSÑIPATA"), ("QUISPICANCHI", "CAMANTI"), ("QUISPICANCHI", "MARCAPATA"),
           ("CARABAYA", "COASA"), ("CARABAYA", "AYAPATA"), ("CARABAYA", "ITUATA"), ("CARABAYA", "OLLACHEA"), ("CARABAYA", "SAN GABAN"),
           ("SANDIA", "SAN JUAN DEL ORO"), ("SANDIA", "LIMBANI"), ("SANDIA", "YANAHUAYA"), ("SANDIA", "PHARA"),
           ("SANDIA", "ALTO INAMBARI"), ("SANDIA", "SANDIA"), ("SANDIA", "PATAMBUCO")}
def reg(r):
    if r.departamento in ZTE_DEP or (r.departamento, r.provincia) in ZTE_PROV or (r.provincia, r.distrito) in ZTE_DIS: return "ZTE"
    return "ZTC"

d["circ"] = d.apply(circ, axis=1)
d["regimen"] = d.apply(reg, axis=1)
assert (d.circ != "?").all()
d.to_file(f"{B}/distritos_tematico.gpkg", driver="GPKG")
for col, out in [(["departamento", "provincia"], "provincias"), (["departamento"], "departamentos"),
                 (["circ"], "circunscripciones"), (["regimen"], "regimen")]:
    g = d.dissolve(by=col, as_index=False)[col + ["geometry"]]
    g["geometry"] = g.buffer(0)
    g.to_file(f"{B}/{out}.gpkg", driver="GPKG"); print(out, len(g))
peru = d.dissolve()[["geometry"]]; peru.to_file(f"{B}/peru.gpkg", driver="GPKG")
print(d[d.regimen == "ZTE"].groupby("departamento").size())
