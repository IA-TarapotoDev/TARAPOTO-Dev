# MAPA 2 – Corredores de salida de mercancías de la ZTE hacia la ZTC (A0 vertical, 1:1 000 000)
# Misma distribución que el mapa 1: el mapa ocupa todo el recuadro; relieve sólo en la ZTE y fondo blanco en la ZTC.
import sys, textwrap
sys.path.insert(0, "/home/user/mapas_scripts")
from mural import *
from carto import _key
from shapely.ops import substring

OUT = sys.argv[1] if len(sys.argv) > 1 else "/home/user/TARAPOTO-Dev/mapas/Mapa2_Corredores_ZTE_ZTC"
DPI = int(sys.argv[2]) if len(sys.argv) > 2 else 300
MODE = sys.argv[3] if len(sys.argv) > 3 else "both"     # both | pdf | nopdf
SCALE = 1_000_000
M = Mural(SCALE, -60_000, 9_790_000)
fr, fig, bg, ov, pn = M.fr, M.fig, M.bg, M.ov, M.pn
CB = fr.clipbox(0.05)

# recuadros dentro del marco (x, y, ancho, alto en mm de página)
B_TIT = (20, 1079, 300, 90)       # título (noroeste, sobre Ecuador)
B_UBI = (591, 982, 230, 187)      # ubicación (noreste)
B_LEY = (20, 20, 262, 240)        # leyenda (suroeste)
CAJAS = (B_TIT, B_UBI, B_LEY)
M.reservar(*CAJAS)

# ------------------------------------------------ datos
circ = gpd.read_file(f"{U}/circunscripciones.gpkg"); reg = gpd.read_file(f"{U}/regimen.gpkg"); peru = gpd.read_file(f"{U}/peru.gpkg")
paises = gpd.read_file(f"{U}/paises.gpkg"); pext = gpd.read_file(f"{U}/prov_extranjeras.gpkg")
dist = gpd.read_file(f"{U}/distritos_tematico.gpkg"); prov = fr.load("provincias"); dep = fr.load("departamentos")
peru_g = peru.geometry.iloc[0]; tara = circ[circ.circ == "IA TARAPOTO"].geometry.iloc[0]
zte = reg[reg.regimen == "ZTE"].geometry.iloc[0]
ext = [g.difference(peru_g) for g in paises.geometry]; land = [peru_g] + ext
land_u = unary_union(land)
COR = json.load(open("/home/user/data_base/corredores.json"))
CCOL = {"OESTE": "#1546c4", "SUROESTE": "#7b1fa2", "SUR": "#00796b", "FLUVIAL": "#0277bd"}
CNOM = {"OESTE": ("CORREDOR OESTE", "Corral Quemado → Puente Boliche → Chiclayo"),
        "SUROESTE": ("CORREDOR SUROESTE", "Chachapoyas → Balsas → Celendín → Cajamarca"),
        "SUR": ("CORREDOR SUR", "Tocache → Tingo María → Huánuco → Ambo → Cerro de Pasco"),
        "FLUVIAL": ("CORREDOR FLUVIAL", "Iquitos → Nauta → Lagunas → Yurimaguas")}
def fkm(v, d=1):
    return f"{v:,.{d}f}".replace(",", " ").replace(".", ",")
def fgr(v):
    return f"{abs(v):.5f}".replace(".", ",")

# ------------------------------------------------ geometrías de corredores, tramos y puntos asociados
pts_all = gpd.read_file(f"{U}/puntos.gpkg")
corr = {}
for k, c in COR.items():
    ln = gpd.GeoSeries([LineString(c["coords"])], crs=4326).to_crs(32718).iloc[0]
    f = c["km_total"] * 1000 / ln.length
    segs = [(substring(ln, s["desde_km"] * 1000 / f, s["hasta_km"] * 1000 / f), s["regimen"], s["desde_km"], s["hasta_km"]) for s in c["segmentos"]]
    cir = []
    for row in circ.itertuples():
        g = ln.intersection(row.geometry)
        if g.length > 300:
            for s in getattr(g, "geoms", [g]):
                a, b = sorted([ln.project(Point(s.coords[0])), ln.project(Point(s.coords[-1]))])
                if b - a > 300: cir.append((a * f / 1000, b * f / 1000, row.circ))
    cir.sort()
    near = pts_all[pts_all.clase.isin(["peaje", "pesaje", "control", "sunat", "frontera", "policia", "grifo", "puerto"]) & pts_all.pe].copy()
    near["d"] = near.distance(ln)
    near = near[(near.d < 400) & ~((near.clase.isin(["grifo", "policia"])) & (near.d > 250))].copy()
    near["km"] = [ln.project(p) * f / 1000 for p in near.geometry]
    stops = [(s["nombre"], s["km"], ln.interpolate(min(s["km"] * 1000 / f, ln.length))) for s in c["paradas"]]
    corr[k] = dict(line=ln, f=f, segs=segs, cir=cir, pts=near.sort_values("km"), data=c, stops=stops)
LINEAS = unary_union([c["line"] for c in corr.values()])
STOP_PTS = [p for c in corr.values() for _, _, p in c["stops"]]

# salida definitiva de la ZTE y tramos intermedios en ZTC
EXITS = {}
for k, c in corr.items():
    ex = c["data"]["salidas"]
    if not ex: continue
    e = ex[-1]
    X, Y = TO_UTM.transform(e["lon"], e["lat"]); p = Point(X, Y)
    lim = dist[dist.distance(p) < 60].sort_values("regimen", ascending=False)
    e["limite_txt"] = [f"{nombre(r.distrito)} ({nombre(r.provincia)}, {nombre(r.departamento)}) – {r.regimen}" for r in lim.itertuples()]
    inter = []
    for g, rg, a, b in c["segs"]:
        if rg == "ZTC" and b <= e["km"] + 0.01 and b - a > 5:
            dd = dist[dist.intersects(g)].copy()
            dd["lg"] = [r.geometry.intersection(g).length for r in dd.itertuples()]
            dd = dd[dd.lg > 1000].sort_values("lg", ascending=False)
            provs = sorted({nombre(p_) for p_ in dd.provincia})
            nombres = " y ".join(", ".join(nombre(d_) for d_ in dd.distrito).rsplit(", ", 1))
            inter.append((a, b, f"{nombres} – provincia de {', '.join(provs)}"))
    e["intermedios"] = inter
    EXITS[k] = (X, Y, e)

# ------------------------------------------------ relieve sólo en la ZTE; ZTC y países vecinos en blanco; mar celeste
FUERA = CB.difference(zte).intersection(land_u)
fr.relief(dem="/home/user/data_base/dem_m2_z11.tif", res=100, src_res=76, land=land, veil=[FUERA], veil_alpha=1.0, shade=(0.60, 0.46))
CL_IN = fr.clip_patch(zte.intersection(CB)); fr.ax.add_patch(CL_IN)
CL_OUT = fr.clip_patch(CB.difference(zte)); fr.ax.add_patch(CL_OUT)

# ------------------------------------------------ hidrografía
agua = fr.load("agua_poly"); rios = fr.load("rios"); hum = fr.load("humedales")
fr.polys(list(hum.geometry), fc="#b9d9c9", alpha=0.35, z=2, clip=CL_IN)
fr.polys(list(agua.geometry), fc=C["agua"], ec=C["agua_lin"], lw=0.15, z=3)
W_IN = {"quebrada": (0.18, 0.55), "canal": (0.3, 0.7), "rio": (0.55, 0.95), "navegable": (1.25, 1), "hidrovia": (2.2, 1)}
W_OUT = {"rio": (0.4, 0.75), "navegable": (0.9, 0.9), "hidrovia": (1.6, 0.9)}
for i, cl in enumerate(W_IN):
    g = list(rios[rios.clase == cl].geometry)
    fr.lines(g, color=C["agua_lin"], lw=W_IN[cl][0], alpha=W_IN[cl][1], z=3.2 + 0.1 * i, clip=CL_IN)
    if cl in W_OUT:
        fr.lines(g, color="#7fb3dc", lw=W_OUT[cl][0], alpha=W_OUT[cl][1], z=3.2 + 0.1 * i, clip=CL_OUT)

# ------------------------------------------------ ZTE: franja interior
zz = zte.intersection(CB)
zclip = fr.clip_patch(zz); fr.ax.add_patch(zclip)
fr.lines([zz.boundary], color=C["zte"], lw=11, alpha=0.30, z=4.6, clip=zclip, cap="butt")
fr.lines([zz.boundary.difference(peru_g.boundary.buffer(800))], color=C["zte"], lw=1.6, z=4.7)

# ------------------------------------------------ límites
dz = dist[dist.intersects(fr.bbox)]
fr.lines(list(dz.geometry.boundary), color=C["dist"], lw=0.3, ls=(0, (2.2, 1.6)), z=6, alpha=0.8, clip=CL_IN)
fr.lines(list(prov.geometry.boundary), color=C["prov"], lw=0.8, ls=(0, (5, 2.2)), z=6.5, clip=CL_IN)
fr.lines(list(prov.geometry.boundary), color="#bdbdbd", lw=0.5, ls=(0, (5, 2.2)), z=6.5, clip=CL_OUT)
fr.lines(list(dep.geometry.boundary), color=C["dep"], lw=1.5, ls=(0, (8, 2.5, 1.5, 2.5)), z=7)
cb = unary_union([g.boundary for g in circ.geometry]).difference(peru_g.boundary.buffer(800))
fr.lines([cb.intersection(CB)], color=C["circ"], lw=2.0, ls=(0, (7, 3)), z=8)
fr.lines([tara.boundary.difference(peru_g.boundary.buffer(800))], color=C["tarapoto"], lw=2.0, z=8.4)
fr.lines(list(pext.geometry.boundary), color="#9a9a9a", lw=0.6, ls=(0, (5, 2.5)), z=6.5)
fr.lines([peru_g.boundary.intersection(CB)], color="#d9534f", lw=5, alpha=0.25, z=9)
fr.lines([peru_g.boundary.intersection(CB)], color=C["frontera"], lw=1.9, ls=(0, (10, 2.5, 2, 2.5, 2, 2.5)), z=9.2)

# ------------------------------------------------ red vial (detalle en la ZTE; red principal atenuada en la ZTC)
vias = fr.load("vias"); vx = vias[~vias.pe]; vias = vias[vias.pe]
fr.lines(list(vx[vx.clase.isin(["nacional", "departamental"])].geometry), color="#b0b0b0", lw=0.7, z=10.2)
dv = vias[vias.clase == "departamental"]; nv = vias[vias.clase == "nacional"]
fr.lines(list(vias[vias.clase == "trocha"].geometry), color=C["trocha"], lw=0.4, ls=(0, (3, 1.6)), z=10, alpha=0.85, clip=CL_IN)
fr.lines(list(vias[vias.clase == "vecinal"].geometry), color=C["vecinal"], lw=0.55, z=10.5, alpha=0.9, clip=CL_IN)
fr.lines(list(dv.geometry), color="#7a4a00", lw=1.7, z=11, cap="butt", clip=CL_IN)
fr.lines(list(dv.geometry), color=C["departamental"], lw=1.2, z=11.1, clip=CL_IN)
fr.lines(list(nv.geometry), color="#5a0010", lw=2.6, z=12, cap="butt", clip=CL_IN)
fr.lines(list(nv.geometry), color=C["nacional"], lw=1.9, z=12.1, clip=CL_IN)
fr.lines(list(dv.geometry), color="#f4cfa8", lw=0.7, z=11, clip=CL_OUT)
fr.lines(list(nv.geometry), color="#eba8a8", lw=1.1, z=12, clip=CL_OUT)

# ------------------------------------------------ corredores
for k, c in corr.items():
    col = CCOL[k]; fluv = k == "FLUVIAL"
    for g, rg, a, b in c["segs"]:
        fr.lines([g], color="white", lw=8.4, z=13, cap="butt")
        fr.lines([g], color=col, lw=6.0, z=13.2, ls=(0, (4, 1.2)) if fluv else "-")
        if rg == "ZTC": fr.lines([g], color="white", lw=2.2, z=13.3, ls=(0, (3, 3)))
    ln, f = c["line"], c["f"]
    step = 25 if not fluv else 50
    for km in np.arange(step, c["data"]["km_total"], step):
        d = km * 1000 / f; p = ln.interpolate(d); a = ln.interpolate(max(0, d - 1500)); b = ln.interpolate(min(ln.length, d + 1500))
        ang = math.atan2(b.y - a.y, b.x - a.x) + math.pi / 2
        L_ = 4.4 * fr.m_pt
        fr.ax.plot([p.x - L_ * math.cos(ang), p.x + L_ * math.cos(ang)], [p.y - L_ * math.sin(ang), p.y + L_ * math.sin(ang)],
                   color="#111", lw=1.1, zorder=13.5)
        if km % (2 * step) == 0:
            fr.labels.place(p.x, p.y, f"km {km:.0f}", size=7.2, weight="bold", color=col, h=1.8,
                            offsets=[(8 * math.cos(ang), 8 * math.sin(ang)), (-8 * math.cos(ang), -8 * math.sin(ang)),
                                     (13 * math.cos(ang), 13 * math.sin(ang)), (-13 * math.cos(ang), -13 * math.sin(ang))])

# ------------------------------------------------ salidas de la ZTE, paradas y puntos operativos
for k, (X, Y, e) in EXITS.items():
    fr.ax.plot([X], [Y], marker="o", ms=17, mfc="white", mec=C["salida"], mew=2.6, zorder=28)
    fr.ax.plot([X], [Y], marker="x", ms=9, mec=C["salida"], mew=2.6, zorder=28.1)
    fr.labels.obstacle(X, Y, 4.2)
for k, c in corr.items():
    for nm, km, p in c["stops"]:
        fr.ax.plot([p.x], [p.y], marker="o", ms=8.5, mfc=CCOL[k], mec="white", mew=1.5, zorder=27)
        fr.labels.obstacle(p.x, p.y, 2.4)
pts = fr.load("puntos"); pts = pts[pts.geometry.within(fr.bbox) & pts.pe]
pts = pts[pts.geometry.within(zte) | (pts.distance(LINEAS) < 3000)]
ptsv = pd.concat([c["pts"] for c in corr.values()])
draw_points(fr, pts[pts.clase.isin(["peaje", "pesaje", "control", "frontera", "sunat", "aerodromo", "puerto"])])
draw_points(fr, ptsv[ptsv.clase.isin(["grifo", "policia"])])

# capitales: departamento y provincia, distritos > 10 000 hab. y las situadas sobre los corredores
caps = fr.load("capitales"); caps = caps[caps.geometry.within(fr.bbox)].copy()
caps["sobre"] = caps.distance(LINEAS) < 2500
caps["cerca"] = caps.distance(LINEAS) < 25000
caps["en_zte"] = caps.within(zte)
stop_keys = {_key(nm) for c in corr.values() for nm, _, _ in c["stops"]}
caps["parada"] = [min(p.distance(q) for q in STOP_PTS) < 6000 or (_key(nom_cap(n)) in stop_keys and min(p.distance(q) for q in STOP_PTS) < 20000)
                  for p, n in zip(caps.geometry, caps.nombre)]
keep = (caps.nivel == 0) | caps.sobre | ((caps.nivel == 1) & (caps.en_zte | caps.cerca)) | (caps.en_zte & (caps["pop"] >= 10000))
caps = caps[keep & ~caps.parada]
caps = dibujar_capitales(fr, caps)

# ------------------------------------------------ rótulos (por prioridad)
L = fr.labels
for k, (X, Y, e) in EXITS.items():
    L.place(X, Y, f"SALIDA DE LA ZTE\nkm {fkm(e['km'])}", size=10.5, weight="bold", color=C["salida"], h=2.6, linespacing=1.0,
            offsets=ring(12) + ring(20), force=True)
for k, c in corr.items():
    for nm, km, p in c["stops"]:
        L.place(p.x, p.y, f"{nm}\nkm {fkm(km)}", size=10, weight="bold", color=CCOL[k], h=2.4, linespacing=1.0,
                offsets=ring(9) + ring(16), force=True)
rotular_capitales(fr, caps, forzar=(caps.nivel <= 1) | caps.sobre, k=0.9)
for g, n in zip(paises.geometry, paises.name):
    p, gi = M.ancla(g.difference(peru_g))
    if gi is not None and gi.area > 1e8:
        L.place(p.x, p.y, n.upper(), size=30, weight="bold", color="#8a8a8a", spacing=1, h=2.5,
                offsets=[(0, 0), (0, -60), (0, 60), (0, -120), (0, 120), (60, 0), (-60, 0)])
for row in dep.itertuples():
    p, gi = M.ancla(row.geometry, 1000)
    if gi is None or gi.area < 3e9: continue
    en_zte = zte.contains(p)
    L.place(p.x, p.y, nombre(row.departamento).upper(), size=24 if en_zte else 20, weight="bold", color="#4a4a4a" if en_zte else "#8a8a8a",
            spacing=1, h=2.8, alpha=0.75, inside=gi, inside_min=0.6,
            offsets=[(0, 0), (0, 50), (0, -50), (0, 100), (0, -100), (50, 0), (-50, 0), (0, 150), (0, -150), (70, 70), (-70, -70)],
            shrink=(20, 16))
for row in circ.itertuples():
    p, gi = M.ancla(row.geometry, 1000)
    if gi is None or gi.area < 2e9: continue
    L.place(p.x, p.y, row.circ, size=13, weight="bold", color=C["tarapoto"] if row.circ == "IA TARAPOTO" else C["circ"], h=2.6,
            inside=gi, inside_min=0.6, offsets=[(0, -60), (0, 60), (0, -120), (0, 120), (50, 0), (-50, 0), (0, 0), (70, -70), (-70, 70)],
            shrink=(11,))
for row in prov.itertuples():
    p, gi = M.ancla(row.geometry, 300)
    if gi is None or gi.area < 1.5e8: continue
    en_zte = zte.contains(p)
    if not en_zte and not row.geometry.intersects(LINEAS): continue
    L.place(p.x, p.y, nombre(row.provincia).upper(), size=9 if en_zte else 7.6, weight="semibold", color="#4a4a4a" if en_zte else "#9a9a9a",
            h=1.8, inside=gi, offsets=[(0, 0), (0, 14), (0, -14), (18, 0), (-18, 0)], shrink=(7.6,))
rn = rios[rios.clase.isin(["hidrovia", "navegable", "rio"]) & rios.name.notna()]
for cl, (sz, ev) in {"hidrovia": (11, 150), "navegable": (9, 130), "rio": (7, 130)}.items():
    g = rn[rn.clase == cl]
    grupos = []
    for n, x in g.groupby("name"):
        geoms = list(x.geometry) if cl != "rio" else [gg.intersection(zte) for gg in x.geometry if gg.intersects(zte)]
        if geoms: grupos.append((n, geoms))
    along_labels(fr, grupos, ev, sz, C["agua_txt"], weight="bold" if cl != "rio" else "normal", family="Liberation Serif",
                 min_len_mm=18 if cl != "rio" else 40, h=1.6)
nv_in = nv[nv.intersects(zte)].copy(); nv_in["geometry"] = nv_in.geometry.intersection(zte)
nv_out = nv[~nv.within(zte)].copy(); nv_out["geometry"] = nv_out.geometry.difference(zte)
shields(fr, nv_in, "nacional", C["nacional"], "white", every_mm=80, size=6.8)
nv_out = nv_out[nv_out.geometry.distance(LINEAS) < 3000]
shields(fr, nv_out, "nacional", "#e3a3a3", "white", every_mm=110, size=6.2)
dv_in = dv[dv.intersects(zte)].copy(); dv_in["geometry"] = dv_in.geometry.intersection(zte)
shields(fr, dv_in, "departamental", "#ffd08a", "#4a2b00", every_mm=110, size=6.0, min_len_mm=30)
ptsl = pd.concat([pts[pts.clase.isin(["peaje", "pesaje", "control", "frontera", "sunat"])], ptsv[ptsv.clase.isin(["grifo", "policia"])]])
for row in ptsl.itertuples():
    if not isinstance(row.name, str): continue
    col = {"sunat": "#0d47a1", "peaje": "#5d4a00", "frontera": "#9b1c1c", "control": "#9b1c1c", "grifo": "#4a148c", "policia": "#0d47a1"}.get(row.clase, "#333")
    L.place(row.geometry.x, row.geometry.y, row.name, size=6.6 if row.clase not in ("grifo", "policia") else 5.8, color=col, offsets=ring(5.5), h=1.5)
fr.frame(step_deg=1.0, utm_km=100, skip=CAJAS)

# ======================================================================= recuadros
M.titulo(B_TIT, "CORREDORES DE SALIDA DE MERCANCÍAS", "DE LA ZTE HACIA LA ZTC",
         "Rutas, kilometraje, salida exacta de la Zona de Tributación Especial (Ley N.° 27037) y puntos de control",
         "1:1 000 000")
M.ubicacion(B_UBI, "UBICACIÓN · ZONA DE TRIBUTACIÓN ESPECIAL (LEY N.° 27037)", zte, "ZTE", peru, circ, tara)

# ------------------------------------------------ leyenda (SO)
x, y, w, h = B_LEY
M.caja(B_LEY)
M.barra(x, y + h - 9, w, "LEYENDA", h=9, size=9)
ly = y + h - 15
lg = Legend(pn, x + 6, ly, 118, row=9.2, size=9.8)
lg.header("Corredores")
for k in ["OESTE", "SUROESTE", "SUR"]:
    lg.line(CNOM[k][0].title().replace("Corredor ", "Corredor ") + " (en ZTE)", CCOL[k], 5.0, casing=("white", 7))
lg.line("Tramo del corredor en ZTC", CCOL["OESTE"], 5.0, casing=("white", 7))
pn.plot([lg.x, lg.x + lg.sw], [lg.cy + lg.row] * 2, color="white", lw=1.8, ls=(0, (2, 2)), zorder=6)
lg.line("Corredor fluvial (en ZTE)", CCOL["FLUVIAL"], 5.0, ls=(0, (3, 1)), casing=("white", 7))
lg.header("Puntos del corredor")
lg.marker("Salida definitiva de la ZTE", marker="o", ms=11, mfc="white", mec=C["salida"], mew=2)
lg.marker("Origen, parada o destino (km acumulado)", marker="o", ms=7.5, mfc=CCOL["OESTE"], mec="white", mew=1.2)
lg.marker("Unidad de peaje", marker="s", ms=5.2, mfc="#f2c200", mec="#3b3b3b", mew=0.6)
lg.marker("Puesto de control (público)", marker="^", ms=5.4, mfc="#ef5350", mec="#3b0000", mew=0.6)
lg.marker("Oficina / puesto SUNAT", marker="p", ms=6.6, mfc="#0d47a1", mec="white", mew=0.7)
lg.marker("Grifo en ruta", marker="o", ms=4, mfc="#6a1b9a", mec="white", mew=0.4)
lg.marker("Comisaría en ruta", marker="o", ms=4.5, mfc="#1565c0", mec="white", mew=0.4)
lg.glyph("Aeropuerto / aeródromo", "✈", "#0b3d91")

lg2 = Legend(pn, x + 134, ly, 120, row=9.2, size=9.8)
lg2.header("Régimen tributario")
lg2.band("ZTE – art. 3, Ley N.° 27037 (con relieve)", C["zte"], 1.6, 1.7)
lg2.box("ZTC – Zona de Tributación Común (fondo blanco)", fc="white", ec="#888", lw=0.5)
lg2.header("Límites")
lg2.line("Límite internacional", C["frontera"], 2.0, ls=(0, (6, 1.5, 1.2, 1.5)), under=("#d9534f", 5.5, 0.25))
lg2.line("Circunscripción de intendencia de aduana", C["circ"], 2.0, ls=(0, (4, 1.8)))
lg2.line("Circunscripción IA Tarapoto", C["tarapoto"], 2.0)
lg2.line("Límite departamental", C["dep"], 1.5, ls=(0, (5, 1.5, 1, 1.5)))
lg2.line("Límite provincial", C["prov"], 0.8, ls=(0, (3.5, 1.5)))
lg2.header("Red vial e hidrografía")
lg2.line("Red vial nacional", C["nacional"], 1.9, casing=("#5a0010", 2.6))
lg2.line("Red vial departamental", C["departamental"], 1.2, casing=("#7a4a00", 1.7))
lg2.line("Red vial vecinal / trocha", C["vecinal"], 0.6)
lg2.line("Río navegable", C["agua_lin"], 2.0)
lg2.header("Centros poblados")
lg2.marker("Capital de departamento", ms=9, **SYM[0])
cy_ = lg2.cy
lg2.marker("Capital de provincia", ms=8, **SYM[1])
pn.plot([lg2.x + lg2.sw / 2], [cy_], ls="none", marker="o", ms=8 * 0.32, mfc="black", mec="none", zorder=6)
lg2.marker("Capital de distrito", ms=5.4, **SYM[2])
M.pie(x, min(lg.cy, lg2.cy) - 1, w)
print("leyenda: fondo de contenido en y =", round(min(lg.cy, lg2.cy) - 35, 1), "mm (borde inferior:", y, ")")

if MODE in ("both", "pdf"): fig.savefig(OUT + ".pdf")
if MODE in ("both", "nopdf"): fig.savefig(OUT + ".png", dpi=DPI)
print("ok", OUT)
