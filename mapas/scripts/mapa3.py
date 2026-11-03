# MAPA 3 – Red fluvial del norte del Perú: salidas fluviales de la jurisdicción de la IA Tarapoto y del país (A0 horizontal, 1:1 250 000)
# Misma distribución que los mapas 1 y 2: el mapa ocupa todo el recuadro; relieve sólo en la circunscripción de la IA Tarapoto.
import sys, textwrap
sys.path.insert(0, "/home/user/mapas_scripts")
from mural import *
from carto import _key

OUT = sys.argv[1] if len(sys.argv) > 1 else "/home/user/TARAPOTO-Dev/mapas/Mapa3_Red_Fluvial_Norte_Peru"
DPI = int(sys.argv[2]) if len(sys.argv) > 2 else 300
MODE = sys.argv[3] if len(sys.argv) > 3 else "both"     # both | pdf | nopdf
SCALE = 1_250_000
M = Mural(SCALE, -230_000, 10_002_000, horizontal=True)     # de la costa de Tumbes a Santa Rosa; de la frontera norte a ~9° S
fr, fig, bg, ov, pn = M.fr, M.fig, M.bg, M.ov, M.pn
CB = fr.clipbox(0.05)
NARANJA = "#ef6c00"       # rutas fluviales de salida
ROJO = "#c62828"          # salida del país

# recuadros dentro del marco (x, y, ancho, alto en mm de página; lámina 1189 × 841 mm)
B_TIT = (20, 731, 300, 90)        # título (noroeste, sobre Ecuador)
B_UBI = (939, 636, 230, 185)      # ubicación (noreste, sobre Colombia)
B_LEY = (884, 20, 285, 207)       # leyenda (sureste, sobre Brasil)
CAJAS = (B_TIT, B_UBI, B_LEY)
M.reservar(*CAJAS)

# ------------------------------------------------ datos
circ = gpd.read_file(f"{U}/circunscripciones.gpkg"); peru = gpd.read_file(f"{U}/peru.gpkg"); dep = gpd.read_file(f"{U}/departamentos.gpkg")
pu = gpd.read_file(f"{U}/paises_ubicacion.gpkg"); vec = pu[pu.name != "Perú"]
peru_g = peru.geometry.iloc[0]; tara = circ[circ.circ == "IA TARAPOTO"].geometry.iloc[0]
ext = [g.difference(peru_g) for g in vec.geometry]; land = [peru_g] + ext
land_u = unary_union(land)
R = json.load(open("/home/user/data_base/rutas_fluviales.json"))
R["salidas_pais"] = [s_ for s_ in R["salidas_pais"] if fr.bbox.contains(Point(s_["x"], s_["y"]))]   # sólo las del norte
for s_ in R["salidas_pais"]:
    if "Amazonas" in s_["rio"]: s_["pais"] = "Colombia (Leticia) y Brasil (Tabatinga)"
RUTA_KM = next(r for r in R["rutas"] if r["origen"] == "Yurimaguas")     # kilometraje de referencia: desde Yurimaguas
def fkm(v, d=0):
    return f"{v:,.{d}f}".replace(",", " ").replace(".", ",")

# ------------------------------------------------ fondo: relieve en la IA Tarapoto; resto del Perú en blanco; países vecinos gris claro
FUERA = CB.intersection(land_u).difference(tara)
fr.relief(dem="/home/user/data_base/dem_m1_z12.tif", res=110, src_res=38, land=land, veil=[FUERA], veil_alpha=1.0, shade=(0.62, 0.44))
fr.polys([g.intersection(CB) for g in ext], fc=UBI["vecinos"], ec="none", z=1)
CL_PE = fr.clip_patch(peru_g.intersection(CB)); fr.ax.add_patch(CL_PE)
CL_EXT = fr.clip_patch(CB.difference(peru_g)); fr.ax.add_patch(CL_EXT)

# ------------------------------------------------ vías nacionales (contexto, muy atenuadas)
vias = fr.load("pf_vias")
fr.lines(list(vias.geometry), color="#ecbcbc", lw=0.55, z=2.2, clip=CL_PE)

# ------------------------------------------------ límites
fr.lines(list(dep.geometry.boundary), color="#a9a9a9", lw=0.7, ls=(0, (6, 2.5, 1.5, 2.5)), z=2.6)
cb = unary_union([g.boundary for g in circ.geometry]).difference(peru_g.boundary.buffer(1500))
fr.lines([cb], color=C["circ"], lw=1.4, ls=(0, (6, 3)), z=2.7, alpha=0.75)
tclip = fr.clip_patch(tara); fr.ax.add_patch(tclip)
fr.lines([tara.boundary], color=C["tarapoto"], lw=7, alpha=0.25, z=2.8, clip=tclip, cap="butt")
fr.lines([tara.boundary], color=C["tarapoto"], lw=2.2, z=6.4)
fr.lines(list(vec.geometry.boundary), color="#b9b6ad", lw=0.6, z=2.5)

# ------------------------------------------------ rutas fluviales de salida (banda bajo el río)
rutas = []
for r in R["rutas"]:
    ln = gpd.GeoSeries([LineString(r["coords"])], crs=4326).to_crs(32718).iloc[0]
    rutas.append((r, ln))
    fr.lines([ln], color=NARANJA, lw=9, alpha=0.38, z=2.95, cap="round")

# ------------------------------------------------ red fluvial
rios = fr.load("pf_rios"); agua = fr.load("pf_agua")
fr.polys(list(agua.geometry), fc=C["agua"], ec=C["agua_lin"], lw=0.2, z=3)
W = {"rio": (0.35, 0.75, "#7fb3dc"), "navegable": (1.2, 1, "#1e73be"), "hidrovia": (2.4, 1, "#1257b0")}
for i, cl in enumerate(["rio", "navegable", "hidrovia"]):
    g = list(rios[rios.clase == cl].geometry)
    lw, al, col = W[cl]
    if cl == "hidrovia":
        fr.lines(g, color="white", lw=lw + 1.6, z=3.15 + 0.1 * i, alpha=0.9)
    fr.lines(g, color=col, lw=lw, alpha=al, z=3.2 + 0.1 * i, clip=CL_PE)
    fr.lines(g, color="#9cc3e3" if cl != "rio" else "#b8d4ea", lw=lw * 0.8, alpha=al, z=3.2 + 0.1 * i, clip=CL_EXT)

# límite internacional (sobre los ríos fronterizos)
borde = peru_g.boundary.intersection(unary_union(list(vec.geometry)).buffer(5000))
fr.lines([borde], color="#d9534f", lw=6, alpha=0.25, z=6.5)
fr.lines([borde], color=C["frontera"], lw=1.9, ls=(0, (10, 2.5, 2, 2.5, 2, 2.5)), z=6.6)

# ------------------------------------------------ puertos fluviales, SUNAT y capitales
lug = gpd.read_file(f"{U}/pf_lugares.gpkg")
def buscar(nombre_, lon, lat, r=20000):
    p = Point(*TO_UTM.transform(lon, lat))
    c = lug[lug.distance(p) < r]
    c = c[[_key(nombre_) in _key(n) or _key(n) in _key(nombre_) for n in c.name]]
    return c.geometry.iloc[c.distance(p).argmin()] if len(c) else p
PUERTOS_IA = {"Yurimaguas": (-76.10, -5.90), "San Lorenzo": (-76.555, -4.832), "Saramiriza": (-77.4175, -4.564),
              "Santa María de Nieva": (-77.8667, -4.5938), "Puerto Galilea": (-77.7583, -4.0151), "Lagunas": (-75.68, -5.23),
              "Borja": (-77.546, -4.470), "Nuevo Andoas": (-76.4576, -2.8073)}
PUERTOS_PE = {"Iquitos": (-73.25, -3.75), "Pucallpa": (-74.55, -8.38), "Puerto Maldonado": (-69.19, -12.59), "Nauta": (-73.55, -4.51),
              "Requena": (-73.83, -5.06), "Contamana": (-75.01, -7.35), "Atalaya": (-73.77, -10.73), "Caballococha": (-70.51, -3.91),
              "Santa Rosa": (-69.96, -4.22), "Pebas": (-71.82, -3.32), "San Antonio del Estrecho": (-72.67, -2.45),
              "Cabo Pantoja": (-75.18, -0.97), "Puerto Esperanza": (-70.71, -9.77), "Puerto Inca": (-74.97, -9.38),
              "Intuto": (-74.73, -3.52), "Mazán": (-73.09, -3.50), "Islandia": (-69.92, -4.36)}
PRINC = {"Yurimaguas", "San Lorenzo", "Saramiriza", "Iquitos", "Pucallpa", "Puerto Maldonado"}
PXY = {n: buscar(n, *ll) for n, ll in {**PUERTOS_IA, **PUERTOS_PE}.items()}
PXY = {n: p for n, p in PXY.items() if fr.bbox.buffer(-3000).contains(p)}
for n, p in PXY.items():
    big = n in PRINC
    fr.ax.plot([p.x], [p.y], marker="o", ms=14 if big else 9.5, mfc="#0d47a1", mec="white", mew=1.3, zorder=28)
    fr.ax.text(p.x, p.y, "⚓", fontsize=8 if big else 5.6, color="white", ha="center", va="center", family="DejaVu Sans", zorder=28.5)
    fr.labels.obstacle(p.x, p.y, 2.8 if big else 2.0)
nav = unary_union(list(rios[rios.clase.isin(["navegable", "hidrovia"])].geometry))
sun = gpd.read_file(f"{U}/pf_puntos.gpkg")
sun = sun[(sun.clase == "sunat") & sun.geometry.within(peru_g) & sun.geometry.within(fr.bbox)]
sun = sun[sun.distance(nav) < 5000]
sun = sun[[min(p.distance(q) for q in PXY.values()) > 1500 or True for p in sun.geometry]]
fr.ax.plot(sun.geometry.x, sun.geometry.y, ls="none", marker="p", ms=7, mfc="#0d47a1", mec="white", mew=0.8, zorder=29)
for p in sun.geometry: fr.labels.obstacle(p.x, p.y, 1.6)
# capitales oficiales (INEI): de departamento; de provincia en la IA Tarapoto; de provincia o distrito junto a ríos navegables
capt = gpd.read_file(f"{U}/capitales.gpkg")
capt = capt[capt.geometry.within(fr.bbox.buffer(-3000)) & capt.geometry.within(peru_g)].copy()
capt = capt[[min(p.distance(q) for q in PXY.values()) > 5000 for p in capt.geometry]]
SEDE = Point(*TO_UTM.transform(-76.3592, -6.4863))
capt = capt[capt.distance(SEDE) > 4000]                  # Tarapoto se rotula con la sede de la IA
capt["txt"] = capt.nombre.map(nom_cap)
caps = capt[capt.nivel == 0]
rib = capt[(capt.nivel >= 1) & (capt.distance(nav) < 3000)]
prov_ia = capt[(capt.nivel == 1) & capt.in_ia & ~capt.index.isin(rib.index)]
fr.ax.plot(caps.geometry.x, caps.geometry.y, ls="none", marker="s", ms=8, mfc="white", mec="black", mew=1.5, zorder=27)
fr.ax.plot(prov_ia.geometry.x, prov_ia.geometry.y, ls="none", marker="o", ms=6.5, mfc="white", mec="black", mew=1.3, zorder=26.5)
fr.ax.plot(prov_ia.geometry.x, prov_ia.geometry.y, ls="none", marker="o", ms=2.1, mfc="black", mec="none", zorder=26.6)
fr.ax.plot(rib.geometry.x, rib.geometry.y, ls="none", marker="o", ms=4.6, mfc="#2b2b2b", mec="#1565c0", mew=1.1, zorder=26)
for g_, r_ in ((caps, 1.9), (prov_ia, 1.6), (rib, 1.1)):
    for p in g_.geometry: fr.labels.obstacle(p.x, p.y, r_)

fr.ax.plot([SEDE.x], [SEDE.y], marker="*", ms=17, mfc="#c8102e", mec="white", mew=1.0, zorder=31)
fr.labels.obstacle(SEDE.x, SEDE.y, 3.0)

# ------------------------------------------------ salidas de la jurisdicción y del país
for s_ in R["salidas_ia"]:
    fr.ax.plot([s_["x"]], [s_["y"]], marker="o", ms=17, mfc="white", mec=C["tarapoto"], mew=2.8, zorder=30)
    fr.ax.plot([s_["x"]], [s_["y"]], marker="o", ms=6, mfc=C["tarapoto"], mec="none", zorder=30.1)
    fr.labels.obstacle(s_["x"], s_["y"], 3.4)
for s_ in R["salidas_pais"]:
    big = s_["en_ia"] or "Amazonas" in s_["rio"]
    fr.ax.plot([s_["x"]], [s_["y"]], marker="o", ms=15 if big else 11, mfc="white", mec=ROJO, mew=2.4 if big else 1.8, zorder=30)
    fr.ax.plot([s_["x"]], [s_["y"]], marker="x", ms=7.5 if big else 5.5, mec=ROJO, mew=2.2 if big else 1.6, zorder=30.1)
    fr.labels.obstacle(s_["x"], s_["y"], 3.0 if big else 2.2)

# ------------------------------------------------ rótulos (por prioridad)
L = fr.labels
km_ia = {r["origen"]: r["km_salida_ia"] for r in R["rutas"] if r["km_salida_ia"]}
for s_ in R["salidas_ia"]:
    det = "  ·  ".join(f"km {fkm(v)} desde {o}" for o, v in km_ia.items())
    L.place(s_["x"], s_["y"], f"SALIDA DE LA JURISDICCIÓN\n{s_['rio']} → {s_['hacia'].replace('IA ', 'IA ').title().replace('Ia ', 'IA ')}\n{det}",
            size=10, weight="bold", color=C["tarapoto"], h=2.6, linespacing=1.1, offsets=ring(14) + ring(24), force=True)
km_pais = {}
for r in R["rutas"]:
    rio = r["etiqueta"].split("(río ")[-1].rstrip(")").strip()
    km_pais.setdefault(rio, []).append((r["km_total"], r["origen"]))
for s_ in sorted(R["salidas_pais"], key=lambda s_: (not s_["en_ia"], "Amazonas" not in s_["rio"])):
    big = s_["en_ia"] or "Amazonas" in s_["rio"]
    rio = s_["rio"]
    pais = s_["pais"].replace(", ", " / ")
    lineas = ["SALIDA DEL PAÍS"] + textwrap.wrap(f"{rio} → {pais}", 30)
    if s_["fronterizo"] and "Amazonas" not in rio: lineas.append("(río fronterizo)")
    clave = rio.replace("Río ", "")
    lineas += [f"km {fkm(k)} desde {o}" for k, o in km_pais.get(clave, [])]
    L.place(s_["x"], s_["y"], "\n".join(lineas), size=10 if big else 8.6, weight="bold", color=ROJO, h=2.4,
            linespacing=1.1, offsets=ring(12) + ring(20) + ring(30) + ring(42), force=True)
L.place(SEDE.x, SEDE.y, "SEDE IA TARAPOTO", size=10.5, weight="bold", color="#8b0a1e", h=2.4, offsets=ring(10) + ring(16), force=True)
for n, p in PXY.items():
    big = n in PRINC
    L.place(p.x, p.y, n.upper() if big else n, size=11.5 if big else 9, weight="bold", color="#0d3c8c", h=2.2,
            offsets=ring(9 if big else 6.5) + ring(16), force=big or n in PUERTOS_IA)
# kilómetros en los puntos de paso de las rutas
for r, ln in [(RUTA_KM, None)]:
    for nm, km, ll in r["paradas"]:
        if nm in ("Santa Rosa",): continue
        x_, y_ = TO_UTM.transform(*ll)
        fr.ax.plot([x_], [y_], marker="o", ms=4.5, mfc=NARANJA, mec="white", mew=0.8, zorder=29.5)
        L.place(x_, y_, f"km {fkm(km)}", size=8.2, weight="bold", color="#b34700", h=2, offsets=ring(7) + ring(12))
for r in caps.itertuples():
    L.place(r.geometry.x, r.geometry.y, r.txt.upper(), size=11, weight="bold", color=C["texto"], h=2.2, offsets=ring(7) + ring(12), force=True)
for r in prov_ia.itertuples():
    L.place(r.geometry.x, r.geometry.y, r.txt, size=9.4, weight="semibold", color=C["texto"], h=2, offsets=ring(6) + ring(11), force=True)
for r in rib.sort_values("pop", ascending=False).itertuples():
    L.place(r.geometry.x, r.geometry.y, r.txt, size=8.4 if r.nivel == 1 else 7.6, weight="semibold" if r.nivel == 1 else "medium",
            color="#0d3c8c", h=1.8, offsets=ring(5) + ring(9))
for g, n in zip(vec.geometry, vec.name):
    p, gi = M.ancla(g.difference(peru_g))
    if gi is not None and gi.area > 5e9:
        L.place(p.x, p.y, n.upper(), size=34, weight="bold", color="#9a9a9a", spacing=1, h=2.5,
                offsets=[(0, 0), (0, -80), (0, 80), (80, 0), (-80, 0), (0, -160), (0, 160)])
L.place(*TO_UTM.transform(-80.9, -7.9), "OCÉANO\nPACÍFICO", size=22, style="italic", color="#6f97b5", h=0, linespacing=1.0,
        offsets=[(0, 0), (0, -30), (-30, 0), (0, 30)], force=True)
for row in dep.itertuples():
    p, gi = M.ancla(row.geometry, 2000)
    if gi is None or gi.area < 4e9: continue
    L.place(p.x, p.y, nombre(row.departamento).upper(), size=16, weight="bold", color="#9a9a9a", spacing=1, h=2.2, alpha=0.9,
            inside=gi, inside_min=0.6, offsets=[(0, 0), (0, 40), (0, -40), (0, 80), (0, -80), (50, 0), (-50, 0)], shrink=(12, 10))
for row in circ.itertuples():
    p, gi = M.ancla(row.geometry, 2000)
    if gi is None or gi.area < 3e9: continue
    big = row.circ == "IA TARAPOTO"
    L.place(p.x, p.y, row.circ.replace("IA ", "INTENDENCIA DE ADUANA DE\n") if big else row.circ, size=15 if big else 10.5,
            weight="bold", color=C["tarapoto"] if big else C["circ"], h=2.4, linespacing=1.0, inside=gi, inside_min=0.6,
            offsets=[(0, -50), (0, 50), (0, -100), (0, 100), (60, 0), (-60, 0), (0, 0), (0, -150), (0, 150)], shrink=(9,) if not big else (13,))
rn = rios[rios.clase.isin(["hidrovia", "navegable", "rio"]) & (rios.name != "")]
for cl, (sz, ev) in {"hidrovia": (14, 160), "navegable": (10.5, 140), "rio": (7.6, 140)}.items():
    g = rn[rn.clase == cl]
    if cl == "rio": g = g[g.name.str.startswith("Río")]
    grupos = []
    for n, x in g.groupby("name"):
        geoms = [gg.intersection(peru_g) for gg in x.geometry if gg.intersects(peru_g)]
        geoms = [gg for gg in geoms if not gg.is_empty]
        if geoms: grupos.append((n.replace(" / Rio Javari", ""), geoms))
    along_labels(fr, grupos, ev, sz, "#0d3c8c" if cl != "rio" else C["agua_txt"], weight="bold" if cl != "rio" else "normal",
                 family="Liberation Serif", min_len_mm=20 if cl != "rio" else 30, h=1.8)
lagos = agua[agua.tipo == "lago"].copy(); lagos["a"] = lagos.area
for r in lagos.sort_values("a", ascending=False).head(3).itertuples():
    if isinstance(r.name, str) and r.geometry.area > 5e8:
        p = r.geometry.representative_point()
        L.place(p.x, p.y, r.name, size=10, style="italic", weight="bold", color="#0d3c8c", h=1.8, family="Liberation Serif")
fr.frame(step_deg=1.0, utm_km=100, skip=CAJAS)

# ======================================================================= recuadros
M.titulo(B_TIT, "RED FLUVIAL DEL NORTE DEL PERÚ", "SALIDAS DE LA JURISDICCIÓN Y DEL PAÍS",
         "Hidrovía Amazónica, ríos navegables, puertos y puntos de salida por vía fluvial de la IA Tarapoto y del territorio nacional",
         "1:1 250 000")
M.ubicacion(B_UBI, "UBICACIÓN · ÁMBITO DEL MAPA", tara, None, peru, circ, tara, color_sombra=UBI["destaque"])

x, y, w, h = B_LEY
M.caja(B_LEY)
M.barra(x, y + h - 9, w, "LEYENDA", h=9, size=9)
ly = y + h - 15
lg = Legend(pn, x + 6, ly, 124, row=9.4, size=9.8)
lg.header("Red fluvial")
lg.line("Hidrovía Amazónica (Amazonas, Marañón,\nHuallaga y Ucayali)", "#1257b0", 2.4, casing=("white", 4.0))
lg.cy -= 2
lg.line("Río navegable – embarcaciones menores", "#1e73be", 1.2)
lg.line("Río", "#7fb3dc", 0.5)
lg.box("Lago o laguna", fc=C["agua"], ec=C["agua_lin"], lw=0.3)
lg.line("Ruta fluvial de salida desde la IA Tarapoto", NARANJA, 8, alpha=0.38)
lg.marker("Kilometraje acumulado desde Yurimaguas", marker="o", ms=4.5, mfc=NARANJA, mec="white", mew=0.8)
lg.header("Puertos y control")
lg.marker("Puerto fluvial principal", marker="o", ms=11, mfc="#0d47a1", mec="white", mew=1.2)
lg.marker("Puerto o embarcadero", marker="o", ms=8, mfc="#0d47a1", mec="white", mew=1.0)
lg.marker("Oficina o puesto SUNAT junto a río navegable", marker="p", ms=7, mfc="#0d47a1", mec="white", mew=0.8)

lg2 = Legend(pn, x + 146, ly, 128, row=9.4, size=9.8)
lg2.header("Puntos de salida")
lg2.marker("Salida fluvial de la jurisdicción\nde la IA Tarapoto", marker="o", ms=12, mfc="white", mec=C["tarapoto"], mew=2.2)
pn.plot([lg2.x + lg2.sw / 2], [lg2.cy + lg2.row], ls="none", marker="o", ms=4.4, mfc=C["tarapoto"], mec="none", zorder=6)
lg2.cy -= 2
lg2.marker("Salida fluvial del país", marker="o", ms=11, mfc="white", mec=ROJO, mew=2)
pn.plot([lg2.x + lg2.sw / 2], [lg2.cy + lg2.row], ls="none", marker="x", ms=5.5, mec=ROJO, mew=1.8, zorder=6)
lg2.header("Límites")
lg2.line("Límite internacional", C["frontera"], 1.9, ls=(0, (6, 1.5, 1.2, 1.5)), under=("#d9534f", 5.5, 0.25))
lg2.line("Circunscripción IA Tarapoto (con relieve)", C["tarapoto"], 2.2, under=(C["tarapoto"], 7, 0.25))
lg2.line("Otras circunscripciones de aduana", C["circ"], 1.4, ls=(0, (4, 1.8)), alpha=0.75)
lg2.line("Límite departamental", "#a9a9a9", 0.8, ls=(0, (5, 1.5, 1, 1.5)))
lg2.header("Otros")
lg2.marker("Sede de la Intendencia de Aduana de Tarapoto", marker="*", ms=13, mfc="#c8102e", mec="white", mew=0.8)
lg2.marker("Capital de departamento", marker="s", ms=8, mfc="white", mec="black", mew=1.5)
cy_ = lg2.cy
lg2.marker("Capital de provincia (IA Tarapoto)", marker="o", ms=6.5, mfc="white", mec="black", mew=1.3)
pn.plot([lg2.x + lg2.sw / 2], [cy_], ls="none", marker="o", ms=2.1, mfc="black", mec="none", zorder=6)
lg2.marker("Capital de distrito ribereña", marker="o", ms=4.6, mfc="#2b2b2b", mec="#1565c0", mew=1.1)
lg2.line("Red vial nacional", "#ecbcbc", 1.2)
M.pie(x, min(lg.cy, lg2.cy) - 1, w)
print("leyenda: fondo de contenido en y =", round(min(lg.cy, lg2.cy) - 35, 1), "mm (borde inferior:", y, ")")

if MODE in ("both", "pdf"): fig.savefig(OUT + ".pdf")
if MODE in ("both", "nopdf"): fig.savefig(OUT + ".png", dpi=DPI)
print("ok", OUT, "| salidas del país:", len(R["salidas_pais"]), "| de la jurisdicción:", len(R["salidas_ia"]))
