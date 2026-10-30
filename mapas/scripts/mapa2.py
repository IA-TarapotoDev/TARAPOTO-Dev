# MAPA 2 – Corredores de salida de mercancías de la ZTE hacia la ZTC (A0 vertical, 1:1 000 000)
import sys
sys.path.insert(0, "/home/user/mapas_scripts")
from carto import *
from shapely.ops import substring
import textwrap

OUT = sys.argv[1] if len(sys.argv) > 1 else "/home/user/TARAPOTO-Dev/mapas/Mapa2_Corredores_ZTE_ZTC"
DPI = int(sys.argv[2]) if len(sys.argv) > 2 else 300
NOPDF = len(sys.argv) > 3
SCALE = 1_000_000
fig, bg = page()
fr = MapFrame(fig, (15, 212, 811, 880), (332_000, 9_211_500), SCALE)
CB = fr.clipbox(0.05)

circ = gpd.read_file(f"{U}/circunscripciones.gpkg"); reg = gpd.read_file(f"{U}/regimen.gpkg"); peru = gpd.read_file(f"{U}/peru.gpkg")
paises = gpd.read_file(f"{U}/paises.gpkg"); pext = gpd.read_file(f"{U}/prov_extranjeras.gpkg")
dist = gpd.read_file(f"{U}/distritos_tematico.gpkg"); prov = fr.load("provincias"); dep = fr.load("departamentos")
peru_g = peru.geometry.iloc[0]; tara = circ[circ.circ == "IA TARAPOTO"].geometry.iloc[0]
zte = reg[reg.regimen == "ZTE"].geometry.iloc[0]
ext = [g.difference(peru_g) for g in paises.geometry]; land = [peru_g] + ext
COR = json.load(open("/home/user/data_base/corredores.json"))
CCOL = {"OESTE": "#1546c4", "SUROESTE": "#7b1fa2", "SUR": "#00796b", "FLUVIAL": "#0277bd"}
CNOM = {"OESTE": "Corredor Oeste: Bagua/Jaén → Olmos/Chiclayo", "SUROESTE": "Corredor Suroeste: Chachapoyas → Balsas → Celendín → Cajamarca",
        "SUR": "Corredor Sur: Tocache → Tingo María → Huánuco → Ambo → Pasco", "FLUVIAL": "Corredor Fluvial: Iquitos → Yurimaguas"}

# ------------------------------------------------ geometrías de corredores, tramos y puntos asociados
pts_all = gpd.read_file(f"{U}/puntos.gpkg")
corr = {}
for k, c in COR.items():
    ln = gpd.GeoSeries([LineString(c["coords"])], crs=4326).to_crs(32718).iloc[0]
    f = c["km_total"] * 1000 / ln.length
    segs = [(substring(ln, s["desde_km"] * 1000 / f, s["hasta_km"] * 1000 / f), s["regimen"]) for s in c["segmentos"]]
    # circunscripciones recorridas
    cir = []
    for row in circ.itertuples():
        g = ln.intersection(row.geometry)
        if g.length > 300:
            parts = sorted(getattr(g, "geoms", [g]), key=lambda s: ln.project(Point(s.coords[0])))
            for s in parts:
                a, b = sorted([ln.project(Point(s.coords[0])), ln.project(Point(s.coords[-1]))])
                if b - a > 300: cir.append((a * f / 1000, b * f / 1000, row.circ))
    cir.sort()
    # puntos operativos a < 400 m de la vía (grifos/policía a < 250 m)
    near = pts_all[pts_all.clase.isin(["peaje", "pesaje", "control", "sunat", "frontera", "policia", "grifo", "puerto"])].copy()
    near["d"] = near.distance(ln)
    near = near[(near.d < 400) & ~((near.clase.isin(["grifo", "policia"])) & (near.d > 250))].copy()
    near["km"] = [ln.project(p) * f / 1000 for p in near.geometry]
    corr[k] = dict(line=ln, f=f, segs=segs, cir=cir, pts=near.sort_values("km"), data=c)

# ------------------------------------------------ fondo
veil_ext = [g.intersection(CB) for g in ext]
fr.relief(res=100, land=land, veil=veil_ext, veil_alpha=0.55)
fr.polys([zte.intersection(CB)], fc=C["zte"], alpha=0.13, z=1.2)
agua = fr.load("agua_poly"); rios = fr.load("rios"); hum = fr.load("humedales")
fr.polys(list(agua.geometry), fc=C["agua"], ec=C["agua_lin"], lw=0.12, z=3)
W = {"quebrada": (0.15, 0.45), "canal": (0.25, 0.6), "rio": (0.45, 0.9), "navegable": (1.0, 1), "hidrovia": (1.8, 1)}
for cl in W:
    fr.lines(list(rios[rios.clase == cl].geometry), color=C["agua_lin"], lw=W[cl][0], alpha=W[cl][1], z=3.2 + 0.1 * list(W).index(cl))
zclip = fr.clip_patch(zte.intersection(CB)); fr.ax.add_patch(zclip)
fr.lines([zte.intersection(CB).boundary], color=C["zte"], lw=10, alpha=0.35, z=4.6, clip=zclip, cap="butt")
fr.lines([zte.intersection(CB).boundary.difference(peru_g.boundary.buffer(800))], color=C["zte"], lw=1.6, z=4.7)
dd = dist[dist.intersects(fr.bbox)]
fr.lines(list(dd.geometry.boundary), color=C["dist"], lw=0.25, ls=(0, (2, 1.6)), z=6, alpha=0.8)
fr.lines(list(prov.geometry.boundary), color=C["prov"], lw=0.65, ls=(0, (5, 2.2)), z=6.5)
fr.lines(list(dep.geometry.boundary), color=C["dep"], lw=1.3, ls=(0, (8, 2.5, 1.5, 2.5)), z=7)
cb = unary_union([g.boundary for g in circ.geometry]).difference(peru_g.boundary.buffer(800))
fr.lines([cb.intersection(CB)], color=C["circ"], lw=1.9, ls=(0, (7, 3)), z=8)
fr.lines([tara.boundary], color=C["tarapoto"], lw=2.0, z=8.4)
fr.lines(list(pext.geometry.boundary), color="#6a6a6a", lw=0.6, ls=(0, (5, 2.5)), z=6.5)
fr.lines([peru_g.boundary.intersection(CB)], color="#d9534f", lw=4.5, alpha=0.25, z=9)
fr.lines([peru_g.boundary.intersection(CB)], color=C["frontera"], lw=1.7, ls=(0, (10, 2.5, 2, 2.5, 2, 2.5)), z=9.2)
vias = fr.load("vias"); vx = vias[~vias.pe]; vias = vias[vias.pe]
fr.lines(list(vx.geometry), color="#9a9a9a", lw=0.4, z=10)
fr.lines(list(vias[vias.clase == "trocha"].geometry), color=C["trocha"], lw=0.35, ls=(0, (3, 1.6)), z=10, alpha=0.8)
fr.lines(list(vias[vias.clase == "vecinal"].geometry), color=C["vecinal"], lw=0.45, z=10.5, alpha=0.85)
fr.lines(list(vias[vias.clase == "departamental"].geometry), color=C["departamental"], lw=0.95, z=11)
fr.lines(list(vias[vias.clase == "nacional"].geometry), color="#5a0010", lw=2.0, z=12, cap="butt")
fr.lines(list(vias[vias.clase == "nacional"].geometry), color=C["nacional"], lw=1.4, z=12.1)

# ------------------------------------------------ corredores
for k, c in corr.items():
    col = CCOL[k]
    fluv = k == "FLUVIAL"
    for g, rg in c["segs"]:
        fr.lines([g], color="white", lw=8.2, z=13, cap="butt")
        if rg == "ZTE":
            fr.lines([g], color=col, lw=6.0, z=13.2, ls=(0, (4, 1.2)) if fluv else "-")
        else:
            fr.lines([g], color=col, lw=6.0, z=13.2)
            fr.lines([g], color="white", lw=2.2, z=13.3, ls=(0, (3, 3)))
    ln, f = c["line"], c["f"]
    # marcas de kilometraje
    step = 25 if not fluv else 50
    for km in np.arange(step, c["data"]["km_total"], step):
        d = km * 1000 / f; p = ln.interpolate(d); a = ln.interpolate(max(0, d - 1500)); b = ln.interpolate(min(ln.length, d + 1500))
        ang = math.atan2(b.y - a.y, b.x - a.x) + math.pi / 2
        L_ = 4.2 * fr.m_pt
        fr.ax.plot([p.x - L_ * math.cos(ang), p.x + L_ * math.cos(ang)], [p.y - L_ * math.sin(ang), p.y + L_ * math.sin(ang)],
                   color="#111", lw=1.0, zorder=13.5)
        if km % (2 * step) == 0:
            fr.labels.place(p.x, p.y, f"km {km:.0f}", size=6.0, weight="bold", color=col, h=1.6,
                            offsets=[(7 * math.cos(ang), 7 * math.sin(ang)), (-7 * math.cos(ang), -7 * math.sin(ang))])

# ------------------------------------------------ puntos de salida de la ZTE (salida definitiva) y origen/destino
EXITS = {}
for k, c in corr.items():
    ex = c["data"]["salidas"]
    if ex:
        e = ex[-1]  # salida definitiva
        X, Y = TO_UTM.transform(e["lon"], e["lat"]); EXITS[k] = (X, Y, e)
        fr.ax.plot([X], [Y], marker="o", ms=15, mfc="white", mec=C["salida"], mew=2.4, zorder=28)
        fr.ax.plot([X], [Y], marker="x", ms=8, mec=C["salida"], mew=2.4, zorder=28.1)
        fr.labels.obstacle(X, Y, 4)

# ------------------------------------------------ otros puntos
pts = fr.load("puntos"); pts = pts[pts.geometry.within(fr.bbox)]
ptsv = pd.concat([c["pts"] for c in corr.values()])
draw_points(fr, pts[pts.clase.isin(["peaje", "pesaje", "control", "frontera", "sunat", "aerodromo", "puerto"])])
draw_points(fr, ptsv[ptsv.clase.isin(["grifo", "policia"])])

lug = fr.load("lugares"); lug = lug[lug.geometry.within(fr.bbox) & lug.pe].copy()
lug["rank"] = np.select([lug.cap == 4, lug.cap == 6, lug.cap == 8, lug.place.isin(["city", "town"])], [0, 1, 2, 3], 5)
STY = {0: dict(marker="s", ms=6.5, mfc="white", mec="black", mew=1.3), 1: dict(marker="o", ms=5.4, mfc="white", mec="black", mew=1.2),
       2: dict(marker="o", ms=3.0, mfc="#222", mec="white", mew=0.4), 3: dict(marker="o", ms=2.6, mfc="#444", mec="white", mew=0.4)}
for r in range(4):
    g = lug[lug["rank"] == r]
    fr.ax.plot(g.geometry.x, g.geometry.y, ls="none", zorder=25 - r * 0.1, **STY[r])
    for p in g.geometry: fr.labels.obstacle(p.x, p.y, STY[r]["ms"] * PT * 0.5)

# ------------------------------------------------ recuadros de zoom (posiciones en mm de página)
INSETS = {"OESTE": (20, 918, 165, 160), "SUROESTE": (20, 395, 165, 160), "SUR": (656, 217, 165, 160), "FLUVIAL": (656, 395, 165, 160)}
for r in INSETS.values():
    fr.labels.add_box((r[0] - 2, r[1] - 2, r[0] + r[2] + 2, r[1] + r[3] + 9))
TABLE_BOX = (20, 217, 330, 160)

# ------------------------------------------------ rótulos principales
L = fr.labels
for k, c in corr.items():
    for s in c["data"]["paradas"]:
        if k == "OESTE" and s["nombre"] == "Puente Boliche": pass
        d = s["km"] * 1000 / c["f"]; p = c["line"].interpolate(min(d, c["line"].length))
        fr.ax.plot([p.x], [p.y], marker="o", ms=7.5, mfc=CCOL[k], mec="white", mew=1.4, zorder=27)
        L.obstacle(p.x, p.y, 2.2)
for k, c in corr.items():
    for s in c["data"]["paradas"]:
        d = s["km"] * 1000 / c["f"]; p = c["line"].interpolate(min(d, c["line"].length))
        L.place(p.x, p.y, f"{s['nombre']}\nkm {s['km']:.1f}", size=8.6, weight="bold", color=CCOL[k], h=2.2, linespacing=1.0,
                offsets=ring(8), force=True)
for k, (X, Y, e) in EXITS.items():
    L.place(X, Y, f"SALIDA DE LA ZTE\nkm {e['km']:.1f}", size=9.4, weight="bold", color=C["salida"], h=2.4, linespacing=1.0,
            offsets=ring(11), force=True)
for r, (sz, wt) in {0: (11, "bold"), 1: (8.4, "semibold"), 2: (6.0, "medium"), 3: (5.6, "normal")}.items():
    for row in lug[lug["rank"] == r].sort_values("pop", ascending=False).itertuples():
        L.place(row.geometry.x, row.geometry.y, row.name.upper() if r == 0 else row.name, size=sz, weight=wt, offsets=ring(6 if r < 2 else 4), h=1.8,
                force=r < 2, shrink=(sz * 0.85,) if r < 2 else ())
for g, n in zip(paises.geometry, paises.name):
    gi = g.difference(peru_g).intersection(fr.bbox)
    if gi.area > 1e8:
        p = polylabel(max(getattr(gi, "geoms", [gi]), key=lambda a: a.area), 500)
        L.place(p.x, p.y, n.upper(), size=22, weight="bold", color="#6b6b6b", spacing=1, h=2.5, offsets=[(0, 0), (0, 40), (0, -40), (60, 0), (-60, 0)])
for row in dep.itertuples():
    gi = row.geometry.intersection(fr.bbox)
    if gi.area < 3e9: continue
    p = polylabel(max(getattr(gi, "geoms", [gi]), key=lambda a: a.area), 1000)
    L.place(p.x, p.y, nombre(row.departamento).upper(), size=19, weight="bold", color="#4a4a4a", spacing=1, h=2.6, alpha=0.7,
            offsets=[(0, 0), (0, 40), (0, -40), (0, 80), (0, -80), (50, 0), (-50, 0), (0, 120), (0, -120)], shrink=(15,))
for row in circ.itertuples():
    gi = row.geometry.intersection(fr.bbox)
    if gi.area < 3e9: continue
    p = polylabel(max(getattr(gi, "geoms", [gi]), key=lambda a: a.area), 1000)
    L.place(p.x, p.y, row.circ, size=12, weight="bold", color=C["tarapoto"] if row.circ == "IA TARAPOTO" else C["circ"], h=2.4,
            offsets=[(0, -50), (0, 50), (0, -100), (0, 100), (50, 0), (-50, 0), (0, 0)])
for row in prov.itertuples():
    gi = row.geometry.intersection(fr.bbox)
    if gi.area < 1e8: continue
    p = polylabel(max(getattr(gi, "geoms", [gi]), key=lambda a: a.area), 300)
    L.place(p.x, p.y, nombre(row.provincia).upper(), size=7.2, weight="semibold", color="#5a5a5a", h=1.6, inside=gi,
            offsets=[(0, 0), (0, 12), (0, -12), (16, 0), (-16, 0)])
rn = rios[rios.clase.isin(["hidrovia", "navegable", "rio"]) & rios.name.notna()]
for cl, (sz, ev) in {"hidrovia": (9.5, 140), "navegable": (7.5, 130), "rio": (6.0, 130)}.items():
    g = rn[rn.clase == cl]
    along_labels(fr, [(n, list(x.geometry)) for n, x in g.groupby("name")], ev, sz, C["agua_txt"], weight="bold" if cl != "rio" else "normal",
                 family="Liberation Serif", min_len_mm=18 if cl != "rio" else 35)
shields(fr, vias, "nacional", C["nacional"], "white", every_mm=80, size=6.0)
shields(fr, vias, "departamental", "#ffd08a", "#4a2b00", every_mm=110, size=5.2, min_len_mm=30)
ptsl = pd.concat([pts[pts.clase.isin(["peaje", "pesaje", "control", "frontera", "sunat"])], ptsv[ptsv.clase.isin(["grifo", "policia"])]])
for row in ptsl.itertuples():
    if not isinstance(row.name, str): continue
    col = {"sunat": "#0d47a1", "peaje": "#5d4a00", "frontera": "#9b1c1c", "control": "#9b1c1c", "grifo": "#4a148c", "policia": "#0d47a1"}.get(row.clase, "#333")
    L.place(row.geometry.x, row.geometry.y, row.name, size=5.8 if row.clase not in ("grifo", "policia") else 5.0, color=col, offsets=ring(5), h=1.4)
fr.frame(step_deg=1.0, utm_km=100)

# ------------------------------------------------ recuadros de zoom
def inset(rect, k, title, center=None, scale=60_000, extra=""):
    x, y, w, h = rect
    c = corr[k]
    if center is None: center = EXITS[k][:2]
    bg = fig.ov
    bg.add_patch(Rectangle((x - 1.2, y - 1.2), w + 2.4, h + 10.4, fc="none", ec="#222", lw=0.8, zorder=50))
    bg.add_patch(Rectangle((x, y + h), w, 8, fc=CCOL[k], ec="none", zorder=51))
    bg.text(x + 2.5, y + h + 4, title, fontsize=7.6, color="white", weight="bold", va="center", zorder=52)
    f2 = MapFrame(fig, rect, center, scale, zorder=55)
    bb = f2.clipbox(0.1)
    f2.relief(res=8, land=[peru_g] + ext, tint=True, exag=1.0, shade=(0.78, 0.25))
    f2.polys([zte.intersection(bb)], fc=C["zte"], alpha=0.16, z=1.2)
    zc = f2.clip_patch(zte.intersection(bb)); f2.ax.add_patch(zc)
    f2.lines([zte.intersection(bb).boundary], color=C["zte"], lw=9, alpha=0.35, z=4.6, clip=zc, cap="butt")
    f2.lines([zte.intersection(bb).boundary], color=C["zte"], lw=1.6, z=4.7)
    ag = f2.load("agua_poly"); rr = f2.load("rios")
    f2.polys(list(ag.geometry), fc=C["agua"], ec=C["agua_lin"], lw=0.3, z=3)
    for cl, lw in {"quebrada": 0.5, "canal": 0.6, "rio": 1.1, "navegable": 2.2, "hidrovia": 3.2}.items():
        f2.lines(list(rr[rr.clase == cl].geometry), color=C["agua_lin"], lw=lw, z=3.3)
    ds = dist[dist.intersects(bb)]
    f2.lines(list(ds.geometry.boundary), color="#444", lw=0.9, ls=(0, (4, 2)), z=6)
    vv = f2.load("vias")
    for cl, (col, lw) in {"trocha": (C["trocha"], 0.8), "vecinal": (C["vecinal"], 1.1), "departamental": (C["departamental"], 1.8), "nacional": (C["nacional"], 2.4)}.items():
        f2.lines(list(vv[vv.clase == cl].geometry), color=col, lw=lw, z=10, ls=(0, (3, 1.6)) if cl == "trocha" else "-")
    for g, rg in c["segs"]:
        g = g.intersection(bb)
        f2.lines([g], color="white", lw=9, z=13, cap="butt")
        f2.lines([g], color=CCOL[k], lw=6.5, z=13.1, ls=(0, (4, 1.2)) if k == "FLUVIAL" else "-")
        if rg == "ZTC": f2.lines([g], color="white", lw=2.4, z=13.2, ls=(0, (3, 3)))
    ln, ff = c["line"], c["f"]
    for km in np.arange(0, c["data"]["km_total"], 1.0):
        p = ln.interpolate(km * 1000 / ff)
        if not f2.bbox.contains(p): continue
        a = ln.interpolate(max(0, km * 1000 / ff - 150)); b = ln.interpolate(min(ln.length, km * 1000 / ff + 150))
        ang = math.atan2(b.y - a.y, b.x - a.x) + math.pi / 2; L_ = 5.5 * f2.m_pt
        f2.ax.plot([p.x - L_ * math.cos(ang), p.x + L_ * math.cos(ang)], [p.y - L_ * math.sin(ang), p.y + L_ * math.sin(ang)], color="#111", lw=0.9, zorder=13.5)
        f2.labels.place(p.x, p.y, f"{km:.0f}", size=6.2, weight="bold", color="#111", h=1.6,
                        offsets=[(9 * math.cos(ang), 9 * math.sin(ang)), (-9 * math.cos(ang), -9 * math.sin(ang))])
    pp = f2.load("puntos"); pp = pp[pp.geometry.within(f2.bbox)]
    draw_points(f2, pp[pp.clase.isin(["peaje", "pesaje", "control", "frontera", "sunat", "aerodromo", "puerto", "policia", "grifo"])])
    lg_ = f2.load("lugares"); lg_ = lg_[lg_.geometry.within(f2.bbox)]
    f2.ax.plot(lg_.geometry.x, lg_.geometry.y, ls="none", marker="o", ms=3.2, mfc="#222", mec="white", mew=0.5, zorder=25)
    for p in lg_.geometry: f2.labels.obstacle(p.x, p.y, 0.8)
    if k in EXITS:
        X, Y, e = EXITS[k]
        f2.ax.plot([X], [Y], marker="o", ms=17, mfc="white", mec=C["salida"], mew=2.6, zorder=28)
        f2.ax.plot([X], [Y], marker="x", ms=9, mec=C["salida"], mew=2.6, zorder=28.1)
        f2.labels.obstacle(X, Y, 4)
        f2.labels.place(X, Y, f"SALIDA DE LA ZTE · km {e['km']:.1f}\n{abs(e['lat']):.5f}° S  {abs(e['lon']):.5f}° W", size=7.6, weight="bold",
                        color=C["salida"], h=2.2, linespacing=1.1, offsets=ring(14), force=True)
    for row in pp.itertuples():
        if isinstance(row.name, str): f2.labels.place(row.geometry.x, row.geometry.y, row.name, size=6.4, color="#333", offsets=ring(6), h=1.6)
    for row in ds.itertuples():
        gi = row.geometry.intersection(f2.bbox)
        if gi.area < 1e5: continue
        p = polylabel(max(getattr(gi, "geoms", [gi]), key=lambda a: a.area), 30)
        f2.labels.place(p.x, p.y, f"{nombre(row.distrito).upper()}\n({nombre(row.provincia)}) · {row.regimen}", size=7.2, weight="semibold",
                        color=C["zte"] if row.regimen == "ZTE" else "#5b5b5b", h=2, linespacing=1.05,
                        offsets=[(0, 0), (0, 20), (0, -20), (25, 0), (-25, 0), (0, 40), (0, -40)], inside=gi, force=False)
    for row in lg_.itertuples():
        f2.labels.place(row.geometry.x, row.geometry.y, row.name, size=6.6, color="#222", offsets=ring(4), h=1.6)
    rn2 = rr[rr.name.notna() & rr.clase.isin(["rio", "navegable", "hidrovia"])]
    along_labels(f2, [(n, list(x.geometry)) for n, x in rn2.groupby("name")], 90, 7.4, C["agua_txt"], family="Liberation Serif", min_len_mm=15)
    shields(f2, vv, "nacional", C["nacional"], "white", every_mm=70, size=6.4, min_len_mm=10)
    shields(f2, vv, "departamental", "#ffd08a", "#4a2b00", every_mm=70, size=6.0, min_len_mm=10)
    f2.ax.add_patch(Rectangle((f2.x0, f2.y0), f2.x1 - f2.x0, f2.y1 - f2.y0, fill=False, ec="#222", lw=1.2, zorder=60))
    # escala del recuadro
    sb = 2000 * 1e3 / scale  # 2 km en mm
    bg.add_patch(Rectangle((x + 4, y + 4), w * 0.62, 9.5, fc="white", ec="none", alpha=0.85, zorder=70))
    bg.text(x + 6, y + 10.6, f"Escala 1:{scale:,.0f}".replace(",", " ") + extra, fontsize=6.4, zorder=71, va="center")
    for i in range(4):
        bg.add_patch(Rectangle((x + 6 + i * sb / 2, y + 5.5), sb / 2, 1.8, fc="#222" if i % 2 == 0 else "white", ec="#222", lw=0.4, zorder=71))
    bg.text(x + 8 + 2 * sb, y + 6.4, "2 km", fontsize=6.0, zorder=71, va="center")
    # ubicación en el mapa principal
    rx0, ry0 = fr.mm(f2.x0, f2.y0); rx1, ry1 = fr.mm(f2.x1, f2.y1)
    bg.add_patch(Rectangle((rx0, ry0), rx1 - rx0, ry1 - ry0, fill=False, ec=CCOL[k], lw=1.4, zorder=45))
    cxm, cym = (rx0 + rx1) / 2, (ry0 + ry1) / 2
    tx = min(max(cxm, x), x + w); ty = min(max(cym, y), y + h + 9)
    bg.plot([cxm, tx], [cym, ty], color=CCOL[k], lw=1.0, ls=(0, (3, 2)), zorder=44)

inset(INSETS["OESTE"], "OESTE", f"ZOOM 1 · CORREDOR OESTE – salida definitiva de la ZTE (km {EXITS['OESTE'][2]['km']:.1f})")
inset(INSETS["SUROESTE"], "SUROESTE", f"ZOOM 2 · CORREDOR SUROESTE – puente Balsas, río Marañón (km {EXITS['SUROESTE'][2]['km']:.1f})")
inset(INSETS["SUR"], "SUR", f"ZOOM 3 · CORREDOR SUR – salida de la ZTE al sur de Ambo (km {EXITS['SUR'][2]['km']:.1f})")
yx, yy = TO_UTM.transform(-76.0870, -5.8920)
inset(INSETS["FLUVIAL"], "FLUVIAL", "ZOOM 4 · CORREDOR FLUVIAL – puerto de Yurimaguas (km 703)", center=(yx, yy), scale=60_000)

# ------------------------------------------------ cabecera
bg.add_patch(Rectangle((15, 1100), 811, 77, fc="#1d2b45", ec="none"))
bg.text(27, 1164, "SUPERINTENDENCIA NACIONAL DE ADUANAS Y DE ADMINISTRACIÓN TRIBUTARIA · INTENDENCIA DE ADUANA DE TARAPOTO",
        fontsize=10.5, color="#c9d3e6", weight="semibold", va="center")
bg.text(27, 1140, "CORREDORES DE SALIDA DE MERCANCÍAS DE LA ZTE HACIA LA ZTC", fontsize=30, color="white", weight="bold", va="center", family="Inter Display")
bg.text(27, 1116, "Rutas, kilometraje, puntos exactos de salida de la Zona de Tributación Especial (Ley N.° 27037) y puntos de control públicos",
        fontsize=15, color="#e3e8f2", va="center")
bg.text(814, 1164, "MAPA 2 / 3", fontsize=14, color="white", weight="bold", ha="right", va="center")
bg.text(814, 1140, "Escala 1:1 000 000", fontsize=13, color="#e3e8f2", ha="right", va="center")
bg.text(814, 1116, "Octubre 2026", fontsize=12, color="#c9d3e6", ha="right", va="center")

# ------------------------------------------------ panel inferior: tabla de corredores
P0, P1 = 12, 200
bg.add_patch(Rectangle((15, P0), 811, P1 - P0, fc="white", ec="k", lw=0.8))
tx0, ty = 20, P1 - 6
cols = [(0, "CORREDOR"), (128, "VÍAS"), (200, "KM TOTAL"), (228, "KM EN ZTE"), (258, "SALIDA DEFINITIVA DE LA ZTE (km · coordenadas · límite)"),
        (480, "CIRCUNSCRIPCIONES RECORRIDAS (km)"), (640, "PEAJES / CONTROLES EN RUTA (km)")]
bg.add_patch(Rectangle((tx0 - 2, ty - 4), 805, 7, fc="#1d2b45", ec="none"))
for dx, s in cols: bg.text(tx0 + dx, ty - 0.5, s, fontsize=7.2, weight="bold", color="white", va="center")
ty -= 9
for k in ["OESTE", "SUROESTE", "SUR", "FLUVIAL"]:
    c = corr[k]; d = c["data"]
    rows_h = 21
    bg.add_patch(Rectangle((tx0 - 2, ty - rows_h + 3.5), 805, rows_h, fc="#f4f6fa" if k in ("OESTE", "SUR") else "white", ec="none"))
    bg.add_patch(Rectangle((tx0, ty - 1.6), 5, 3.2, fc=CCOL[k], ec="none"))
    bg.text(tx0 + 7, ty, CNOM[k].split(":")[0], fontsize=9.2, weight="bold", color=CCOL[k], va="center")
    bg.text(tx0 + 7, ty - 5.4, CNOM[k].split(": ")[1], fontsize=7.4, va="center", color="#222")
    bg.text(tx0 + 128, ty + 1.8, "\n".join(textwrap.wrap(", ".join(d["vias"][:6]), 24)), fontsize=7.0, va="top", linespacing=1.2)
    bg.text(tx0 + 200, ty, f"{d['km_total']:.1f}", fontsize=10, weight="bold", va="center")
    bg.text(tx0 + 228, ty, f"{d['km_zte']:.1f}", fontsize=10, weight="bold", va="center", color=C["zte"])
    if k in EXITS:
        e = EXITS[k][2]
        lim = e["limite"].split(" / ")
        bg.text(tx0 + 258, ty, f"km {e['km']:.1f}  ·  {abs(e['lat']):.5f}° S, {abs(e['lon']):.5f}° W", fontsize=8.0, weight="bold", color=C["salida"], va="center")
        bg.text(tx0 + 258, ty - 5.4, "Límite: " + "\n           ".join(lim), fontsize=6.6, linespacing=1.2, va="center", color="#222")
        if k == "OESTE":
            bg.text(tx0 + 258, ty - 12.4, "Entre km 34,4 y 58,3 la vía discurre por el distrito de Choros (Cutervo, ZTC) según límites INEI referenciales.",
                    fontsize=6.2, va="center", color="#7a1d1d", style="italic")
    else:
        bg.text(tx0 + 258, ty, "Recorrido íntegro dentro de la ZTE (Loreto). Ingreso a la circunscripción IA Tarapoto en el río Marañón/Huallaga.",
                fontsize=7.0, va="center", color="#222", wrap=True)
    cir = c["cir"]
    merged_ = []
    for a, b, n in cir:
        if merged_ and merged_[-1][2] == n and a - merged_[-1][1] < 1: merged_[-1] = (merged_[-1][0], b, n)
        else: merged_.append((a, b, n))
    bg.text(tx0 + 480, ty + 1.8, "\n".join(f"{n.replace('IA ', 'IA ')}: {a:.0f}–{b:.0f}" for a, b, n in merged_[:4]), fontsize=7.2, va="top", linespacing=1.25)
    pc = c["pts"][c["pts"].clase.isin(["peaje", "pesaje", "control", "sunat"])]
    txt = "; ".join(f"{(n if isinstance(n, str) else cl.capitalize())} ({km:.0f})" for n, cl, km in zip(pc.name, pc.clase, pc.km))
    bg.text(tx0 + 640, ty + 1.8, "\n".join(textwrap.wrap(txt or "Sin registros públicos en OSM", 52)[:4]), fontsize=6.6, va="top", linespacing=1.25)
    ty -= rows_h

# leyenda
lg = Legend(bg, 20, ty - 4, 160, row=9.0, size=9.2)
lg.header("Corredores")
for k in ["OESTE", "SUROESTE", "SUR"]:
    lg.line(CNOM[k].split(":")[0] + " (tramo en ZTE)", CCOL[k], 5.0, casing=("white", 7))
lg.line("Tramo del corredor en ZTC", CCOL["OESTE"], 5.0, casing=("white", 7))
bg.plot([lg.x, lg.x + lg.sw], [lg.cy + lg.row] * 2, color="white", lw=1.8, ls=(0, (2, 2)))
lg.line("Corredor fluvial (en ZTE)", CCOL["FLUVIAL"], 5.0, ls=(0, (3, 1)), casing=("white", 7))
lg2 = Legend(bg, 192, ty - 4, 160, row=9.0, size=9.2)
lg2.header("Puntos del corredor")
lg2.marker("Salida definitiva de la ZTE", marker="o", ms=11, mfc="white", mec=C["salida"], mew=2)
lg2.marker("Origen / destino / parada (km acumulado)", marker="o", ms=7, mfc=CCOL["OESTE"], mec="white", mew=1.2)
lg2.marker("Unidad de peaje", marker="s", ms=5.2, mfc="#f2c200", mec="#3b3b3b", mew=0.6)
lg2.marker("Puesto de control (público)", marker="^", ms=5.4, mfc="#ef5350", mec="#3b0000", mew=0.6)
lg2.marker("Oficina / puesto SUNAT", marker="p", ms=6.6, mfc="#0d47a1", mec="white", mew=0.7)
lg2.marker("Grifo / estación de servicio (en ruta)", marker="o", ms=4, mfc="#6a1b9a", mec="white", mew=0.4)
lg2.marker("Comisaría / policía (en ruta)", marker="o", ms=4.5, mfc="#1565c0", mec="white", mew=0.4)
lg3 = Legend(bg, 372, ty - 4, 160, row=9.0, size=9.2)
lg3.header("Régimen y límites")
lg3.band("ZTE – art. 3, Ley N.° 27037", C["zte"], 1.6, 1.6)
lg3.box("ZTC – sin trama", fc="white", ec="#888", lw=0.5)
lg3.line("Circunscripción de intendencia de aduana", C["circ"], 1.9, ls=(0, (4, 1.8)))
lg3.line("Límite departamental", C["dep"], 1.3, ls=(0, (5, 1.5, 1, 1.5)))
lg3.line("Límite provincial / distrital", C["prov"], 0.65, ls=(0, (3.5, 1.5)))
lg3.line("Red vial nacional / departamental", C["nacional"], 1.4, casing=("#5a0010", 2.0))
lg3.line("Vía navegable principal / río", C["agua_lin"], 1.8)

X = 560
north_arrow(bg, 806, ty - 22, s=12)
bg.text(X, ty - 4, "ESCALA GRÁFICA", fontsize=7.4, weight="bold", va="center")
scale_bar(bg, X + 12, ty - 16, SCALE, 100, 25)
info = ("WGS 84 · UTM Zona 18 Sur (EPSG:32718) · Escala 1:1 000 000 · A0 vertical\n"
        "Rutas y kilometraje: OSRM sobre OpenStreetMap (30.10.2026); ruta fluvial medida sobre el eje de los ríos (OSM).\n"
        "Salida de la ZTE: cruce de la vía con el límite ZTE (distritos INEI 2019, referenciales). Cutervo representado como ZTC.\n"
        "Peajes, controles, grifos y comisarías: OpenStreetMap (sólo fuentes públicas). Relieve: AWS Terrain Tiles.\n"
        "Circunscripciones: R.S. N.° 000980 y modificatorias. ZTE: art. 3, Ley N.° 27037 y modificatorias.\n"
        "Elaborado por: Equipo de Gestión de Riesgo – IA Tarapoto")
bg.text(X, ty - 27, info, fontsize=7.0, va="top", linespacing=1.35, color="#222")

if not NOPDF: fig.savefig(OUT + ".pdf")
fig.savefig(OUT + ".png", dpi=DPI)
print("ok", OUT)
