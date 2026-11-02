# MAPA 3 – Frontera norte y red fluvial: de Condorcanqui al Datem del Marañón (A0 vertical, 1:550 000)
# Misma distribución que los mapas 1 y 2: el mapa ocupa todo el recuadro; relieve sólo en las provincias del tema
# (Condorcanqui, Datem del Marañón y Alto Amazonas) y fondo blanco fuera de ellas.
import sys
sys.path.insert(0, "/home/user/mapas_scripts")
from mural import *
from carto import _key

OUT = sys.argv[1] if len(sys.argv) > 1 else "/home/user/TARAPOTO-Dev/mapas/Mapa3_Frontera_Norte_Red_Fluvial"
DPI = int(sys.argv[2]) if len(sys.argv) > 2 else 300
MODE = sys.argv[3] if len(sys.argv) > 3 else "both"     # both | pdf | nopdf
SCALE = 550_000
M = Mural(SCALE, 53_000, 9_215_000 + 1149 * SCALE / 1000)
fr, fig, bg, ov, pn = M.fr, M.fig, M.bg, M.ov, M.pn
CB = fr.clipbox(0.05)

# recuadros dentro del marco (x, y, ancho, alto en mm de página)
B_TIT = (20, 1079, 300, 90)       # título (noroeste, sobre Ecuador)
B_UBI = (591, 980, 230, 189)      # ubicación (noreste)
B_LEY = (20, 20, 262, 270)        # leyenda (suroeste)
CAJAS = (B_TIT, B_UBI, B_LEY)
M.reservar(*CAJAS)

# ------------------------------------------------ datos
circ = gpd.read_file(f"{U}/circunscripciones.gpkg"); peru = gpd.read_file(f"{U}/peru.gpkg")
paises = gpd.read_file(f"{U}/paises.gpkg"); pext = gpd.read_file(f"{U}/prov_extranjeras.gpkg")
dist = fr.load("distritos_tematico"); prov = fr.load("provincias"); dep = fr.load("departamentos")
peru_g = peru.geometry.iloc[0]; tara = circ[circ.circ == "IA TARAPOTO"].geometry.iloc[0]
ecu = paises[paises.name == "Ecuador"].geometry.iloc[0]
ext = [g.difference(peru_g) for g in paises.geometry]; land = [peru_g] + ext
land_u = unary_union(land)
PROVS = ["CONDORCANQUI", "DATEM DEL MARAÑON", "ALTO AMAZONAS"]
AMB = unary_union(list(gpd.read_file(f"{U}/provincias.gpkg").query("provincia in @PROVS").geometry))
front = peru_g.boundary.intersection(ecu.buffer(3000)).intersection(CB)     # frontera Perú–Ecuador

# ------------------------------------------------ relieve sólo en el ámbito del mapa; fuera, fondo blanco
FUERA = CB.difference(AMB).intersection(land_u)
fr.relief(dem="/home/user/data_base/dem_m1_z12.tif", res=45, src_res=38, land=land, veil=[FUERA], veil_alpha=1.0, shade=(0.60, 0.46))
CL_IN = fr.clip_patch(AMB.intersection(CB)); fr.ax.add_patch(CL_IN)
CL_OUT = fr.clip_patch(CB.difference(AMB)); fr.ax.add_patch(CL_OUT)

# ------------------------------------------------ hidrografía (protagonista del mapa)
agua = fr.load("agua_poly"); rios = fr.load("rios"); hum = fr.load("humedales")
fr.polys(list(hum.geometry), fc="#b9d9c9", alpha=0.45, z=2, clip=CL_IN)
fr.polys(list(agua.geometry), fc=C["agua"], ec=C["agua_lin"], lw=0.2, z=3)
W_IN = {"quebrada": (0.3, 0.75), "canal": (0.4, 0.8), "rio": (0.8, 1), "navegable": (1.9, 1), "hidrovia": (3.0, 1)}
W_OUT = {"rio": (0.5, 0.8), "navegable": (1.2, 0.9), "hidrovia": (2.0, 0.9)}
for i, cl in enumerate(W_IN):
    g = list(rios[rios.clase == cl].geometry)
    if cl in ("navegable", "hidrovia"):
        fr.lines(g, color="white", lw=W_IN[cl][0] + 1.4, z=3.15 + 0.1 * i, alpha=0.8, clip=CL_IN)
    fr.lines(g, color=C["agua_lin"] if cl not in ("navegable", "hidrovia") else "#1565c0", lw=W_IN[cl][0], alpha=W_IN[cl][1],
             z=3.2 + 0.1 * i, clip=CL_IN)
    if cl in W_OUT:
        fr.lines(g, color="#7fb3dc", lw=W_OUT[cl][0], alpha=W_OUT[cl][1], z=3.2 + 0.1 * i, clip=CL_OUT)
anp = fr.load("anp")
fr.polys(list(anp.geometry), fc=C["anp"], alpha=0.06, z=3.9, clip=CL_IN)
fr.polys(list(anp.geometry), fc="none", ec=C["anp"], lw=0.9, ls=(0, (1.5, 1.2)), z=4, alpha=0.9, clip=CL_IN)

# ------------------------------------------------ límites
fr.lines(list(dist.geometry.boundary), color=C["dist"], lw=0.45, ls=(0, (2.2, 1.6)), z=6, clip=CL_IN)
fr.lines(list(prov.geometry.boundary), color=C["prov"], lw=1.0, ls=(0, (5, 2.2)), z=6.5, clip=CL_IN)
fr.lines(list(prov.geometry.boundary), color="#bdbdbd", lw=0.6, ls=(0, (5, 2.2)), z=6.5, clip=CL_OUT)
fr.lines(list(dep.geometry.boundary), color=C["dep"], lw=1.7, ls=(0, (8, 2.5, 1.5, 2.5)), z=7)
cb = unary_union([g.boundary for g in circ.geometry]).difference(peru_g.boundary.buffer(800))
fr.lines([cb.intersection(CB)], color=C["circ"], lw=2.2, ls=(0, (7, 3)), z=8)
fr.lines([tara.boundary.difference(peru_g.boundary.buffer(800))], color=C["tarapoto"], lw=2.2, z=8.4)
fr.lines([AMB.boundary], color="#2e7d32", lw=8, alpha=0.22, z=8.1, clip=CL_IN, cap="butt")
fr.lines(list(pext.geometry.boundary), color="#a5a5a5", lw=0.8, ls=(0, (5, 2.5)), z=6.5)
fr.lines([peru_g.boundary.intersection(CB)], color="#d9534f", lw=8, alpha=0.28, z=9)
fr.lines([peru_g.boundary.intersection(CB)], color=C["frontera"], lw=2.4, ls=(0, (10, 2.5, 2, 2.5, 2, 2.5)), z=9.2)

# ------------------------------------------------ red vial, senderos y transbordos
vias = fr.load("vias"); vx = vias[~vias.pe]; vp = vias[vias.pe]
sen = gpd.read_file(f"{U}/senderos_m3.gpkg")
fr.lines(list(sen[sen.highway.notna()].geometry), color="#8d6e63", lw=0.5, ls=(0, (1.2, 1.4)), z=9.6, clip=CL_IN)
ferry = sen[sen.route == "ferry"]
fr.lines(list(ferry.geometry), color="#0d47a1", lw=0.9, ls=(0, (4, 2)), z=9.7)
fr.lines(list(vx[vx.clase.isin(["trocha", "vecinal"])].geometry), color="#c4c4c4", lw=0.4, z=10)
fr.lines(list(vx[vx.clase.isin(["nacional", "departamental"])].geometry), color="#a8a8a8", lw=0.9, z=10.2)
dv = vp[vp.clase == "departamental"]; nv = vp[vp.clase == "nacional"]
fr.lines(list(vp[vp.clase == "trocha"].geometry), color=C["trocha"], lw=0.6, ls=(0, (3, 1.6)), z=10.4, clip=CL_IN)
fr.lines(list(vp[vp.clase == "vecinal"].geometry), color=C["vecinal"], lw=0.8, z=10.5, clip=CL_IN)
fr.lines(list(dv.geometry), color="#7a4a00", lw=2.0, z=11, cap="butt", clip=CL_IN)
fr.lines(list(dv.geometry), color=C["departamental"], lw=1.4, z=11.1, clip=CL_IN)
fr.lines(list(nv.geometry), color="#5a0010", lw=2.8, z=12, cap="butt", clip=CL_IN)
fr.lines(list(nv.geometry), color=C["nacional"], lw=2.0, z=12.1, clip=CL_IN)
fr.lines(list(vp[vp.clase == "vecinal"].geometry), color="#cfc2b4", lw=0.5, z=10.5, clip=CL_OUT)
fr.lines(list(dv.geometry), color="#f4cfa8", lw=0.9, z=11, clip=CL_OUT)
fr.lines(list(nv.geometry), color="#eba8a8", lw=1.4, z=12, clip=CL_OUT)

# ------------------------------------------------ cruces de frontera (vías/senderos y ríos)
def crossings(lines_gdf, tol=1500):
    pts_ = []
    for g, n in zip(lines_gdf.geometry, lines_gdf.get("name", pd.Series([None] * len(lines_gdf)))):
        ip = g.intersection(front)
        for p in getattr(ip, "geoms", [ip]):
            if p.is_empty or p.geom_type != "Point": continue
            if all(p.distance(q) > tol for q, _ in pts_): pts_.append((p, n if isinstance(n, str) else None))
    return pts_
roads_all = pd.concat([vias[["name", "geometry"]], sen[sen.highway.notna()][["name", "geometry"]]])
xr = crossings(roads_all[roads_all.intersects(front.buffer(10))])
xw = crossings(rios[rios.clase.isin(["rio", "navegable", "hidrovia"]) & rios.intersects(front.buffer(10))], tol=3000)
for p, n in xr:
    fr.ax.plot([p.x], [p.y], marker="D", ms=8, mfc="#ffeb3b", mec="#b71c1c", mew=1.6, zorder=27)
    fr.labels.obstacle(p.x, p.y, 2.5)
for p, n in xw:
    fr.ax.plot([p.x], [p.y], marker="o", ms=9.5, mfc="white", mec="#0d47a1", mew=2.0, zorder=27)
    fr.ax.plot([p.x], [p.y], marker="o", ms=3.8, mfc="#0d47a1", mec="none", zorder=27.1)
    fr.labels.obstacle(p.x, p.y, 2.7)

# ------------------------------------------------ puntos operativos y puertos
pts = fr.load("puntos"); pts = pts[pts.geometry.within(fr.bbox) & pts.pe]
pts = pts[pts.geometry.within(AMB) | (pts.distance(front) < 10000)]
mil = pts[pts.clase == "militar"]
draw_points(fr, pts[pts.clase.isin(["peaje", "control", "frontera", "sunat", "aerodromo", "helipuerto", "puerto", "policia"])])
fr.ax.plot(mil.geometry.x, mil.geometry.y, ls="none", marker="P", ms=6.5, mfc="#4e342e", mec="white", mew=0.6, zorder=24)
for p in mil.geometry: fr.labels.obstacle(p.x, p.y, 1.4)
PUERTOS = {"Saramiriza": (-77.4175, -4.564), "San Lorenzo": (-76.5546, -4.8316), "Yurimaguas": (-76.1047, -5.8952)}
PSEC = {"Puerto Galilea": (-77.7583, -4.0151), "Santa María de Nieva": (-77.8667, -4.5938), "Borja": (-77.5462, -4.4697),
        "Lagunas": (-75.6797, -5.227), "Nuevo Andoas": (-76.4576, -2.8073), "Imacita": (-78.336, -5.058)}
PXY = {n: Point(*TO_UTM.transform(lo, la)) for n, (lo, la) in {**PUERTOS, **PSEC}.items()}
for n, p in PXY.items():
    big = n in PUERTOS
    fr.ax.plot([p.x], [p.y], marker="o", ms=18 if big else 12, mfc="#0d47a1", mec="white", mew=1.6, zorder=29)
    fr.ax.text(p.x, p.y, "⚓", fontsize=10 if big else 7, color="white", ha="center", va="center", family="DejaVu Sans", zorder=29.5)
    fr.labels.obstacle(p.x, p.y, 3.6 if big else 2.4)

# ------------------------------------------------ centros poblados
# capitales oficiales (INEI) del ámbito y capitales de provincia vecinas; poblados ribereños (OSM, place=village/town)
caps = fr.load("capitales"); caps = caps[caps.geometry.within(fr.bbox)].copy()
caps["en_amb"] = caps.within(AMB.buffer(200))
caps["puerto"] = [min(p.distance(q) for q in PXY.values()) < 3000 for p in caps.geometry]
caps = caps[(caps.en_amb | (caps.nivel <= 1)) & ~caps.puerto]
caps = dibujar_capitales(fr, caps)
nav = unary_union(list(rios[rios.clase.isin(["navegable", "hidrovia"])].geometry))
lug = fr.load("lugares"); lug = lug[lug.geometry.within(fr.bbox)].copy()
lug = lug[lug.place.isin(["village", "town", "city"]) & lug.pe & lug.geometry.within(AMB)]
lug = lug[(lug.distance(nav) < 1500)]
lug = lug[[caps.distance(p).min() > 1500 and min(p.distance(q) for q in PXY.values()) > 2000 for p in lug.geometry]]
fr.ax.plot(lug.geometry.x, lug.geometry.y, ls="none", marker="o", ms=4.6, mfc="#2b2b2b", mec="#1565c0", mew=1.1, zorder=25)
for p in lug.geometry: fr.labels.obstacle(p.x, p.y, 1.0)
# localidades de Ecuador cercanas a la frontera (cabeceras), como referencia de los pasos
lx = gpd.read_file("/home/user/data_base/osm/lugares_points.gpkg").to_crs(32718)
lx = lx[lx.geometry.within(fr.bbox) & lx.geometry.within(ecu) & lx.capital.isin(["4", "6"]) & lx.name.notna()]
lx = lx[lx.distance(front) < 45000]
fr.ax.plot(lx.geometry.x, lx.geometry.y, ls="none", marker="o", ms=4.4, mfc="white", mec="#777", mew=1.0, zorder=24)
for p in lx.geometry: fr.labels.obstacle(p.x, p.y, 1.0)

# ------------------------------------------------ rótulos (por prioridad)
L = fr.labels
for n in PUERTOS:
    p = PXY[n]
    L.place(p.x, p.y, f"PUERTO {n.upper()}", size=12, weight="bold", color="#0d3c8c", h=2.5, offsets=ring(13) + ring(22), force=True)
for n in PSEC:
    p = PXY[n]
    L.place(p.x, p.y, n, size=9.6, weight="bold", color="#0d3c8c", h=2.2, offsets=ring(9) + ring(16), force=True)
for p, n in xw:
    L.place(p.x, p.y, f"Cruce fluvial\n{n or 's/n'}", size=8, weight="bold", color="#0d47a1", h=2, linespacing=1.0, offsets=ring(10) + ring(18), force=True)
for p, n in xr:
    lo, la = TO_LL.transform(p.x, p.y)
    L.place(p.x, p.y, f"Cruce vial o de sendero\n{abs(la):.4f}° S  {abs(lo):.4f}° W".replace(".", ","),
            size=7.2, weight="bold", color="#b71c1c", h=2, linespacing=1.0, offsets=ring(9) + ring(16))
n_cap = rotular_capitales(fr, caps, forzar=caps.en_amb, k=1.0)
for r in lug.sort_values("pop", ascending=False).itertuples():
    L.place(r.geometry.x, r.geometry.y, r.name, size=7.6, weight="medium", color="#0d3c8c", offsets=ring(4.5), h=1.6)
for r in lx.itertuples():
    L.place(r.geometry.x, r.geometry.y, r.name, size=8, color="#7a7a7a", offsets=ring(4.5), h=1.6)
for g, n in zip(paises.geometry, paises.name):
    p, gi = M.ancla(g.difference(peru_g))
    if gi is not None and gi.area > 1e8:
        L.place(p.x, p.y, n.upper(), size=32, weight="bold", color="#8a8a8a", spacing=1, h=2.5,
                offsets=[(0, 0), (0, -60), (0, 60), (60, 0), (-60, 0), (0, -120), (0, 120)], force=True)
for row in pext.itertuples():
    p, gi = M.ancla(row.geometry.difference(peru_g))
    if gi is not None and gi.area > 3e8:
        L.place(p.x, p.y, f"Provincia de {row.name}", size=11, style="italic", color="#8a8a8a", h=1.8, offsets=[(0, 0), (0, 30), (0, -30), (0, 60)])
for row in dep.itertuples():
    p, gi = M.ancla(row.geometry, 1000)
    if gi is None or gi.area < 2e9: continue
    own = AMB.intersects(row.geometry)
    L.place(p.x, p.y, nombre(row.departamento).upper(), size=28 if own else 22, weight="bold", color="#4a4a4a" if own else "#9a9a9a",
            spacing=1, h=2.6, alpha=0.75, inside=gi, inside_min=0.6,
            offsets=[(0, 0), (0, 50), (0, -50), (0, 100), (0, -100), (60, 0), (-60, 0), (0, 150), (0, -150)], shrink=(22, 18))
for row in circ.itertuples():
    p, gi = M.ancla(row.geometry, 1000)
    if gi is None or gi.area < 2e9: continue
    L.place(p.x, p.y, row.circ, size=14, weight="bold", color=C["tarapoto"] if row.circ == "IA TARAPOTO" else C["circ"], h=2.4,
            inside=gi, inside_min=0.6, offsets=[(0, -60), (0, 60), (0, -120), (0, 120), (50, 0), (-50, 0), (0, 0)], shrink=(12,))
for row in prov.itertuples():
    p, gi = M.ancla(row.geometry, 300)
    if gi is None or gi.area < 1e8: continue
    own = row.provincia in PROVS
    L.place(p.x, p.y, nombre(row.provincia).upper(), size=17 if own else 9, weight="bold" if own else "semibold",
            color="#2f3a29" if own else "#9a9a9a", h=2.4 if own else 1.8, spacing=1 if own else 0,
            offsets=[(0, 0), (0, 20), (0, -20), (30, 0), (-30, 0), (0, 40), (0, -40), (0, 60), (0, -60)], inside=gi, shrink=(14, 12) if own else (8,))
# distritos del ámbito (sólo cuando su nombre es distinto al de su capital)
cap_txt = dict(zip(caps.ubigeo, caps.txt))
allcaps = gpd.read_file(f"{U}/capitales.gpkg", ignore_geometry=True)
cap_txt.update({u: nom_cap(n) for u, n in zip(allcaps.ubigeo, allcaps.nombre) if u not in cap_txt})
dd = dist[dist.provincia.isin(PROVS)].copy()
dd = dd[[_key(nombre(d_)) != _key(cap_txt.get(u, "")) for d_, u in zip(dd.distrito, dd.ubigeo)]]
for row in dd.assign(a=dd.area).sort_values("a", ascending=False).itertuples():
    p, gi = M.ancla(row.geometry, 200)
    if gi is None: continue
    L.place(p.x, p.y, nombre(row.distrito), size=9, style="italic", color="#4f3a66", h=1.6, inside=gi,
            offsets=[(0, 0), (0, 12), (0, -12), (16, 0), (-16, 0), (0, 24), (0, -24)], shrink=(8, 7))
rn = rios[rios.clase.isin(["hidrovia", "navegable", "rio"]) & rios.name.notna()]
for cl, (sz, ev) in {"hidrovia": (14, 120), "navegable": (11.5, 110), "rio": (8, 110)}.items():
    g = rn[rn.clase == cl]
    grupos = []
    for n, x in g.groupby("name"):
        geoms = list(x.geometry) if cl != "rio" else [gg.intersection(AMB) for gg in x.geometry if gg.intersects(AMB)]
        if geoms: grupos.append((n, geoms))
    along_labels(fr, grupos, ev, sz, "#0d3c8c" if cl != "rio" else C["agua_txt"], weight="bold" if cl != "rio" else "normal",
                 family="Liberation Serif", min_len_mm=15 if cl != "rio" else 25, h=2)
nv_in = nv[nv.intersects(AMB)].copy(); nv_in["geometry"] = nv_in.geometry.intersection(AMB)
shields(fr, nv_in, "nacional", C["nacional"], "white", every_mm=80, size=7.2)
nv_out = nv[~nv.within(AMB)].copy(); nv_out["geometry"] = nv_out.geometry.difference(AMB)
shields(fr, nv_out, "nacional", "#e3a3a3", "white", every_mm=120, size=6.4)
dv_in = dv[dv.intersects(AMB)].copy(); dv_in["geometry"] = dv_in.geometry.intersection(AMB)
shields(fr, dv_in, "departamental", "#ffd08a", "#4a2b00", every_mm=90, size=6.4, min_len_mm=20)
for row in pd.concat([pts[pts.clase.isin(["peaje", "control", "frontera", "sunat", "aerodromo", "helipuerto", "policia"])], mil]).itertuples():
    if not isinstance(row.name, str): continue
    col = {"aerodromo": "#0b3d91", "sunat": "#0d47a1", "peaje": "#5d4a00", "frontera": "#9b1c1c", "militar": "#4e342e"}.get(row.clase, "#333")
    L.place(row.geometry.x, row.geometry.y, row.name, size=7.2, color=col, offsets=ring(5.5), h=1.6)
for row in anp.itertuples():
    p, gi = M.ancla(row.geometry.intersection(AMB), 500)
    if gi is None or gi.area < 1e8: continue
    L.place(p.x, p.y, row.name, size=8.6, style="italic", color="#2e6b2e", h=1.6, inside=gi, offsets=[(0, 0), (0, 14), (0, -14), (0, 28)])
fr.frame(step_deg=0.5, utm_km=50, skip=CAJAS)

# ======================================================================= recuadros
M.titulo(B_TIT, "FRONTERA NORTE Y RED FLUVIAL", "DE CONDORCANQUI AL DATEM DEL MARAÑÓN",
         "Ríos Santiago, Cenepa, Morona, Pastaza, Marañón y Huallaga · puertos, poblados ribereños y cruces de frontera",
         "1:550 000")
M.ubicacion(B_UBI, "UBICACIÓN · ÁMBITO DEL MAPA EN LA IA TARAPOTO", AMB, None, peru, circ, tara, color_sombra=UBI["destaque"], fondo_ia=True)

# ------------------------------------------------ leyenda (SO)
x, y, w, h = B_LEY
M.caja(B_LEY)
M.barra(x, y + h - 9, w, "LEYENDA", h=9, size=9)
ly = y + h - 15
lg = Legend(pn, x + 6, ly, 118, row=9.6, size=9.8)
lg.header("Frontera y control")
lg.line("Límite internacional Perú – Ecuador", C["frontera"], 2.2, ls=(0, (6, 1.5, 1.2, 1.5)), under=("#d9534f", 7, 0.28))
lg.marker("Cruce vial o de sendero con la frontera", marker="D", ms=7, mfc="#ffeb3b", mec="#b71c1c", mew=1.4)
lg.marker("Cruce fluvial de la frontera", marker="o", ms=8, mfc="white", mec="#0d47a1", mew=1.8)
lg.marker("Control fronterizo / Migraciones / SUNAT", marker="h", ms=6.4, mfc="#c62828", mec="white", mew=0.7)
lg.marker("Puesto de control o vigilancia", marker="^", ms=5.4, mfc="#ef5350", mec="#3b0000", mew=0.6)
lg.marker("Puesto o base militar (territorio peruano)", marker="P", ms=6.5, mfc="#4e342e", mec="white", mew=0.6)
lg.glyph("Aeródromo / helipuerto", "✈", "#0b3d91")
lg.header("Red fluvial")
lg.line("Vía navegable principal (Hidrovía Amazónica)", "#1565c0", 3.0, casing=("white", 4.4))
lg.line("Río navegable – embarcaciones menores", "#1565c0", 1.9, casing=("white", 3.3))
lg.line("Río / quebrada", C["agua_lin"], 0.8)
lg.line("Ruta de transbordo / ferry", "#0d47a1", 0.9, ls=(0, (4, 2)))
lg.marker("Puerto fluvial principal", marker="o", ms=11, mfc="#0d47a1", mec="white", mew=1.4)
lg.marker("Puerto / embarcadero secundario", marker="o", ms=8, mfc="#0d47a1", mec="white", mew=1.2)

lg2 = Legend(pn, x + 134, ly, 120, row=9.6, size=9.8)
lg2.header("Ámbito y límites")
lg2.box("Ámbito del mapa: Condorcanqui, Datem del\nMarañón y Alto Amazonas (con relieve)", fc="#dfe6c9", ec="#2e7d32", lw=0.8)
lg2.cy -= 2
lg2.box("Fuera del ámbito (fondo blanco)", fc="white", ec="#888", lw=0.5)
lg2.line("Circunscripción IA Tarapoto / otras IA", C["tarapoto"], 2.2)
lg2.line("Límite departamental / provincial", C["dep"], 1.5, ls=(0, (5, 1.5, 1, 1.5)))
lg2.line("Límite distrital (referencial INEI)", C["dist"], 0.5, ls=(0, (2, 1.4)))
lg2.box("Área natural protegida", fc="#e3efe3", ec=C["anp"], lw=0.8, ls=(0, (1.5, 1.2)))
lg2.header("Vías")
lg2.line("Red vial nacional / departamental", C["nacional"], 2.0, casing=("#5a0010", 2.8))
lg2.line("Red vial vecinal / trocha", C["vecinal"], 0.8)
lg2.line("Sendero / camino peatonal", "#8d6e63", 0.6, ls=(0, (1.2, 1.4)))
lg2.header("Centros poblados")
lg2.marker("Capital de departamento", ms=9, **SYM[0])
cy_ = lg2.cy
lg2.marker("Capital de provincia", ms=8, **SYM[1])
pn.plot([lg2.x + lg2.sw / 2], [cy_], ls="none", marker="o", ms=8 * 0.32, mfc="black", mec="none", zorder=6)
lg2.marker("Capital de distrito", ms=5.4, **SYM[2])
lg2.marker("Poblado ribereño", marker="o", ms=4.6, mfc="#2b2b2b", mec="#1565c0", mew=1.1)
lg2.marker("Localidad de Ecuador (referencia)", marker="o", ms=4.4, mfc="white", mec="#777", mew=1.0)
M.pie(x, min(lg.cy, lg2.cy) - 1, w)
print("leyenda: fondo de contenido en y =", round(min(lg.cy, lg2.cy) - 35, 1), "mm (borde inferior:", y, ")")

if MODE in ("both", "pdf"): fig.savefig(OUT + ".pdf")
if MODE in ("both", "nopdf"): fig.savefig(OUT + ".png", dpi=DPI)
print("ok", OUT, "| cruces viales", len(xr), "| fluviales", len(xw), "| capitales rotuladas", n_cap, "| poblados ribereños", len(lug))
