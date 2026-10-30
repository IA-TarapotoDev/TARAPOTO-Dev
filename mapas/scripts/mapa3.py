# MAPA 3 – Frontera norte y red fluvial: de Condorcanqui al Datem del Marañón (A0 vertical, 1:550 000)
import sys
sys.path.insert(0, "/home/user/mapas_scripts")
from carto import *

OUT = sys.argv[1] if len(sys.argv) > 1 else "/home/user/TARAPOTO-Dev/mapas/Mapa3_Frontera_Norte_Red_Fluvial"
DPI = int(sys.argv[2]) if len(sys.argv) > 2 else 300
NOPDF = len(sys.argv) > 3
SCALE = 550_000
fig, bg = page()
ov = fig.ov
fr = MapFrame(fig, (15, 288, 811, 804), (275_500, 9_546_000), SCALE)
CB = fr.clipbox(0.05)

circ = gpd.read_file(f"{U}/circunscripciones.gpkg"); peru = gpd.read_file(f"{U}/peru.gpkg")
paises = gpd.read_file(f"{U}/paises.gpkg"); pext = gpd.read_file(f"{U}/prov_extranjeras.gpkg")
dist = fr.load("distritos_tematico"); prov = fr.load("provincias"); dep = fr.load("departamentos")
peru_g = peru.geometry.iloc[0]; tara = circ[circ.circ == "IA TARAPOTO"].geometry.iloc[0]
ecu = paises[paises.name == "Ecuador"].geometry.iloc[0]
ext = [g.difference(peru_g) for g in paises.geometry]; land = [peru_g] + ext
# frontera Perú–Ecuador (contorno INEI próximo al polígono de Ecuador)
front = peru_g.boundary.intersection(ecu.buffer(3000)).intersection(CB)

# ------------------------------------------------ fondo
fr.relief(res=50, land=land, veil=[g.intersection(CB) for g in ext], veil_alpha=0.50)
fr.polys([peru_g.difference(tara).intersection(CB)], fc="white", alpha=0.25, z=1)
agua = fr.load("agua_poly"); rios = fr.load("rios"); hum = fr.load("humedales")
fr.polys(list(hum.geometry), fc="#b9d9c9", alpha=0.45, z=2)
fr.polys(list(agua.geometry), fc=C["agua"], ec=C["agua_lin"], lw=0.2, z=3)
W = {"quebrada": (0.3, 0.75), "canal": (0.4, 0.8), "rio": (0.8, 1), "navegable": (1.9, 1), "hidrovia": (3.0, 1)}
for cl in W:
    g = rios[rios.clase == cl]
    if cl in ("navegable", "hidrovia"):
        fr.lines(list(g.geometry), color="white", lw=W[cl][0] + 1.4, z=3.15 + 0.1 * list(W).index(cl), alpha=0.8)
    fr.lines(list(g.geometry), color=C["agua_lin"] if cl not in ("navegable", "hidrovia") else "#1565c0", lw=W[cl][0], alpha=W[cl][1],
             z=3.2 + 0.1 * list(W).index(cl))
anp = fr.load("anp")
fr.polys(list(anp.geometry), fc=C["anp"], alpha=0.06, z=3.9)
fr.polys(list(anp.geometry), fc="none", ec=C["anp"], lw=0.9, ls=(0, (1.5, 1.2)), z=4, alpha=0.9)

# ------------------------------------------------ límites
fr.lines(list(dist.geometry.boundary), color=C["dist"], lw=0.45, ls=(0, (2.2, 1.6)), z=6)
fr.lines(list(prov.geometry.boundary), color=C["prov"], lw=1.0, ls=(0, (5, 2.2)), z=6.5)
fr.lines(list(dep.geometry.boundary), color=C["dep"], lw=1.7, ls=(0, (8, 2.5, 1.5, 2.5)), z=7)
cb = unary_union([g.boundary for g in circ.geometry]).difference(peru_g.boundary.buffer(800))
fr.lines([cb.intersection(CB)], color=C["circ"], lw=2.2, ls=(0, (7, 3)), z=8)
tclip = fr.clip_patch(tara.intersection(CB)); fr.ax.add_patch(tclip)
fr.lines([tara.boundary], color=C["tarapoto"], lw=7, alpha=0.25, z=8.2, clip=tclip, cap="butt")
fr.lines([tara.boundary.difference(peru_g.boundary.buffer(800))], color=C["tarapoto"], lw=2.2, z=8.4)
fr.lines(list(pext.geometry.boundary), color="#6a6a6a", lw=0.8, ls=(0, (5, 2.5)), z=6.5)
fr.lines([peru_g.boundary.intersection(CB)], color="#d9534f", lw=8, alpha=0.28, z=9)
fr.lines([peru_g.boundary.intersection(CB)], color=C["frontera"], lw=2.4, ls=(0, (10, 2.5, 2, 2.5, 2, 2.5)), z=9.2)

# ------------------------------------------------ red vial y senderos
vias = fr.load("vias"); vx = vias[~vias.pe]; vp = vias[vias.pe]
sen = gpd.read_file(f"{U}/senderos_m3.gpkg")
fr.lines(list(sen[sen.highway.notna()].geometry), color="#8d6e63", lw=0.5, ls=(0, (1.2, 1.4)), z=9.6)
ferry = sen[sen.route == "ferry"]
fr.lines(list(ferry.geometry), color="#0d47a1", lw=0.9, ls=(0, (4, 2)), z=9.7)
fr.lines(list(vx[vx.clase.isin(["trocha", "vecinal"])].geometry), color="#9a9a9a", lw=0.45, z=10)
fr.lines(list(vx[vx.clase.isin(["nacional", "departamental"])].geometry), color="#7d7d7d", lw=1.1, z=10.2)
fr.lines(list(vp[vp.clase == "trocha"].geometry), color=C["trocha"], lw=0.6, ls=(0, (3, 1.6)), z=10.4)
fr.lines(list(vp[vp.clase == "vecinal"].geometry), color=C["vecinal"], lw=0.8, z=10.5)
fr.lines(list(vp[vp.clase == "departamental"].geometry), color="#7a4a00", lw=2.0, z=11, cap="butt")
fr.lines(list(vp[vp.clase == "departamental"].geometry), color=C["departamental"], lw=1.4, z=11.1)
fr.lines(list(vp[vp.clase == "nacional"].geometry), color="#5a0010", lw=2.8, z=12, cap="butt")
fr.lines(list(vp[vp.clase == "nacional"].geometry), color=C["nacional"], lw=2.0, z=12.1)

# ------------------------------------------------ cruces de frontera (vías/senderos y ríos)
def crossings(lines_gdf, tol=1500):
    pts = []
    for g, n in zip(lines_gdf.geometry, lines_gdf.get("name", pd.Series([None] * len(lines_gdf)))):
        ip = g.intersection(front)
        for p in getattr(ip, "geoms", [ip]):
            if p.is_empty or p.geom_type != "Point": continue
            if all(p.distance(q) > tol for q, _ in pts): pts.append((p, n if isinstance(n, str) else None))
    return pts
roads_all = pd.concat([vias[["name", "geometry"]], sen[sen.highway.notna()][["name", "geometry"]]])
xr = crossings(roads_all[roads_all.intersects(front.buffer(10))])
xw = crossings(rios[rios.clase.isin(["rio", "navegable", "hidrovia"]) & rios.intersects(front.buffer(10))], tol=3000)
for p, n in xr:
    fr.ax.plot([p.x], [p.y], marker="D", ms=7.5, mfc="#ffeb3b", mec="#b71c1c", mew=1.6, zorder=27)
    fr.labels.obstacle(p.x, p.y, 2.4)
for p, n in xw:
    fr.ax.plot([p.x], [p.y], marker="o", ms=9, mfc="white", mec="#0d47a1", mew=2.0, zorder=27)
    fr.ax.plot([p.x], [p.y], marker="o", ms=3.6, mfc="#0d47a1", mec="none", zorder=27.1)
    fr.labels.obstacle(p.x, p.y, 2.6)

# ------------------------------------------------ puntos operativos, puertos y poblados ribereños
pts = fr.load("puntos"); pts = pts[pts.geometry.within(fr.bbox)]
mil = pts[(pts.clase == "militar") & pts.pe]
draw_points(fr, pts[pts.clase.isin(["peaje", "control", "frontera", "sunat", "aerodromo", "helipuerto", "puerto", "policia"])])
fr.ax.plot(mil.geometry.x, mil.geometry.y, ls="none", marker="P", ms=6, mfc="#4e342e", mec="white", mew=0.6, zorder=24)
PUERTOS = {"Saramiriza": (-77.4175, -4.564), "San Lorenzo": (-76.5546, -4.8316), "Yurimaguas": (-76.1047, -5.8952)}
PSEC = {"Puerto Galilea": (-77.7583, -4.0151), "Santa María de Nieva": (-77.8667, -4.5938), "Borja": (-77.5462, -4.4697),
        "Lagunas": (-75.6797, -5.227), "Nuevo Andoas": (-76.4576, -2.8073), "Imacita": (-78.336, -5.058)}
for n, (lo, la) in {**PUERTOS, **PSEC}.items():
    X, Y = TO_UTM.transform(lo, la)
    big = n in PUERTOS
    fr.ax.plot([X], [Y], marker="o", ms=17 if big else 11, mfc="#0d47a1", mec="white", mew=1.6, zorder=29)
    fr.ax.text(X, Y, "⚓", fontsize=9.5 if big else 6.5, color="white", ha="center", va="center", family="DejaVu Sans", zorder=29.5)
    fr.labels.obstacle(X, Y, 3.4 if big else 2.2)

lug = fr.load("lugares"); lug = lug[lug.geometry.within(fr.bbox)].copy()
nav = unary_union(list(rios[rios.clase.isin(["navegable", "hidrovia"])].geometry))
lug["riber"] = lug.distance(nav) < 1500
lug["rank"] = np.select([lug.cap == 4, lug.cap == 6, lug.cap == 8, lug.place.isin(["city", "town"]), lug.place == "village"], [0, 1, 2, 3, 4], 5)
lug.loc[~lug.pe & (lug["rank"] == 2), "rank"] = 4
STY = {0: dict(marker="s", ms=7, mfc="white", mec="black", mew=1.4), 1: dict(marker="o", ms=6.2, mfc="white", mec="black", mew=1.3),
       2: dict(marker="o", ms=4.2, mfc="#222", mec="white", mew=0.6), 3: dict(marker="o", ms=3.4, mfc="#333", mec="white", mew=0.5),
       4: dict(marker="o", ms=2.7, mfc="#444", mec="white", mew=0.4), 5: dict(marker="o", ms=2.0, mfc="#555", mec="none")}
for r in range(6):
    g = lug[lug["rank"] == r]
    gr = g[g.riber & g.pe & (r >= 3)]
    fr.ax.plot(g.geometry.x, g.geometry.y, ls="none", zorder=25 - r * 0.1, **STY[r])
    if len(gr):
        fr.ax.plot(gr.geometry.x, gr.geometry.y, ls="none", marker="o", ms=STY[r]["ms"] + 2.6, mfc="none", mec="#1565c0", mew=0.9, zorder=24.9)
    for p in g.geometry: fr.labels.obstacle(p.x, p.y, STY[r]["ms"] * PT * 0.5)

# ------------------------------------------------ recuadros (reservar espacio)
L = fr.labels

# ------------------------------------------------ rótulos
for g, n in zip(paises.geometry, paises.name):
    gi = g.difference(peru_g).intersection(fr.bbox)
    if gi.area > 1e8:
        p = polylabel(max(getattr(gi, "geoms", [gi]), key=lambda a: a.area), 500)
        L.place(p.x, p.y, n.upper(), size=28, weight="bold", color="#6b6b6b", spacing=1, h=2.5, offsets=[(0, 0), (0, 40), (0, -40), (60, 0), (-60, 0)], force=True)
for row in pext.itertuples():
    gi = row.geometry.difference(peru_g).intersection(fr.bbox)
    if gi.area > 3e8:
        p = polylabel(max(getattr(gi, "geoms", [gi]), key=lambda a: a.area), 500)
        L.place(p.x, p.y, f"Provincia de {row.name}", size=10, style="italic", color="#666", h=1.8, offsets=[(0, 0), (0, 25), (0, -25)])
L.place(*TO_UTM.transform(-77.9, -3.25), "PERÚ", size=28, weight="bold", color="#555", spacing=1, h=2.5, offsets=[(0, 0), (0, -30), (40, 0)], force=True)
for n, (lo, la) in PUERTOS.items():
    X, Y = TO_UTM.transform(lo, la)
    L.place(X, Y, f"PUERTO {n.upper()}", size=11, weight="bold", color="#0d3c8c", h=2.4, offsets=ring(12), force=True)
for n, (lo, la) in PSEC.items():
    X, Y = TO_UTM.transform(lo, la)
    L.place(X, Y, n, size=8.6, weight="bold", color="#0d3c8c", h=2.0, offsets=ring(8), force=True)
for i, (p, n) in enumerate(xw):
    L.place(p.x, p.y, f"Cruce fluvial\n{n or 's/n'}", size=7.2, weight="bold", color="#0d47a1", h=2, linespacing=1.0, offsets=ring(9), force=True)
for i, (p, n) in enumerate(xr):
    lo, la = TO_LL.transform(p.x, p.y)
    L.place(p.x, p.y, f"Cruce vial/sendero\n{abs(la):.4f}° S {abs(lo):.4f}° W", size=6.4, weight="bold", color="#b71c1c", h=2, linespacing=1.0, offsets=ring(8))
for r, (sz, wt) in {0: (12, "bold"), 1: (9.4, "semibold"), 2: (7.2, "medium")}.items():
    for row in lug[lug["rank"] == r].sort_values("pop", ascending=False).itertuples():
        if row.name in PUERTOS or row.name in PSEC: continue
        L.place(row.geometry.x, row.geometry.y, row.name.upper() if r == 0 else row.name, size=sz, weight=wt, offsets=ring(6), h=1.8,
                force=row.pe and r < 2, shrink=(sz * 0.85,))
for row in dep.itertuples():
    gi = row.geometry.intersection(fr.bbox)
    if gi.area < 2e9: continue
    p = polylabel(max(getattr(gi, "geoms", [gi]), key=lambda a: a.area), 1000)
    L.place(p.x, p.y, nombre(row.departamento).upper(), size=24, weight="bold", color="#4a4a4a", spacing=1, h=2.6, alpha=0.7,
            offsets=[(0, 0), (0, 40), (0, -40), (0, 80), (0, -80), (60, 0), (-60, 0)], force=True)
for row in circ.itertuples():
    gi = row.geometry.intersection(fr.bbox)
    if gi.area < 2e9: continue
    p = polylabel(max(getattr(gi, "geoms", [gi]), key=lambda a: a.area), 1000)
    L.place(p.x, p.y, row.circ, size=13, weight="bold", color=C["tarapoto"] if row.circ == "IA TARAPOTO" else C["circ"], h=2.4,
            offsets=[(0, -60), (0, 60), (0, -120), (0, 120), (50, 0), (-50, 0), (0, 0)])
for row in prov.itertuples():
    gi = row.geometry.intersection(fr.bbox)
    if gi.area < 1e8: continue
    p = polylabel(max(getattr(gi, "geoms", [gi]), key=lambda a: a.area), 300)
    L.place(p.x, p.y, nombre(row.provincia).upper(), size=12 if tara.contains(p) else 9, weight="semibold", color="#3d3d3d", h=2,
            offsets=[(0, 0), (0, 16), (0, -16), (22, 0), (-22, 0), (0, 32), (0, -32)], inside=gi, shrink=(10,))
dist["in_t"] = dist.geometry.representative_point().within(tara)
for row in dist.sort_values("in_t", ascending=False).itertuples():
    gi = row.geometry.intersection(fr.bbox)
    if gi.is_empty or gi.area < 4e6: continue
    p = polylabel(max(getattr(gi, "geoms", [gi]), key=lambda a: a.area), 200)
    L.place(p.x, p.y, nombre(row.distrito), size=7.6 if row.in_t else 6.2, style="italic", color="#4f3a66" if row.in_t else "#7b7b7b", h=1.4,
            inside=gi, offsets=[(0, 0), (0, 9), (0, -9), (12, 0), (-12, 0), (0, 18), (0, -18)], shrink=(6.6, 5.8))
rn = rios[rios.clase.isin(["hidrovia", "navegable", "rio"]) & rios.name.notna()]
for cl, (sz, ev) in {"hidrovia": (13, 120), "navegable": (10.5, 110), "rio": (7.2, 110)}.items():
    g = rn[rn.clase == cl]
    along_labels(fr, [(n, list(x.geometry)) for n, x in g.groupby("name")], ev, sz, "#0d3c8c" if cl != "rio" else C["agua_txt"],
                 weight="bold" if cl != "rio" else "normal", family="Liberation Serif", min_len_mm=15 if cl != "rio" else 25, h=2)
shields(fr, vp, "nacional", C["nacional"], "white", every_mm=80, size=6.8)
shields(fr, vp, "departamental", "#ffd08a", "#4a2b00", every_mm=90, size=6.0, min_len_mm=20)
for row in pd.concat([pts[pts.clase.isin(["peaje", "control", "frontera", "sunat", "aerodromo", "puerto", "helipuerto", "policia"])], mil]).itertuples():
    if not isinstance(row.name, str): continue
    col = {"aerodromo": "#0b3d91", "puerto": "#0b5394", "sunat": "#0d47a1", "peaje": "#5d4a00", "frontera": "#9b1c1c", "militar": "#4e342e"}.get(row.clase, "#333")
    L.place(row.geometry.x, row.geometry.y, row.name, size=6.6, color=col, offsets=ring(5.5), h=1.6)
for row in anp.itertuples():
    gi = row.geometry.intersection(fr.bbox)
    if gi.area < 1e8: continue
    p = polylabel(max(getattr(gi, "geoms", [gi]), key=lambda a: a.area), 500)
    L.place(p.x, p.y, row.name, size=8, style="italic", color="#2e6b2e", h=1.6, inside=gi, offsets=[(0, 0), (0, 14), (0, -14), (0, 28)])
for r, sz in [(3, 7.0), (4, 6.4), (5, 5.6)]:
    g = lug[(lug["rank"] == r)]
    for row in g.sort_values(["riber", "pop"], ascending=[False, False]).itertuples():
        L.place(row.geometry.x, row.geometry.y, row.name, size=sz, color="#0d3c8c" if row.riber and row.pe else ("#333" if row.pe else "#777"),
                weight="medium" if row.riber else "normal", offsets=ring(4), h=1.4)
fr.frame(step_deg=0.5, utm_km=50)

# ------------------------------------------------ cabecera
bg.add_patch(Rectangle((15, 1100), 811, 77, fc="#1d2b45", ec="none"))
bg.text(27, 1164, "SUPERINTENDENCIA NACIONAL DE ADUANAS Y DE ADMINISTRACIÓN TRIBUTARIA · INTENDENCIA DE ADUANA DE TARAPOTO",
        fontsize=10.5, color="#c9d3e6", weight="semibold", va="center")
bg.text(27, 1140, "FRONTERA NORTE Y RED FLUVIAL: DE CONDORCANQUI AL DATEM DEL MARAÑÓN", fontsize=27, color="white", weight="bold", va="center", family="Inter Display")
bg.text(27, 1116, "Ríos Santiago, Cenepa, Morona, Pastaza, Marañón y Huallaga · puertos, embarcaderos, poblados ribereños y cruces de frontera",
        fontsize=15, color="#e3e8f2", va="center")
bg.text(814, 1164, "MAPA 3 / 3", fontsize=14, color="white", weight="bold", ha="right", va="center")
bg.text(814, 1140, "Escala 1:550 000", fontsize=13, color="#e3e8f2", ha="right", va="center")
bg.text(814, 1116, "Octubre 2026", fontsize=12, color="#c9d3e6", ha="right", va="center")

# ------------------------------------------------ panel inferior: recuadros de puertos
P0, P1 = 12, 276
bg.add_patch(Rectangle((15, P0), 811, P1 - P0, fc="white", ec="k", lw=0.8))
def zoom(rect, center_ll, title, scale=50_000):
    x, y, w, h = rect
    ov.add_patch(Rectangle((x, y + h), w, 8, fc="#0d3c8c", ec="none", zorder=5))
    ov.text(x + 2.5, y + h + 4, title, fontsize=7.8, color="white", weight="bold", va="center", zorder=6)
    f2 = MapFrame(fig, rect, TO_UTM.transform(*center_ll), scale, zorder=55)
    bb = f2.clipbox(0.1)
    f2.relief(res=8, land=land, exag=1.0, shade=(0.78, 0.25))
    ag = f2.load("agua_poly"); rr = f2.load("rios")
    f2.polys(list(ag.geometry), fc=C["agua"], ec=C["agua_lin"], lw=0.3, z=3)
    for cl, lw in {"quebrada": 0.5, "canal": 0.6, "rio": 1.2, "navegable": 2.4, "hidrovia": 3.4}.items():
        f2.lines(list(rr[rr.clase == cl].geometry), color=C["agua_lin"], lw=lw, z=3.3)
    ds = dist[dist.intersects(bb)]
    f2.lines(list(ds.geometry.boundary), color="#444", lw=0.9, ls=(0, (4, 2)), z=6)
    vv = f2.load("vias"); ss = sen[sen.intersects(bb)]
    f2.lines(list(ss[ss.highway.notna()].geometry), color="#8d6e63", lw=0.7, ls=(0, (1.2, 1.4)), z=9.6)
    for cl, (col, lw) in {"trocha": (C["trocha"], 0.9), "vecinal": (C["vecinal"], 1.2), "departamental": (C["departamental"], 1.9), "nacional": (C["nacional"], 2.5)}.items():
        f2.lines(list(vv[vv.clase == cl].geometry), color=col, lw=lw, z=10, ls=(0, (3, 1.6)) if cl == "trocha" else "-")
    pp = f2.load("puntos"); pp = pp[pp.geometry.within(f2.bbox)]
    draw_points(f2, pp[pp.clase.isin(["peaje", "control", "frontera", "sunat", "aerodromo", "puerto", "policia", "grifo", "helipuerto", "municipalidad"])])
    lg_ = f2.load("lugares"); lg_ = lg_[lg_.geometry.within(f2.bbox)]
    f2.ax.plot(lg_.geometry.x, lg_.geometry.y, ls="none", marker="o", ms=3.4, mfc="#222", mec="white", mew=0.5, zorder=25)
    for p in lg_.geometry: f2.labels.obstacle(p.x, p.y, 0.8)
    for row in pp.itertuples():
        if isinstance(row.name, str): f2.labels.place(row.geometry.x, row.geometry.y, row.name, size=6.2, color="#333", offsets=ring(6), h=1.6)
    for row in lg_.sort_values("cap").itertuples():
        f2.labels.place(row.geometry.x, row.geometry.y, row.name, size=7.6 if row.cap == row.cap else 6.4, weight="bold" if row.cap == row.cap else "normal",
                        color="#222", offsets=ring(4), h=1.6)
    rn2 = rr[rr.name.notna() & rr.clase.isin(["rio", "navegable", "hidrovia"])]
    along_labels(f2, [(n, list(x.geometry)) for n, x in rn2.groupby("name")], 70, 8, "#0d3c8c", family="Liberation Serif", weight="bold", min_len_mm=12)
    f2.ax.add_patch(Rectangle((f2.x0, f2.y0), f2.x1 - f2.x0, f2.y1 - f2.y0, fill=False, ec="#222", lw=1.2, zorder=60))
    sb = 2000 * 1e3 / scale
    ov.add_patch(Rectangle((x + 3, y + 3), 62, 9.5, fc="white", ec="none", alpha=0.85, zorder=7))
    ov.text(x + 5, y + 9.6, f"Escala 1:{scale:,.0f}".replace(",", " "), fontsize=6.4, zorder=8, va="center")
    for i in range(4):
        ov.add_patch(Rectangle((x + 5 + i * sb / 2, y + 4.5), sb / 2, 1.8, fc="#222" if i % 2 == 0 else "white", ec="#222", lw=0.4, zorder=8))
    ov.text(x + 7 + 2 * sb, y + 5.4, "2 km", fontsize=6.0, zorder=8, va="center")
    rx0, ry0 = fr.mm(f2.x0, f2.y0); rx1, ry1 = fr.mm(f2.x1, f2.y1)
    ov.add_patch(Rectangle((rx0, ry0), rx1 - rx0, ry1 - ry0, fill=False, ec="#0d3c8c", lw=1.4, zorder=4))
    ov.text(rx1 + 1, ry1 + 1, title.split("·")[0].strip(), fontsize=7, weight="bold", color="#0d3c8c", zorder=4, path_effects=halo(1.6))

ZW, ZH, ZY = 195, 150, P1 - 162
zoom((20, ZY, ZW, ZH), (-77.4175, -4.564), "ZOOM A · Puerto de Saramiriza – río Marañón")
zoom((221, ZY, ZW, ZH), (-76.5546, -4.8316), "ZOOM B · Puerto de San Lorenzo – río Marañón")
zoom((422, ZY, ZW, ZH), (-77.7583, -4.0151), "ZOOM C · Puerto Galilea – río Santiago")
zoom((623, ZY, ZW, ZH), (-76.1047, -5.8952), "ZOOM D · Puerto de Yurimaguas – río Huallaga")

# leyenda
LY = ZY - 6
lg = Legend(bg, 20, LY, 170, row=7.6, size=8.4)
lg.header("Frontera y control")
lg.line("Límite internacional Perú – Ecuador", C["frontera"], 2.2, ls=(0, (6, 1.5, 1.2, 1.5)), under=("#d9534f", 7, 0.28))
lg.marker("Cruce vial o de sendero con la frontera (OSM)", marker="D", ms=7, mfc="#ffeb3b", mec="#b71c1c", mew=1.4)
lg.marker("Cruce fluvial de la frontera", marker="o", ms=8, mfc="white", mec="#0d47a1", mew=1.8)
lg.marker("Control fronterizo / Migraciones / SUNAT", marker="h", ms=6.4, mfc="#c62828", mec="white", mew=0.7)
lg.marker("Puesto de control / vigilancia (OSM)", marker="^", ms=5.4, mfc="#ef5350", mec="#3b0000", mew=0.6)
lg.marker("Puesto o base militar en territorio peruano (OSM)", marker="P", ms=6, mfc="#4e342e", mec="white", mew=0.6)
lg2 = Legend(bg, 205, LY, 170, row=7.6, size=8.4)
lg2.header("Red fluvial")
lg2.line("Vía navegable principal (Hidrovía Amazónica)", "#1565c0", 3.0, casing=("white", 4.4))
lg2.line("Río navegable por embarcaciones menores", "#1565c0", 1.9, casing=("white", 3.3))
lg2.line("Río / quebrada", C["agua_lin"], 0.8)
lg2.line("Ruta de transbordo / ferry (OSM)", "#0d47a1", 0.9, ls=(0, (4, 2)))
lg2.marker("Puerto fluvial principal", marker="o", ms=11, mfc="#0d47a1", mec="white", mew=1.4)
lg2.marker("Puerto / embarcadero secundario", marker="o", ms=8, mfc="#0d47a1", mec="white", mew=1.2)
lg2.marker("Poblado ribereño (a < 1,5 km de río navegable)", marker="o", ms=5.5, mfc="#444", mec="#1565c0", mew=1.0)
lg3 = Legend(bg, 390, LY, 170, row=7.6, size=8.4)
lg3.header("Vías y límites")
lg3.line("Red vial nacional / departamental", C["nacional"], 2.0, casing=("#5a0010", 2.8))
lg3.line("Red vial vecinal / trocha", C["vecinal"], 0.8)
lg3.line("Sendero / camino peatonal (OSM)", "#8d6e63", 0.6, ls=(0, (1.2, 1.4)))
lg3.line("Circunscripción IA Tarapoto / otras IA", C["tarapoto"], 2.2, under=(C["tarapoto"], 7, 0.25))
lg3.line("Límite departamental / provincial", C["dep"], 1.5, ls=(0, (5, 1.5, 1, 1.5)))
lg3.line("Límite distrital (referencial INEI)", C["dist"], 0.5, ls=(0, (2, 1.4)))
lg3.box("Área natural protegida", fc="#e3efe3", ec=C["anp"], lw=0.8, ls=(0, (1.5, 1.2)))

X = 580
north_arrow(bg, 808, LY - 22, s=12)
bg.text(X, LY, "ESCALA GRÁFICA", fontsize=7.4, weight="bold", va="center")
scale_bar(bg, X + 10, LY - 13, SCALE, 50, 10)
info = ("WGS 84 · UTM Zona 18 Sur (EPSG:32718) · Escala 1:550 000 · A0 vertical\n"
        "Todo el territorio peruano representado pertenece a la ZTE (Ley N.° 27037, art. 3).\n"
        "Ríos, puertos, poblados, vías, senderos, cruces y puntos de control: © OpenStreetMap (30.10.2026).\n"
        "Cruces de frontera: intersección de vías/senderos/ríos OSM con el límite INEI (referencial).\n"
        "Límites: INEI 2019 (referenciales). Relieve: AWS Terrain Tiles.\n"
        "Capa opcional de casos por distrito: pendiente de datos agregados del equipo.\n"
        "Elaborado por: Equipo de Gestión de Riesgo – IA Tarapoto")
bg.text(X, LY - 22, info, fontsize=6.1, va="top", linespacing=1.4, color="#222")

if not NOPDF: fig.savefig(OUT + ".pdf")
fig.savefig(OUT + ".png", dpi=DPI)
print("ok", OUT, "cruces viales", len(xr), "fluviales", len(xw), [n for _, n in xw])
