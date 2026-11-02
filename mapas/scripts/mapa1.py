# MAPA 1 – Circunscripción territorial de la Intendencia de Aduana de Tarapoto (A0 vertical, 1:625 000)
# Distribución tipo mapa mural: el mapa ocupa todo el recuadro; título, ubicación, leyenda, zoom y tabla
# van dentro del marco sobre las zonas que quedan fuera de la circunscripción.
import sys
sys.path.insert(0, "/home/user/mapas_scripts")
from carto import *

OUT = sys.argv[1] if len(sys.argv) > 1 else "/home/user/TARAPOTO-Dev/mapas/Mapa1_Circunscripcion_IA_Tarapoto"
DPI = int(sys.argv[2]) if len(sys.argv) > 2 else 300
MODE = sys.argv[3] if len(sys.argv) > 3 else "both"     # both | pdf | nopdf
SCALE = 625_000
FR = (20, 20, 801, 1149)                       # marco del mapa (mm de página)
X_L = 35_000                                   # borde oeste del marco (UTM)
fig, bg = page(); ov = fig.ov
pn = mm_axes(fig, 0, 0, PAGE_W, PAGE_H, zorder=50)   # capa de recuadros (sobre el mapa, bajo los insertos)
pn.set_xlim(0, PAGE_W); pn.set_ylim(0, PAGE_H); pn.axis("off"); pn.patch.set_alpha(0)
fr = MapFrame(fig, FR, (X_L + FR[2] * SCALE / 2000, 9_375_400), SCALE)
CB = fr.clipbox(0.05)
OLIVA = "#36432f"        # texto de títulos (oliva oscuro)
SALVIA = "#dde5d0"       # fondo de encabezados (salvia claro, acorde al relieve)
CREMA = "#f4f1e8"        # fondo del título

# recuadros dentro del marco (x, y, ancho, alto en mm)
B_TIT = (20, 1081, 262, 88)       # título (noroeste, sobre Ecuador)
B_UBI = (581, 879, 240, 290)      # ubicación (noreste)
B_LEY = (20, 20, 260, 305)        # leyenda (suroeste)
B_SE = (631, 20, 190, 348)        # zoom Tarapoto + tabla (sureste)
for b in (B_TIT, B_UBI, B_LEY, B_SE):
    fr.labels.add_box((b[0] - 2.5, b[1] - 2.5, b[0] + b[2] + 2.5, b[1] + b[3] + 2.5))

def mm_a_utm(b):
    x, y, w, h = b
    k = SCALE / 1000
    return box(fr.x0 + (x - FR[0]) * k, fr.y0 + (y - FR[1]) * k, fr.x0 + (x + w - FR[0]) * k, fr.y0 + (y + h - FR[1]) * k)
VIS = fr.bbox.buffer(-4000, join_style=2).difference(unary_union([mm_a_utm(b).buffer(4000, join_style=2) for b in (B_TIT, B_UBI, B_LEY, B_SE)]))
def ancla(geom, tol=500):
    """Punto de rótulo (polo de inaccesibilidad) sobre la parte visible más grande del polígono."""
    gi = geom.intersection(VIS)
    ps = [g for g in getattr(gi, "geoms", [gi]) if g.geom_type == "Polygon" and not g.is_empty]
    if not ps: return None, None
    part = max(ps, key=lambda a: a.area)
    return polylabel(part, tol), part

# ------------------------------------------------ datos
dist = fr.load("distritos_tematico"); prov = fr.load("provincias"); dep = fr.load("departamentos")
circ = gpd.read_file(f"{U}/circunscripciones.gpkg"); reg = gpd.read_file(f"{U}/regimen.gpkg"); peru = gpd.read_file(f"{U}/peru.gpkg")
paises = gpd.read_file(f"{U}/paises.gpkg"); pext = gpd.read_file(f"{U}/prov_extranjeras.gpkg")
peru_g = peru.geometry.iloc[0]
tara = circ[circ.circ == "IA TARAPOTO"].geometry.iloc[0]
zte = reg[reg.regimen == "ZTE"].geometry.iloc[0]
ext = [g.difference(peru_g) for g in paises.geometry]
land = [peru_g] + ext

# ------------------------------------------------ relieve (MDE ~38 m) con velo fuera del ámbito
fr.relief(dem="/home/user/data_base/dem_m1_z12.tif", res=65, src_res=38, land=land,
          veil=[g.intersection(CB) for g in ext], veil_alpha=0.50)
fr.polys([peru_g.difference(tara).intersection(CB)], fc="white", alpha=0.28, z=1)

# ------------------------------------------------ hidrografía
agua = fr.load("agua_poly"); rios = fr.load("rios"); hum = fr.load("humedales")
fr.polys(list(hum.geometry), fc="#b9d9c9", alpha=0.35, z=2)
fr.polys(list(agua.geometry), fc=C["agua"], ec=C["agua_lin"], lw=0.18, z=3)
W = {"quebrada": (0.25, 0.6), "canal": (0.35, 0.7), "rio": (0.7, 0.95), "navegable": (1.5, 1), "hidrovia": (2.6, 1)}
for cl in W:
    fr.lines(list(rios[rios.clase == cl].geometry), color=C["agua_lin"], lw=W[cl][0], alpha=W[cl][1], z=3.2 + 0.1 * list(W).index(cl))

# ------------------------------------------------ áreas naturales protegidas
anp = fr.load("anp")
fr.polys(list(anp.geometry), fc="none", ec=C["anp"], lw=0.85, ls=(0, (1.5, 1.2)), z=4, alpha=0.9)

# ------------------------------------------------ ZTE: franja interior
zz = zte.intersection(CB)
zclip = fr.clip_patch(zz); fr.ax.add_patch(zclip)
fr.polys([zz], fc=C["zte"], alpha=0.07, z=4.5)
fr.lines([zz.boundary], color=C["zte"], lw=11, alpha=0.30, z=4.6, clip=zclip, cap="butt")
fr.lines([zz.boundary.difference(peru_g.boundary.buffer(800))], color=C["zte"], lw=1.6, z=4.7)

# ------------------------------------------------ límites
fr.lines(list(dist.geometry.boundary), color=C["dist"], lw=0.45, ls=(0, (2.4, 1.7)), z=6, alpha=0.9)
fr.lines(list(prov.geometry.boundary), color=C["prov"], lw=1.0, ls=(0, (5.5, 2.4)), z=6.5)
fr.lines(list(dep.geometry.boundary), color=C["dep"], lw=1.8, ls=(0, (9, 2.6, 1.6, 2.6)), z=7)
cb = unary_union([g.boundary for g in circ.geometry]).difference(peru_g.boundary.buffer(800))
fr.lines([cb.intersection(CB)], color=C["circ"], lw=2.4, ls=(0, (7, 3)), z=8)
tclip = fr.clip_patch(tara); fr.ax.add_patch(tclip)
fr.lines([tara.boundary], color=C["tarapoto"], lw=9, alpha=0.28, z=8.2, clip=tclip, cap="butt")
fr.lines([tara.boundary], color=C["tarapoto"], lw=2.6, z=8.4)
fr.lines(list(pext.geometry.boundary), color="#6a6a6a", lw=0.8, ls=(0, (5, 2.5)), z=6.5)
fr.lines([peru_g.boundary.intersection(CB)], color="#d9534f", lw=6, alpha=0.25, z=9)
fr.lines([peru_g.boundary.intersection(CB)], color=C["frontera"], lw=2.2, ls=(0, (10, 2.5, 2, 2.5, 2, 2.5)), z=9.2)

# ------------------------------------------------ red vial
vias = fr.load("vias")
vx = vias[~vias.pe]; vias = vias[vias.pe]
fr.lines(list(vx[vx.clase == "trocha"].geometry), color="#9a9a9a", lw=0.4, ls=(0, (3, 1.6)), z=10)
fr.lines(list(vx[vx.clase == "vecinal"].geometry), color="#9a9a9a", lw=0.55, z=10)
fr.lines(list(vx[vx.clase.isin(["nacional", "departamental"])].geometry), color="#7d7d7d", lw=1.2, z=10.2)
fr.lines(list(vias[vias.clase == "trocha"].geometry), color=C["trocha"], lw=0.55, ls=(0, (3, 1.6)), z=10)
fr.lines(list(vias[vias.clase == "vecinal"].geometry), color=C["vecinal"], lw=0.75, z=10.5)
dv = vias[vias.clase == "departamental"]
fr.lines(list(dv.geometry), color="#7a4a00", lw=2.1, z=11, cap="butt")
fr.lines(list(dv.geometry), color=C["departamental"], lw=1.5, z=11.1)
nv = vias[vias.clase == "nacional"]
fr.lines(list(nv.geometry), color="#5a0010", lw=3.2, z=12, cap="butt")
fr.lines(list(nv.geometry), color=C["nacional"], lw=2.4, z=12.1)

# ------------------------------------------------ puntos operativos públicos
pts = fr.load("puntos")
pts = pts[pts.clase.isin(["peaje", "pesaje", "control", "frontera", "sunat", "aerodromo", "puerto", "helipuerto"])]
pts = pts[pts.geometry.within(fr.bbox)]
sede = pts[pts.clase == "sunat"].copy()
sede["d"] = sede.distance(Point(*TO_UTM.transform(-76.3592, -6.4863)))
sede_pt = sede.sort_values("d").geometry.iloc[0]
others = pts.drop(sede.sort_values("d").index[:1])
draw_points(fr, others)
fr.ax.plot([sede_pt.x], [sede_pt.y], marker="*", ms=20, mfc="#c8102e", mec="white", mew=1.1, zorder=30)
fr.labels.obstacle(sede_pt.x, sede_pt.y, 3.6)

# ------------------------------------------------ centros poblados
lug = fr.load("lugares"); lug = lug[lug.geometry.within(fr.bbox)].copy()
lug.loc[~lug.pe & (lug.cap == 8), "cap"] = np.nan
lug["rank"] = np.select([lug.cap == 4, lug.cap == 6, lug.cap == 8, lug.place.isin(["city", "town"]), lug.place == "village"],
                        [0, 1, 2, 3, 4], 5)
in_t = lug.geometry.within(tara)
STY = {0: dict(marker="s", ms=8, mfc="white", mec="black", mew=1.5), 1: dict(marker="o", ms=7, mfc="white", mec="black", mew=1.4),
       2: dict(marker="o", ms=4.2, mfc="#222", mec="white", mew=0.6), 3: dict(marker="o", ms=3.4, mfc="#444", mec="white", mew=0.5),
       4: dict(marker="o", ms=2.4, mfc="#555", mec="none"), 5: dict(marker="o", ms=1.6, mfc="#777", mec="none")}
for r in range(6):
    g = lug[(lug["rank"] == r) & (in_t | (lug["rank"] <= 2))]
    if r == 5: g = g[g.place == "hamlet"]
    fr.ax.plot(g.geometry.x, g.geometry.y, ls="none", zorder=25 - r * 0.1, **STY[r])
    for p in g.geometry: fr.labels.obstacle(p.x, p.y, STY[r]["ms"] * PT * 0.5)

# ------------------------------------------------ rectángulo del zoom N.° 01 (Tarapoto)
ZC = TO_UTM.transform(-76.364, -6.492); ZSCALE = 40_000
ZR = (633, 160, 186, 197)                         # mapa del zoom (mm)
zw, zh = ZR[2] * ZSCALE / 1000, ZR[3] * ZSCALE / 1000
fr.ax.add_patch(Rectangle((ZC[0] - zw / 2, ZC[1] - zh / 2), zw, zh, fill=False, ec="#c8102e", lw=1.3, zorder=31))
fr.labels.obstacle(ZC[0], ZC[1], 7)

# ------------------------------------------------ rótulos (por prioridad)
L = fr.labels
for dx, dy, ha, va in [(34, -26, "left", "top"), (34, 26, "left", "bottom"), (-34, -26, "right", "top"), (-34, 26, "right", "bottom")]:
    X, Y = sede_pt.x + dx * fr.scale / 1000, sede_pt.y + dy * fr.scale / 1000
    t = fr.text(X, Y, "SEDE DE LA INTENDENCIA\nDE ADUANA DE TARAPOTO\nJr. Ramírez Hurtado 301, Tarapoto", size=10, weight="bold",
                color="#8b0a1e", ha=ha, va=va, h=0, z=31, linespacing=1.15,
                bbox=dict(boxstyle="round,pad=0.45", fc="white", ec="#c8102e", lw=1.1, alpha=0.95))
    b_ = L.bbox_mm(t, pad=2.5)
    if not L.collides(b_) or (dy == 26 and dx == -34):
        L.add_box(b_)
        fr.ax.plot([sede_pt.x, X], [sede_pt.y, Y], color="#c8102e", lw=1.0, zorder=30.5)
        break
    t.remove()
L.place(ZC[0] + zw / 2, ZC[1] - zh / 2, "Zoom N.° 01", size=7.6, weight="bold", color="#c8102e", h=1.8,
        offsets=[(3, -2, "left", "top"), (3, 2, "left", "bottom"), (-3, -2, "right", "top")], force=True)
for r, (sz, wt) in {0: (14, "bold"), 1: (11, "semibold")}.items():
    for row in lug[lug["rank"] == r].sort_values("pop", ascending=False).itertuples():
        near_sede = row.geometry.distance(sede_pt) < 4000
        L.place(row.geometry.x, row.geometry.y, row.name.upper() if r == 0 else row.name, size=sz, weight=wt,
                offsets=ring(14 if near_sede else (8 if r == 0 else 7)), h=2.2, force=row.pe, shrink=(sz * 0.85,))
for g, n in zip(paises.geometry, paises.name):
    p, gi = ancla(g.difference(peru_g))
    if gi is not None and gi.area > 1e8:
        L.place(p.x, p.y, n.upper(), size=30, weight="bold", color="#6b6b6b", spacing=1, h=2.5,
                offsets=[(0, 0), (0, -60), (0, 60), (0, -120), (0, 120), (0, -180)])
for row in pext.itertuples():
    p, gi = ancla(row.geometry.difference(peru_g))
    if gi is not None and gi.area > 6e8:
        L.place(p.x, p.y, f"Provincia de {row.name}" if row.name != "Amazonas" else row.name, size=10.5, style="italic", color="#6b6b6b", h=1.8,
                offsets=[(0, 0), (0, 30), (0, -30), (0, 60), (0, -60)])
for row in dep.itertuples():
    p, gi = ancla(row.geometry, 1000)
    if gi is None or gi.area < 2e9: continue
    own = row.departamento in ("SAN MARTIN", "AMAZONAS", "LORETO")   # departamentos de la circunscripción
    L.place(p.x, p.y, nombre(row.departamento).upper(), size=30 if own else 24, weight="bold", color="#4a4a4a", spacing=1, h=2.8, alpha=0.75,
            offsets=[(0, 0), (0, 50), (0, -50), (0, 100), (0, -100), (50, 0), (-50, 0), (0, 150), (0, -150), (70, 70), (-70, -70)],
            shrink=(24, 20) if own else (20, 16), inside=gi, inside_min=0.6, force=own)
for row in circ.itertuples():
    p, gi = ancla(row.geometry, 1000)
    if gi is None or gi.area < 1.5e9: continue
    big = row.circ == "IA TARAPOTO"
    L.place(p.x, p.y, row.circ.replace("IA ", "INTENDENCIA DE ADUANA DE\n") if big else row.circ, size=20 if big else 15,
            weight="bold", color=C["tarapoto"] if big else C["circ"], h=2.8, linespacing=1.0, inside=gi, inside_min=0.6,
            offsets=[(0, -70), (0, 70), (0, -140), (0, 140), (50, 0), (-50, 0), (0, 0), (0, -210), (0, 210), (70, -70), (-70, 70),
                     (70, 70), (-70, -70), (0, -280), (0, 280)], shrink=(13, 11) if not big else ())
for row in prov.itertuples():
    p, gi = ancla(row.geometry, 300)
    if gi is None or gi.area < 4e7: continue
    intar = tara.contains(p)
    L.place(p.x, p.y, nombre(row.provincia).upper(), size=13 if intar else 10, weight="semibold", color="#3d3d3d" if intar else "#6b6b6b",
            h=2, offsets=[(0, 0), (0, 16), (0, -16), (22, 0), (-22, 0), (0, 32), (0, -32)], inside=gi, shrink=(11, 9) if intar else (8.5,))
for row in lug[lug["rank"] == 2].itertuples():
    L.place(row.geometry.x, row.geometry.y, row.name, size=7.8, weight="medium", offsets=ring(5), h=1.6, shrink=(6.8,))
dist["in_t"] = dist.geometry.representative_point().within(tara)
dist["a"] = dist.area
n_ok = 0
for row in dist.sort_values(["in_t", "a"], ascending=[False, False]).itertuples():
    gi = row.geometry.intersection(fr.bbox)
    if gi.is_empty or gi.area < 3e6: continue
    p = polylabel(max(getattr(gi, "geoms", [gi]), key=lambda a: a.area), 200)
    s = nombre(row.distrito)
    if row.in_t:
        kw_ = dict(style="italic", color="#4f3a66", h=1.4)
        t = L.place(p.x, p.y, s, size=7.6, inside=gi, offsets=[(0, 0), (0, 8), (0, -8), (11, 0), (-11, 0), (0, 15), (0, -15), (14, 10), (-14, -10)],
                    shrink=(6.8, 6.0, 5.2), **kw_)
        if t is None:   # distrito pequeño: rótulo menor y menos exigente
            t = L.place(p.x, p.y, s, size=5.0, inside=gi, inside_min=0.3, offsets=[(0, 0), (0, 5), (0, -5), (7, 0), (-7, 0)], shrink=(4.5,), **kw_)
        if t is None:   # último recurso: rótulo fuera del polígono con línea guía
            t = L.place(p.x, p.y, s, size=5.4, offsets=ring(14) + ring(22) + ring(32) + ring(44) + ring(58) + ring(74), shrink=(4.8, 4.4), **kw_)
            if t is not None:
                ax_, ay_ = t.get_position()
                fr.ax.plot([p.x, ax_], [p.y, ay_], color="#4f3a66", lw=0.45, zorder=19, alpha=0.9)
                fr.ax.plot([p.x], [p.y], marker="o", ms=1.6, color="#4f3a66", zorder=19)
        n_ok += t is not None
        if t is None: print("   sin rótulo:", s, "(", nombre(row.provincia), ")")
    else:
        L.place(p.x, p.y, s, size=6.2, style="italic", color="#7b7b7b", h=1.2, inside=gi, offsets=[(0, 0), (0, 8), (0, -8)])
print("distritos rotulados en la circunscripción:", n_ok, "de", int(dist.in_t.sum()))
rn = rios[rios.clase.isin(["hidrovia", "navegable", "rio"]) & rios.name.notna()]
for cl, (sz, ev) in {"hidrovia": (12, 150), "navegable": (10, 130), "rio": (7.6, 120)}.items():
    g = rn[rn.clase == cl]
    along_labels(fr, [(n, list(x.geometry)) for n, x in g.groupby("name")], ev, sz, C["agua_txt"], weight="bold" if cl != "rio" else "normal",
                 family="Liberation Serif", min_len_mm=18 if cl != "rio" else 30, h=1.6)
shields(fr, vias, "nacional", C["nacional"], "white", every_mm=85, size=7.0)
shields(fr, vias, "departamental", "#ffd08a", "#4a2b00", every_mm=95, size=6.2, min_len_mm=25)
for row in others.itertuples():
    if not isinstance(row.name, str): continue
    sz = {"aerodromo": 7.2, "puerto": 7.0, "sunat": 7.2, "peaje": 6.8, "frontera": 7.0, "control": 6.6}.get(row.clase, 6.6)
    col = {"aerodromo": "#0b3d91", "puerto": "#0b5394", "sunat": "#0d47a1", "peaje": "#5d4a00", "frontera": "#9b1c1c"}.get(row.clase, "#333")
    L.place(row.geometry.x, row.geometry.y, row.name, size=sz, color=col, offsets=ring(6), h=1.6)
for row in anp.itertuples():
    p, gi = ancla(row.geometry, 500)
    if gi is None or gi.area < 1.5e8: continue
    L.place(p.x, p.y, row.name, size=7.6, style="italic", color="#2e6b2e", h=1.5, inside=gi, offsets=[(0, 0), (0, 12), (0, -12), (0, 24)])
for r, sz in [(3, 7.0), (4, 6.2), (5, 5.4)]:
    g = lug[(lug["rank"] == r) & in_t]
    for row in g.sort_values("pop", ascending=False).itertuples():
        L.place(row.geometry.x, row.geometry.y, row.name, size=sz, color="#333" if r < 5 else "#555", offsets=ring(4), h=1.3)

fr.frame(step_deg=0.5, utm_km=50, skip=(B_TIT, B_UBI, B_LEY, B_SE))

# ======================================================================= recuadros
def caja(b, fc="white", ec="#222", lw=0.9):
    pn.add_patch(Rectangle(b[:2], b[2], b[3], fc=fc, ec="none", zorder=1))
    ov.add_patch(Rectangle(b[:2], b[2], b[3], fill=False, ec=ec, lw=lw, zorder=40))

def barra(x, y, w, s, h=8.5, size=8.2):
    ov.add_patch(Rectangle((x, y), w, h, fc=SALVIA, ec="none", zorder=41))
    ov.plot([x, x + w], [y, y], color="#9aab86", lw=0.8, zorder=42)
    ov.text(x + 3, y + h / 2, s, fontsize=size, color=OLIVA, weight="bold", va="center", zorder=42)

# ------------------------------------------------ título (NO)
x, y, w, h = B_TIT
caja(B_TIT, fc=CREMA, ec="#a39c86")
ov.add_patch(Rectangle((x, y), 4, h, fc="#7d9467", ec="none", zorder=41))
ov.text(x + 10, y + h - 8, "SUPERINTENDENCIA NACIONAL DE ADUANAS Y DE ADMINISTRACIÓN TRIBUTARIA – SUNAT", fontsize=7.8, color="#6a7060", weight="semibold", va="center", zorder=42)
ov.text(x + 10, y + h - 14.5, "INTENDENCIA DE ADUANA DE TARAPOTO · EQUIPO DE GESTIÓN DE RIESGO", fontsize=7.8, color="#6a7060", va="center", zorder=42)
ov.text(x + 10, y + h - 29, "CIRCUNSCRIPCIÓN TERRITORIAL", fontsize=22, color=OLIVA, weight="bold", va="center", family="Inter Display", zorder=42)
ov.text(x + 10, y + h - 41, "DE LA INTENDENCIA DE ADUANA DE TARAPOTO", fontsize=22, color=OLIVA, weight="bold", va="center", family="Inter Display", zorder=42)
ov.text(x + 10, y + h - 54, "Límites político-administrativos, régimen tributario (Ley N.° 27037) y red de transporte", fontsize=9.6, color="#4f5948", va="center", zorder=42)
ov.plot([x + 10, x + w - 10], [y + 17, y + 17], color="#c9c2ad", lw=0.7, zorder=42)
ov.text(x + 10, y + 9.5, "MAPA 1 / 3", fontsize=9.5, color=OLIVA, weight="bold", va="center", zorder=42)
ov.text(x + w - 10, y + 9.5, "Escala 1:625 000  ·  A0 (841 × 1189 mm)  ·  Noviembre 2026", fontsize=9, color="#4f5948", ha="right", va="center", zorder=42)

# ------------------------------------------------ ubicación (NE)
x, y, w, h = B_UBI
caja(B_UBI)
barra(x, y + h - 8.5, w, "UBICACIÓN · CIRCUNSCRIPCIONES DE LAS INTENDENCIAS DE ADUANA")
pu = gpd.read_file(f"{U}/paises_ubicacion.gpkg")
pb = peru.total_bounds
mh = h - 14; mw = mh * (pb[2] - pb[0] + 120e3) / (pb[3] - pb[1] + 60e3)
ax_in = mm_axes(fig, x + (w - mw) / 2, y + 3, mw, mh, zorder=56)
ax_in.set_facecolor(C["mar"])
for row in pu[pu.name != "Perú"].itertuples():
    ax_in.add_patch(PathPatch(poly_path(row.geometry), fc="#ececec", ec="#b5b5b5", lw=0.4))
pal = ["#d8e2dc", "#ffe5d9", "#ffcad4", "#f4acb7", "#e2ece9", "#cddafd", "#dfe7fd", "#f0efeb", "#fde2e4", "#fad2e1",
       "#e9f5db", "#cfe1b9", "#eae4e9", "#bee1e6", "#f1e3d3", "#fff1e6"]
for i, row in enumerate(circ.itertuples()):
    t_ = row.circ == "IA TARAPOTO"
    ax_in.add_patch(PathPatch(poly_path(row.geometry), fc="#b39ddb" if t_ else pal[i % len(pal)], ec="#7b1f5c", lw=0.4))
    p = polylabel(max(getattr(row.geometry, "geoms", [row.geometry]), key=lambda a: a.area), 2000)
    if t_:
        ax_in.text(p.x, p.y, "IA\nTARAPOTO", fontsize=8, weight="bold", ha="center", va="center", color="#2d0f4f", linespacing=1.0)
    else:
        ax_in.text(p.x, p.y, row.circ.replace("IA ", "").replace("MARÍTIMA DEL ", "MAR. DEL\n").replace("PUERTO ", "PTO.\n"), fontsize=5.0,
                   ha="center", va="center", color="#444", linespacing=1.0)
ax_in.add_patch(PathPatch(poly_path(tara), fc="none", ec=C["tarapoto"], lw=1.4))
ax_in.add_patch(Rectangle((fr.x0, fr.y0), fr.x1 - fr.x0, fr.y1 - fr.y0, fill=False, ec="#c8102e", lw=1.1))
for n, (lo, la) in {"ECUADOR": (-78.6, -1.2), "COLOMBIA": (-72.6, -1.6), "BRASIL": (-70.4, -8.6), "BOLIVIA": (-68.9, -16.0),
                    "CHILE": (-69.6, -18.0), "OCÉANO\nPACÍFICO": (-79.6, -12.2)}.items():
    ax_in.text(*TO_UTM.transform(lo, la), n, fontsize=6.2, color="#5f87a6" if "OCÉANO" in n else "#777", ha="center", va="center",
               style="italic" if "OCÉANO" in n else "normal", weight="bold" if "OCÉANO" not in n else "normal", linespacing=1.0)
ax_in.set_xlim(pb[0] - 60e3, pb[2] + 60e3); ax_in.set_ylim(pb[1] - 30e3, pb[3] + 30e3); ax_in.set_aspect("equal")
ax_in.set_xticks([]); ax_in.set_yticks([])
for s in ax_in.spines.values(): s.set_lw(0.6)
ov.text(x + (w - mw) / 2 + 4, y + 9, "Recuadro rojo: ámbito\ndel mapa principal", fontsize=6.2, color="#8b0a1e", va="center", zorder=45, linespacing=1.1)

# ------------------------------------------------ zoom N.° 01: Tarapoto (SE)
x, y, w, h = B_SE
caja(B_SE)
barra(x, y + h - 8.5, w, "ZOOM N.° 01 · TARAPOTO – SEDE DE LA INTENDENCIA DE ADUANA")
z1 = MapFrame(fig, ZR, ZC, ZSCALE, zorder=56)
zb = z1.clipbox(0.08)
z1.relief(dem="/home/user/data_base/dem_m1_z12.tif", res=8, src_res=38, exag=1.0, shade=(0.80, 0.22))
tl = gpd.read_file(f"{U}/tpp_multipolygons.gpkg"); tln = gpd.read_file(f"{U}/tpp_lines.gpkg")
for g_, cs_ in ((tl, ["landuse", "leisure", "aeroway", "name"]), (tln, ["highway", "aeroway", "name"])):
    for c_ in cs_:
        if c_ not in g_: g_[c_] = None
LU = {"residential": "#ece6dc", "retail": "#f1d9dd", "commercial": "#f1d9dd", "industrial": "#e3dcea", "cemetery": "#d6e5d1",
      "grass": "#dcebcf", "recreation_ground": "#d4ebc6", "farmland": "#eef0d8", "farmyard": "#efe6d2", "military": "#e8d5d5"}
for k, col in LU.items():
    z1.polys(list(tl[tl.landuse == k].geometry), fc=col, ec="none", z=1.5)
z1.polys(list(tl[tl.leisure.isin(["park", "pitch", "stadium"])].geometry), fc="#cfe8c0", ec="none", z=1.6)
z1.polys(list(tl[tl.aeroway == "aerodrome"].geometry), fc="#e6e6ef", ec="#9a9ab5", lw=0.5, z=1.7)
z1.polys(list(tl[tl.aeroway.isin(["apron", "terminal"])].geometry), fc="#c9c9d6", ec="none", z=1.8)
ag = z1.load("agua_poly"); rr = z1.load("rios")
z1.polys(list(ag.geometry), fc=C["agua"], ec=C["agua_lin"], lw=0.3, z=2)
for cl, lw in {"quebrada": 0.6, "canal": 0.7, "rio": 1.4, "navegable": 2.2, "hidrovia": 3.0}.items():
    z1.lines(list(rr[rr.clase == cl].geometry), color=C["agua_lin"], lw=lw, z=2.2)
dz = dist[dist.intersects(zb)]
z1.lines(list(dz.geometry.boundary), color="#5b4a73", lw=1.0, ls=(0, (5, 2.5)), z=6)
HW = {"track": ("#9b8b76", 0.7, (0, (3, 1.6))), "path": ("#a08f7a", 0.5, (0, (1.2, 1.2))), "footway": ("#a08f7a", 0.5, (0, (1.2, 1.2))),
      "service": ("#ffffff", 0.8, "-"), "living_street": ("#ffffff", 1.2, "-"), "residential": ("#ffffff", 1.4, "-"),
      "unclassified": ("#ffffff", 1.5, "-"), "tertiary": ("#ffe9a8", 2.2, "-"), "secondary": ("#ffc061", 2.7, "-"),
      "primary": ("#f28b60", 3.1, "-"), "trunk": (C["nacional"], 3.5, "-")}
for k in ["residential", "living_street", "unclassified", "service", "tertiary", "secondary", "primary", "trunk"]:
    g = tln[tln.highway.fillna("").str.replace("_link", "") == k]
    if k not in ("track", "path", "footway"):
        z1.lines(list(g.geometry), color="#8d8d8d", lw=HW[k][1] + 0.9, z=9 + 0.1 * list(HW).index(k), cap="butt")
for k, (col, lw, ls) in HW.items():
    g = tln[tln.highway.fillna("").str.replace("_link", "") == k]
    z1.lines(list(g.geometry), color=col, lw=lw, ls=ls, z=9.05 + 0.1 * list(HW).index(k))
z1.lines(list(tln[tln.aeroway == "runway"].geometry), color="#6f6f80", lw=7, z=9.0, cap="butt")
z1.lines(list(tln[tln.aeroway == "taxiway"].geometry), color="#8c8ca0", lw=2, z=9.0)
pp = z1.load("puntos"); pp = pp[pp.geometry.within(z1.bbox) & pp.clase.isin(["peaje", "control", "sunat", "policia", "grifo", "aerodromo", "municipalidad"])]
pp = pp[pp.distance(sede_pt) > 60]
draw_points(z1, pp[pp.clase != "municipalidad"])
mun = pp[pp.clase == "municipalidad"]
z1.ax.plot(mun.geometry.x, mun.geometry.y, ls="none", marker="s", ms=5, mfc="#795548", mec="white", mew=0.6, zorder=24)
for p in mun.geometry: z1.labels.obstacle(p.x, p.y, 1.2)
z1.ax.plot([sede_pt.x], [sede_pt.y], marker="*", ms=22, mfc="#c8102e", mec="white", mew=1.2, zorder=30)
z1.labels.obstacle(sede_pt.x, sede_pt.y, 4)
z1.labels.place(sede_pt.x, sede_pt.y, "SEDE IA TARAPOTO\nJr. Ramírez Hurtado 301", size=8.6, weight="bold", color="#8b0a1e", h=2.4,
                linespacing=1.05, offsets=ring(14), force=True)
lz = gpd.read_file("/home/user/data_base/osm/lugares_points.gpkg").to_crs(32718)
lz = lz[lz.geometry.within(z1.bbox) & lz.name.notna()]
for row in lz[lz.place.isin(["city", "town"])].itertuples():
    z1.labels.place(row.geometry.x, row.geometry.y, row.name.upper(), size=13, weight="bold", color="#333", h=2.4, spacing=1,
                    offsets=[(0, 0), (0, 30), (0, -30), (40, 0), (-40, 0)])
for row in dz.itertuples():
    gi = row.geometry.intersection(z1.bbox)
    if gi.area < 2e5: continue
    p = polylabel(max(getattr(gi, "geoms", [gi]), key=lambda a: a.area), 20)
    z1.labels.place(p.x, p.y, f"Distrito de {nombre(row.distrito)}", size=8.2, style="italic", weight="semibold", color="#5b4a73", h=2,
                    offsets=[(0, 0), (0, 25), (0, -25), (35, 0), (-35, 0), (0, 50), (0, -50)], inside=gi)
for row in pp.itertuples():
    if isinstance(row.name, str):
        z1.labels.place(row.geometry.x, row.geometry.y, row.name, size=6.6, color="#333", offsets=ring(6), h=1.6)
for row in lz[lz.place.isin(["suburb", "neighbourhood", "village", "hamlet", "locality"])].itertuples():
    z1.labels.place(row.geometry.x, row.geometry.y, row.name, size=6.4, color="#555", style="italic", offsets=[(0, 0), (0, 8), (0, -8)], h=1.6)
main = tln[tln.highway.fillna("").isin(["trunk", "primary", "secondary", "tertiary"]) & tln.name.notna()]
along_labels(z1, [(n, list(g.geometry)) for n, g in main.groupby("name")], 60, 6.4, "#3b3b3b", style="normal", weight="medium", min_len_mm=12, h=1.8)
rz = rr[rr.name.notna() & rr.clase.isin(["rio", "navegable", "hidrovia"])]
along_labels(z1, [(n, list(g.geometry)) for n, g in rz.groupby("name")], 70, 8, C["agua_txt"], family="Liberation Serif", min_len_mm=12, h=1.8)
for row in tl[(tl.aeroway == "aerodrome") & tl.name.notna()].itertuples():
    p = row.geometry.representative_point()
    z1.labels.place(p.x, p.y, row.name, size=7, weight="semibold", color="#0b3d91", h=2, offsets=[(0, -14), (0, 14), (0, 0)])
z1.ax.add_patch(Rectangle((z1.x0, z1.y0), z1.x1 - z1.x0, z1.y1 - z1.y0, fill=False, ec="#222", lw=1.0, zorder=60))
sb = 1000 * 1e3 / ZSCALE
ov.add_patch(Rectangle((ZR[0] + 3, ZR[1] + 3), 66, 10, fc="white", ec="none", alpha=0.9, zorder=43))
ov.text(ZR[0] + 5, ZR[1] + 10, "Escala 1:40 000", fontsize=6.6, zorder=44, va="center")
for i in range(4):
    ov.add_patch(Rectangle((ZR[0] + 5 + i * sb / 2, ZR[1] + 4.6), sb / 2, 1.8, fc="#222" if i % 2 == 0 else "white", ec="#222", lw=0.4, zorder=44))
ov.text(ZR[0] + 7 + 2 * sb, ZR[1] + 5.5, "2 km", fontsize=6.2, zorder=44, va="center")

# ------------------------------------------------ tabla de provincias (SE, bajo el zoom)
tb = pd.read_csv("/home/user/data_base/tabla_provincias_ia_tarapoto.csv")
ty = ZR[1] - 5
barra(x, ty - 8.5, w, "PROVINCIAS DE LA CIRCUNSCRIPCIÓN DE LA IA TARAPOTO", size=7.8)
ty -= 13
cols = [(3, "DEPARTAMENTO"), (36, "PROVINCIA"), (88, "CAPITAL"), (138, "DISTRITOS"), (186, "ÁREA km²")]
for dx, s in cols:
    pn.text(x + dx, ty, s, fontsize=6.6, weight="bold", va="center", ha="right" if dx >= 138 else "left", zorder=5, color=OLIVA)
pn.plot([x + 2, x + w - 2], [ty - 3, ty - 3], color="#555", lw=0.6, zorder=5)
ty -= 7.4
RH = 5.4
prev = None
for i, row in enumerate(tb.itertuples()):
    if i % 2 == 0: pn.add_patch(Rectangle((x + 1.5, ty - RH / 2), w - 3, RH, fc="#f3f1ea", ec="none", zorder=2))
    if row.departamento != prev:
        pn.text(x + 3, ty, nombre(row.departamento), fontsize=6.9, weight="bold", va="center", zorder=5)
        prev = row.departamento
    pn.text(x + 36, ty, nombre(row.provincia), fontsize=6.9, va="center", zorder=5)
    pn.text(x + 88, ty, row.capital, fontsize=6.9, va="center", zorder=5)
    pn.text(x + 138, ty, f"{row.distritos}", fontsize=6.9, va="center", ha="right", zorder=5)
    pn.text(x + 186, ty, f"{row.area_km2:,.0f}".replace(",", " "), fontsize=6.9, va="center", ha="right", zorder=5)
    ty -= RH
pn.plot([x + 2, x + w - 2], [ty + RH / 2, ty + RH / 2], color="#555", lw=0.6, zorder=5)
pn.text(x + 3, ty - 0.6, f"TOTAL: 4 departamentos (2 completos), {len(tb)} provincias", fontsize=7, weight="bold", va="center", zorder=5)
pn.text(x + 138, ty - 0.6, f"{tb.distritos.sum()}", fontsize=7, weight="bold", va="center", ha="right", zorder=5)
pn.text(x + 186, ty - 0.6, f"{tb.area_km2.sum():,.0f}".replace(",", " "), fontsize=7, weight="bold", va="center", ha="right", zorder=5)
pn.text(x + 3, ty - 7, "Área aproximada calculada sobre límites referenciales INEI (UTM 18S). Loreto: sólo Alto Amazonas y Datem del Marañón.",
        fontsize=5.4, color="#555", va="center", zorder=5, style="italic")

# ------------------------------------------------ leyenda (SO)
x, y, w, h = B_LEY
caja(B_LEY)
barra(x, y + h - 9, w, "LEYENDA", h=9, size=9)
ly = y + h - 15
lg = Legend(pn, x + 6, ly, 118, row=8.0, size=9.6)
lg.header("Límites")
lg.line("Límite internacional", C["frontera"], 2.0, ls=(0, (6, 1.5, 1.2, 1.5)), under=("#d9534f", 5.5, 0.25))
lg.line("Circunscripción de intendencia de aduana", C["circ"], 2.2, ls=(0, (4, 1.8)))
lg.line("Circunscripción IA Tarapoto", C["tarapoto"], 2.4, under=(C["tarapoto"], 8, 0.28))
lg.line("Límite departamental", C["dep"], 1.6, ls=(0, (5, 1.5, 1, 1.5)))
lg.line("Límite provincial", C["prov"], 1.0, ls=(0, (3.5, 1.5)))
lg.line("Límite distrital (referencial INEI)", C["dist"], 0.5, ls=(0, (2, 1.4)))
lg.line("Límite provincial (Ecuador)", "#6a6a6a", 0.8, ls=(0, (3.5, 1.8)))
lg.header("Régimen tributario y ámbito")
lg.band("Zona de Tributación Especial – ZTE (art. 3, Ley N.° 27037)", C["zte"], 1.6, 1.7)
lg.box("Zona de Tributación Común – ZTC (sin trama)", fc="white", ec="#888", lw=0.5)
lg.box("Fuera de la circunscripción IA Tarapoto (velo)", fc="#f3f3f3", ec="#bbb", lw=0.4)
lg.box("Área natural protegida", fc="none", ec=C["anp"], lw=0.9, ls=(0, (1.5, 1.2)))
lg.header("Hidrografía")
lg.line("Vía navegable principal (Hidrovía Amazónica)", C["agua_lin"], 2.6)
lg.line("Río navegable – embarcaciones menores", C["agua_lin"], 1.5)
lg.line("Río / quebrada", C["agua_lin"], 0.7)
lg.box("Lago, laguna o cauce mayor", fc=C["agua"], ec=C["agua_lin"], lw=0.3)

lg2 = Legend(pn, x + 134, ly, 120, row=8.0, size=9.6)
lg2.header("Red vial")
lg2.line("Red vial nacional", C["nacional"], 2.4, casing=("#5a0010", 3.2))
lg2.line("Red vial departamental", C["departamental"], 1.5, casing=("#7a4a00", 2.1))
lg2.line("Red vial vecinal / caminos", C["vecinal"], 0.75)
lg2.line("Trocha carrozable / camino de herradura", C["trocha"], 0.6, ls=(0, (3, 1.6)))
lg2.shield("Código de ruta nacional", "PE-5N", C["nacional"], "white")
lg2.shield("Código de ruta departamental", "SM-105", "#ffd08a", "#4a2b00")
lg2.header("Centros poblados")
lg2.marker("Capital de departamento", **STY[0])
lg2.marker("Capital de provincia", **STY[1])
lg2.marker("Capital de distrito", **STY[2])
lg2.marker("Ciudad / pueblo", **STY[3])
lg2.marker("Centro poblado menor / caserío", **STY[4])
lg2.header("Infraestructura y control")
lg2.marker("Sede de la Intendencia de Aduana de Tarapoto", marker="*", ms=14, mfc="#c8102e", mec="white", mew=0.8)
lg2.marker("Oficina / puesto SUNAT", marker="p", ms=6.6, mfc="#0d47a1", mec="white", mew=0.7)
lg2.marker("Control fronterizo / Migraciones", marker="h", ms=6.4, mfc="#c62828", mec="white", mew=0.7)
lg2.marker("Puesto de control (público)", marker="^", ms=5.4, mfc="#ef5350", mec="#3b0000", mew=0.6)
lg2.marker("Unidad de peaje", marker="s", ms=5.2, mfc="#f2c200", mec="#3b3b3b", mew=0.6)
lg2.glyph("Aeropuerto / aeródromo", "✈", "#0b3d91")
lg2.glyph("Helipuerto", "Ⓗ", "#0b5394", size=7)
lg2.glyph("Puerto / embarcadero fluvial", "⚓", "#0b5394")
ycut = min(lg.cy, lg2.cy) - 2
pn.plot([x + 4, x + w - 4], [ycut, ycut], color="#999", lw=0.5, zorder=5)
pn.text(x + 6, ycut - 6, "ESCALA 1:625 000", fontsize=9, weight="bold", va="center", zorder=5)
scale_bar(pn, x + 52, ycut - 18, SCALE, 100, 25, h=2.8)
north_arrow(pn, x + w - 20, ycut - 19, s=13)
info_a = ("DATOS TÉCNICOS\n"
          "Sistema de referencia WGS 84 · Proyección UTM Zona 18 Sur (EPSG:32718)\n"
          "Cuadrícula geográfica cada 30' · marcas UTM cada 50 km\n\n"
          "FUENTES\n"
          "Límites: INEI 2019, referenciales (calderonsamuel/perumapas). Países: OSM.\n"
          "Circunscripciones: R.S. N.° 000980 y modificatorias (R.S. 391-2014,\n"
          "188-2015 y 070-2016/SUNAT; Ley N.° 28593 – Datem del Marañón).\n"
          "ZTE: art. 3 de la Ley N.° 27037 y modificatorias (Ley N.° 27759).\n"
          "Vías, ríos, poblados, peajes, puertos, aeródromos y controles:\n"
          "© colaboradores de OpenStreetMap (ODbL), extracto del 30.10.2026.\n"
          "Relieve: AWS Terrain Tiles (SRTM), MDE ~38 m.")
info_b = ("NOTAS\n"
          "1. Límites distritales referenciales (INEI); no son límites oficiales.\n"
          "2. Provincia de Cutervo representada como ZTC. La Ley N.° 32582\n"
          "   (15.04.2026) la incluye en la ZTE (excepto el distrito de Cutervo);\n"
          "   su reglamento no ha sido ubicado.\n"
          "3. Clasificación vial referencial a partir de OSM (códigos PE-,\n"
          "   XX-1nn). Clasificación oficial: SINAC – MTC.\n"
          "4. Sólo se muestran puntos operativos de fuentes públicas.\n\n"
          "Elaborado por: Equipo de Gestión de Riesgo\n"
          "Intendencia de Aduana de Tarapoto – SUNAT")
pn.text(x + 6, ycut - 30, info_a, fontsize=7.6, va="top", linespacing=1.32, color="#222", zorder=5)
pn.text(x + 134, ycut - 30, info_b, fontsize=7.6, va="top", linespacing=1.32, color="#222", zorder=5)

if MODE in ("both", "pdf"): fig.savefig(OUT + ".pdf")
if MODE in ("both", "nopdf"): fig.savefig(OUT + ".png", dpi=DPI)
print("ok", OUT)
