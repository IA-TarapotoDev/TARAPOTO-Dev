# MAPA 1 – Circunscripción territorial de la Intendencia de Aduana de Tarapoto (A0 vertical, 1:850 000)
import sys
sys.path.insert(0, "/home/user/mapas_scripts")
from carto import *

OUT = sys.argv[1] if len(sys.argv) > 1 else "/home/user/TARAPOTO-Dev/mapas/Mapa1_Circunscripcion_IA_Tarapoto"
DPI = int(sys.argv[2]) if len(sys.argv) > 2 else 300
NOPDF = len(sys.argv) > 3
SCALE = 850_000
fig, bg = page()
fr = MapFrame(fig, (15, 212, 811, 880), (272_850, 9_375_400), SCALE)
CB = fr.clipbox(0.05)

# ------------------------------------------------ datos
dist = fr.load("distritos_tematico"); prov = fr.load("provincias"); dep = fr.load("departamentos")
circ = gpd.read_file(f"{U}/circunscripciones.gpkg"); reg = gpd.read_file(f"{U}/regimen.gpkg"); peru = gpd.read_file(f"{U}/peru.gpkg")
paises = gpd.read_file(f"{U}/paises.gpkg"); pext = gpd.read_file(f"{U}/prov_extranjeras.gpkg")
peru_g = peru.geometry.iloc[0]
tara = circ[circ.circ == "IA TARAPOTO"].geometry.iloc[0]
zte = reg[reg.regimen == "ZTE"].geometry.iloc[0]
ext = [g.difference(peru_g) for g in paises.geometry]          # países vecinos sin solape con el Perú (INEI)
land = [peru_g] + ext

# ------------------------------------------------ relieve (velo fuera del ámbito)
veil_ext = [g.intersection(CB) for g in ext]
fr.relief(res=75, land=land, veil=veil_ext, veil_alpha=0.50)
fr.polys([peru_g.difference(tara).intersection(CB)], fc="white", alpha=0.28, z=1)

# ------------------------------------------------ hidrografía
agua = fr.load("agua_poly"); rios = fr.load("rios"); hum = fr.load("humedales")
fr.polys(list(hum.geometry), fc="#b9d9c9", alpha=0.35, z=2)
fr.polys(list(agua.geometry), fc=C["agua"], ec=C["agua_lin"], lw=0.15, z=3)
W = {"quebrada": (0.18, 0.55), "canal": (0.3, 0.7), "rio": (0.55, 0.95), "navegable": (1.2, 1), "hidrovia": (2.1, 1)}
for cl in ["quebrada", "canal", "rio", "navegable", "hidrovia"]:
    g = rios[rios.clase == cl]
    fr.lines(list(g.geometry), color=C["agua_lin"], lw=W[cl][0], alpha=W[cl][1], z=3.2 + 0.1 * list(W).index(cl))

# ------------------------------------------------ áreas naturales protegidas
anp = fr.load("anp")
fr.polys(list(anp.geometry), fc="none", ec=C["anp"], lw=0.7, ls=(0, (1.5, 1.2)), z=4, alpha=0.9)

# ------------------------------------------------ ZTE: franja interior
zclip = fr.clip_patch(zte.intersection(CB))
fr.ax.add_patch(zclip)
fr.polys([zte.intersection(CB)], fc=C["zte"], alpha=0.07, z=4.5)
fr.lines([zte.intersection(CB).boundary], color=C["zte"], lw=9, alpha=0.30, z=4.6, clip=zclip, cap="butt")
fr.lines([zte.intersection(CB).boundary.difference(peru_g.boundary.buffer(800))], color=C["zte"], lw=1.4, z=4.7)

# ------------------------------------------------ límites
fr.lines(list(dist.geometry.boundary), color=C["dist"], lw=0.35, ls=(0, (2.2, 1.6)), z=6, alpha=0.9)
fr.lines(list(prov.geometry.boundary), color=C["prov"], lw=0.85, ls=(0, (5, 2.2)), z=6.5)
fr.lines(list(dep.geometry.boundary), color=C["dep"], lw=1.5, ls=(0, (8, 2.5, 1.5, 2.5)), z=7)
# circunscripciones aduaneras (sólo bordes internos del Perú)
cb = unary_union([g.boundary for g in circ.geometry]).difference(peru_g.boundary.buffer(800))
fr.lines([cb.intersection(CB)], color=C["circ"], lw=2.0, ls=(0, (7, 3)), z=8)
# franja de la IA Tarapoto
tclip = fr.clip_patch(tara); fr.ax.add_patch(tclip)
fr.lines([tara.boundary], color=C["tarapoto"], lw=7, alpha=0.28, z=8.2, clip=tclip, cap="butt")
fr.lines([tara.boundary], color=C["tarapoto"], lw=2.2, z=8.4)
# frontera internacional y provincias extranjeras
fr.lines(list(pext.geometry.boundary), color="#6a6a6a", lw=0.7, ls=(0, (5, 2.5)), z=6.5)
fr.lines([peru_g.boundary.intersection(CB)], color="#d9534f", lw=5, alpha=0.25, z=9)
fr.lines([peru_g.boundary.intersection(CB)], color=C["frontera"], lw=1.9, ls=(0, (10, 2.5, 2, 2.5, 2, 2.5)), z=9.2)

# ------------------------------------------------ red vial
vias = fr.load("vias")
vx = vias[~vias.pe]; vias = vias[vias.pe]
fr.lines(list(vx[vx.clase.isin(["trocha"])].geometry), color="#9a9a9a", lw=0.35, ls=(0, (3, 1.6)), z=10)
fr.lines(list(vx[vx.clase.isin(["vecinal"])].geometry), color="#9a9a9a", lw=0.45, z=10)
fr.lines(list(vx[vx.clase.isin(["nacional", "departamental"])].geometry), color="#7d7d7d", lw=1.0, z=10.2)
fr.lines(list(vias[vias.clase == "trocha"].geometry), color=C["trocha"], lw=0.45, ls=(0, (3, 1.6)), z=10)
fr.lines(list(vias[vias.clase == "vecinal"].geometry), color=C["vecinal"], lw=0.6, z=10.5)
dv = vias[vias.clase == "departamental"]
fr.lines(list(dv.geometry), color="#7a4a00", lw=1.75, z=11, cap="butt")
fr.lines(list(dv.geometry), color=C["departamental"], lw=1.2, z=11.1)
nv = vias[vias.clase == "nacional"]
fr.lines(list(nv.geometry), color="#5a0010", lw=2.6, z=12, cap="butt")
fr.lines(list(nv.geometry), color=C["nacional"], lw=1.9, z=12.1)

# ------------------------------------------------ puntos operativos públicos
pts = fr.load("puntos")
pts = pts[pts.clase.isin(["peaje", "pesaje", "control", "frontera", "sunat", "aerodromo", "puerto", "helipuerto"])]
pts = pts[pts.geometry.within(fr.bbox)]
# Sede IA Tarapoto (OSM 'Sunat', Tarapoto; dirección oficial: Jr. Ramírez Hurtado 301)
sede = pts[(pts.clase == "sunat")].copy()
sede["d"] = sede.distance(Point(*TO_UTM.transform(-76.3592, -6.4863)))
sede_pt = sede.sort_values("d").geometry.iloc[0]
others = pts.drop(sede.sort_values("d").index[:1])
draw_points(fr, others)
fr.ax.plot([sede_pt.x], [sede_pt.y], marker="*", ms=17, mfc="#c8102e", mec="white", mew=1.0, zorder=30)
fr.labels.obstacle(sede_pt.x, sede_pt.y, 3.2)

# ------------------------------------------------ centros poblados
lug = fr.load("lugares"); lug = lug[lug.geometry.within(fr.bbox)].copy()
lug.loc[~lug.pe & (lug.cap == 8), "cap"] = np.nan
lug["rank"] = np.select([lug.cap == 4, lug.cap == 6, lug.cap == 8, lug.place.isin(["city", "town"]), lug.place == "village"],
                        [0, 1, 2, 3, 4], 5)
in_t = lug.geometry.within(tara)
STY = {0: dict(marker="s", ms=6.5, mfc="white", mec="black", mew=1.3), 1: dict(marker="o", ms=5.6, mfc="white", mec="black", mew=1.2),
       2: dict(marker="o", ms=3.4, mfc="#222", mec="white", mew=0.5), 3: dict(marker="o", ms=2.8, mfc="#444", mec="white", mew=0.4),
       4: dict(marker="o", ms=1.9, mfc="#555", mec="none"), 5: dict(marker="o", ms=1.3, mfc="#777", mec="none")}
for r in range(6):
    g = lug[(lug["rank"] == r) & (in_t | (lug["rank"] <= 2))]
    if r == 5: g = g[g.place == "hamlet"]
    fr.ax.plot(g.geometry.x, g.geometry.y, ls="none", zorder=25 - r * 0.1, **STY[r])
    for p in g.geometry: fr.labels.obstacle(p.x, p.y, STY[r]["ms"] * PT * 0.5)
    lug.loc[g.index, "drawn"] = True

# ------------------------------------------------ rótulos (por prioridad)
L = fr.labels
for dx, dy, ha, va in [(30, -22, "left", "top"), (30, 22, "left", "bottom"), (-30, -22, "right", "top"), (-30, 22, "right", "bottom")]:
    X, Y = sede_pt.x + dx * fr.scale / 1000, sede_pt.y + dy * fr.scale / 1000
    t = fr.text(X, Y, "SEDE DE LA INTENDENCIA\nDE ADUANA DE TARAPOTO\nJr. Ramírez Hurtado 301, Tarapoto", size=8.4, weight="bold",
                color="#8b0a1e", ha=ha, va=va, h=0, z=31, linespacing=1.15,
                bbox=dict(boxstyle="round,pad=0.45", fc="white", ec="#c8102e", lw=1.0, alpha=0.95))
    b_ = L.bbox_mm(t, pad=2.5)
    if not L.collides(b_) or dy == 22 and dx == -30:
        L.add_box(b_)
        fr.ax.plot([sede_pt.x, X], [sede_pt.y, Y], color="#c8102e", lw=0.9, zorder=30.5)
        break
    t.remove()
for r, (sz, wt) in {0: (12, "bold"), 1: (9, "semibold")}.items():
    for row in lug[lug["rank"] == r].sort_values("pop", ascending=False).itertuples():
        near_sede = row.geometry.distance(sede_pt) < 4000
        L.place(row.geometry.x, row.geometry.y, row.name.upper() if r == 0 else row.name, size=sz, weight=wt,
                offsets=ring(13 if near_sede else (7 if r == 0 else 6)), h=2, force=row.pe, shrink=(sz * 0.85,))
# países y provincias extranjeras
for g, n in zip(paises.geometry, paises.name):
    gi = g.difference(peru_g).intersection(fr.bbox)
    if gi.area > 1e8:
        p = polylabel(max(getattr(gi, "geoms", [gi]), key=lambda a: a.area), 500)
        L.place(p.x, p.y, n.upper(), size=24, weight="bold", color="#6b6b6b", spacing=1, h=2.5)
for row in pext.itertuples():
    gi = row.geometry.difference(peru_g).intersection(fr.bbox)
    if gi.area > 6e8:
        p = polylabel(max(getattr(gi, "geoms", [gi]), key=lambda a: a.area), 500)
        L.place(p.x, p.y, f"Provincia de {row.name}" if row.name != "Amazonas" else row.name, size=9, style="italic", color="#6b6b6b", h=1.8)
# departamentos
for row in dep.itertuples():
    gi = row.geometry.intersection(fr.bbox)
    if gi.area < 2e9: continue
    p = polylabel(max(getattr(gi, "geoms", [gi]), key=lambda a: a.area), 1000)
    L.place(p.x, p.y, nombre(row.departamento).upper(), size=22, weight="bold", color="#4a4a4a", spacing=1, h=2.6, alpha=0.75,
            offsets=[(0, 0), (0, 40), (0, -40), (0, 80), (0, -80), (40, 0), (-40, 0), (0, 120), (0, -120), (60, 60), (-60, -60)],
            shrink=(18,), force=True)
# intendencias
for row in circ.itertuples():
    gi = row.geometry.intersection(fr.bbox)
    if gi.area < 3e9: continue
    p = polylabel(max(getattr(gi, "geoms", [gi]), key=lambda a: a.area), 1000)
    big = row.circ == "IA TARAPOTO"
    L.place(p.x, p.y, row.circ.replace("IA ", "INTENDENCIA DE ADUANA DE\n") if big else row.circ, size=16 if big else 12.5,
            weight="bold", color=C["tarapoto"] if big else C["circ"], h=2.6, linespacing=1.0,
            offsets=[(0, -60), (0, 60), (0, -120), (0, 120), (40, 0), (-40, 0), (0, 0)])
# provincias
for row in prov.itertuples():
    gi = row.geometry.intersection(fr.bbox)
    if gi.area < 4e7: continue
    p = polylabel(max(getattr(gi, "geoms", [gi]), key=lambda a: a.area), 300)
    intar = tara.contains(p)
    L.place(p.x, p.y, nombre(row.provincia).upper(), size=10 if intar else 8, weight="semibold", color="#3d3d3d" if intar else "#6b6b6b",
            h=1.8, offsets=[(0, 0), (0, 14), (0, -14), (18, 0), (-18, 0), (0, 28), (0, -28)], inside=gi, shrink=(8.5, 7) if intar else ())
# capitales distritales
for row in lug[lug["rank"] == 2].itertuples():
    L.place(row.geometry.x, row.geometry.y, row.name, size=6.4, weight="medium", offsets=ring(4.2), h=1.5, shrink=(5.6,))
# distritos (todos los de la circunscripción; vecinos si hay espacio)
dist["in_t"] = dist.geometry.representative_point().within(tara)
dist["a"] = dist.area
for row in dist.sort_values(["in_t", "a"], ascending=[False, False]).itertuples():
    gi = row.geometry.intersection(fr.bbox)
    if gi.is_empty or gi.area < 4e6: continue
    p = polylabel(max(getattr(gi, "geoms", [gi]), key=lambda a: a.area), 200)
    s = nombre(row.distrito)
    if row.in_t:
        L.place(p.x, p.y, s, size=6.2, style="italic", color="#4f3a66", h=1.3, inside=gi,
                offsets=[(0, 0), (0, 7), (0, -7), (9, 0), (-9, 0), (0, 13), (0, -13), (12, 9), (-12, -9)], shrink=(5.4, 4.6, 4.0),
                force=False)
    else:
        L.place(p.x, p.y, s, size=5.2, style="italic", color="#7b7b7b", h=1.2, inside=gi, offsets=[(0, 0), (0, 7), (0, -7)])
# ríos
rn = rios[rios.clase.isin(["hidrovia", "navegable", "rio"]) & rios.name.notna()]
for cl, (sz, ev) in {"hidrovia": (10, 150), "navegable": (8, 130), "rio": (6.4, 120)}.items():
    g = rn[rn.clase == cl]
    along_labels(fr, [(n, list(x.geometry)) for n, x in g.groupby("name")], ev, sz, C["agua_txt"], weight="bold" if cl != "rio" else "normal",
                 family="Liberation Serif", min_len_mm=18 if cl != "rio" else 30)
# vías: escudos
shields(fr, vias, "nacional", C["nacional"], "white", every_mm=85, size=6.2)
shields(fr, vias, "departamental", "#ffd08a", "#4a2b00", every_mm=95, size=5.4, min_len_mm=25)
# puntos operativos
for row in others.itertuples():
    if not isinstance(row.name, str): continue
    sz = {"aerodromo": 6.4, "puerto": 6.2, "sunat": 6.4, "peaje": 5.8, "frontera": 6.0, "control": 5.6}.get(row.clase, 5.6)
    col = {"aerodromo": "#0b3d91", "puerto": "#0b5394", "sunat": "#0d47a1", "peaje": "#5d4a00", "frontera": "#9b1c1c"}.get(row.clase, "#333")
    L.place(row.geometry.x, row.geometry.y, row.name, size=sz, color=col, style="normal", offsets=ring(5.5), h=1.5)
# ANP
for row in anp.itertuples():
    gi = row.geometry.intersection(fr.bbox)
    if gi.area < 1.5e8: continue
    p = polylabel(max(getattr(gi, "geoms", [gi]), key=lambda a: a.area), 500)
    L.place(p.x, p.y, row.name, size=6.4, style="italic", color="#2e6b2e", h=1.4, inside=gi, offsets=[(0, 0), (0, 10), (0, -10)])
# otros centros poblados (dentro de la circunscripción)
for r, sz in [(3, 6.0), (4, 5.2), (5, 4.6)]:
    g = lug[(lug["rank"] == r) & in_t]
    for row in g.sort_values("pop", ascending=False).itertuples():
        L.place(row.geometry.x, row.geometry.y, row.name, size=sz, color="#333" if r < 5 else "#555", offsets=ring(3.6), h=1.2)

fr.frame(step_deg=0.5, utm_km=50)

# ------------------------------------------------ cabecera
bg.add_patch(Rectangle((15, 1100), 811, 77, fc="#1d2b45", ec="none"))
bg.text(27, 1164, "SUPERINTENDENCIA NACIONAL DE ADUANAS Y DE ADMINISTRACIÓN TRIBUTARIA · INTENDENCIA DE ADUANA DE TARAPOTO",
        fontsize=10.5, color="#c9d3e6", weight="semibold", va="center")
bg.text(27, 1140, "CIRCUNSCRIPCIÓN TERRITORIAL DE LA INTENDENCIA DE ADUANA DE TARAPOTO", fontsize=30, color="white",
        weight="bold", va="center", family="Inter Display")
bg.text(27, 1116, "Límites político-administrativos, régimen tributario de la Amazonía (Ley N.° 27037) y red de transporte",
        fontsize=15, color="#e3e8f2", va="center")
bg.text(814, 1164, "MAPA 1 / 3", fontsize=14, color="white", weight="bold", ha="right", va="center")
bg.text(814, 1140, "Escala 1:850 000", fontsize=13, color="#e3e8f2", ha="right", va="center")
bg.text(814, 1116, "Octubre 2026", fontsize=12, color="#c9d3e6", ha="right", va="center")

# ------------------------------------------------ panel inferior
P0, P1 = 12, 200
bg.add_patch(Rectangle((15, P0), 811, P1 - P0, fc="white", ec="k", lw=0.8))
# (a) mapa de ubicación: circunscripciones de las intendencias en el Perú
ax_in = mm_axes(fig, 18, P0 + 3, 132, P1 - P0 - 14)
cl = gpd.read_file(f"{U}/circunscripciones.gpkg")
for g in paises.geometry: ax_in.add_patch(PathPatch(poly_path(g), fc="#efefef", ec="#bbbbbb", lw=0.3))
pal = ["#d8e2dc", "#ffe5d9", "#ffcad4", "#f4acb7", "#e2ece9", "#cddafd", "#dfe7fd", "#f0efeb", "#fde2e4", "#fad2e1",
       "#e9f5db", "#cfe1b9", "#eae4e9", "#bee1e6", "#f1e3d3", "#fff1e6"]
for i, row in enumerate(cl.itertuples()):
    ax_in.add_patch(PathPatch(poly_path(row.geometry), fc="#b39ddb" if row.circ == "IA TARAPOTO" else pal[i % len(pal)],
                              ec="#7b1f5c", lw=0.35))
    if row.circ != "IA TARAPOTO":
        p = polylabel(max(getattr(row.geometry, "geoms", [row.geometry]), key=lambda a: a.area), 2000)
        ax_in.text(p.x, p.y, row.circ.replace("IA ", "").replace("MARÍTIMA DEL ", ""), fontsize=3.6, ha="center", va="center", color="#444")
ax_in.add_patch(PathPatch(poly_path(tara), fc="none", ec=C["tarapoto"], lw=1.2))
p = polylabel(tara, 2000); ax_in.text(p.x, p.y, "IA\nTARAPOTO", fontsize=5.5, weight="bold", ha="center", va="center", color="#2d0f4f")
ax_in.add_patch(Rectangle((fr.x0, fr.y0), fr.x1 - fr.x0, fr.y1 - fr.y0, fill=False, ec="#c8102e", lw=0.9))
xb, yb = peru.total_bounds[[0, 2]], peru.total_bounds[[1, 3]]
ax_in.set_xlim(xb[0] - 60e3, xb[1] + 60e3); ax_in.set_ylim(yb[0] - 30e3, yb[1] + 30e3); ax_in.set_aspect("equal")
ax_in.set_facecolor(C["mar"]); ax_in.set_xticks([]); ax_in.set_yticks([])
for s in ax_in.spines.values(): s.set_lw(0.6)
bg.text(84, P1 - 6, "UBICACIÓN Y CIRCUNSCRIPCIONES DE LAS INTENDENCIAS DE ADUANA", fontsize=6.6, weight="bold", ha="center", va="center")

# (b) leyenda
lg = Legend(bg, 160, P1 - 7, 136, row=9.0, size=9.4)
lg.header("Límites")
lg.line("Límite internacional", C["frontera"], 1.9, ls=(0, (6, 1.5, 1.2, 1.5)), under=("#d9534f", 5, 0.25))
lg.line("Circunscripción de intendencia de aduana", C["circ"], 2.0, ls=(0, (4, 1.8)))
lg.line("Circunscripción IA Tarapoto", C["tarapoto"], 2.2, under=(C["tarapoto"], 7, 0.28))
lg.line("Límite departamental", C["dep"], 1.5, ls=(0, (5, 1.5, 1, 1.5)))
lg.line("Límite provincial", C["prov"], 0.85, ls=(0, (3.5, 1.5)))
lg.line("Límite distrital (referencial INEI)", C["dist"], 0.4, ls=(0, (2, 1.4)))
lg.line("Límite provincial (Ecuador)", "#6a6a6a", 0.7, ls=(0, (3.5, 1.8)))
lg.header("Régimen tributario (Ley N.° 27037)")
lg.band("Zona de Tributación Especial – ZTE (art. 3)", C["zte"], 1.4, 1.6)
lg.box("Zona de Tributación Común – ZTC (sin trama)", fc="white", ec="#888", lw=0.5)
lg.box("Fuera de la circunscripción (velo)", fc="#f3f3f3", ec="#bbb", lw=0.4)
lg.box("Área natural protegida", fc="none", ec=C["anp"], lw=0.8, ls=(0, (1.5, 1.2)))

lg2 = Legend(bg, 300, P1 - 7, 118, row=9.0, size=9.4)
lg2.header("Red vial")
lg2.line("Red vial nacional", C["nacional"], 1.9, casing=("#5a0010", 2.6))
lg2.line("Red vial departamental", C["departamental"], 1.2, casing=("#7a4a00", 1.75))
lg2.line("Red vial vecinal / caminos", C["vecinal"], 0.6)
lg2.line("Trocha carrozable / camino de herradura", C["trocha"], 0.5, ls=(0, (3, 1.6)))
lg2.shield("Código de ruta nacional", "PE-5N", C["nacional"], "white")
lg2.shield("Código de ruta departamental", "SM-105", "#ffd08a", "#4a2b00")
lg2.header("Hidrografía")
lg2.line("Vía navegable principal (Hidrovía Amazónica)", C["agua_lin"], 2.1)
lg2.line("Río navegable – embarcaciones menores", C["agua_lin"], 1.2)
lg2.line("Río / quebrada", C["agua_lin"], 0.55)
lg2.box("Lago, laguna o cauce mayor", fc=C["agua"], ec=C["agua_lin"], lw=0.3)

lg3 = Legend(bg, 436, P1 - 7, 118, row=9.0, size=9.4)
lg3.header("Centros poblados")
lg3.marker("Capital de departamento", **STY[0])
lg3.marker("Capital de provincia", **STY[1])
lg3.marker("Capital de distrito", **STY[2])
lg3.marker("Ciudad / pueblo", **STY[3])
lg3.marker("Centro poblado menor / caserío", **STY[4])
lg3.header("Infraestructura y control")
lg3.marker("Sede de la Intendencia de Aduana de Tarapoto", marker="*", ms=13, mfc="#c8102e", mec="white", mew=0.8)
lg3.marker("Oficina / puesto SUNAT", marker="p", ms=6.6, mfc="#0d47a1", mec="white", mew=0.7)
lg3.marker("Control fronterizo / Migraciones", marker="h", ms=6.4, mfc="#c62828", mec="white", mew=0.7)
lg3.marker("Puesto de control (público)", marker="^", ms=5.4, mfc="#ef5350", mec="#3b0000", mew=0.6)
lg3.marker("Unidad de peaje", marker="s", ms=5.2, mfc="#f2c200", mec="#3b3b3b", mew=0.6)
lg3.glyph("Aeropuerto / aeródromo", "✈", "#0b3d91")
lg3.glyph("Puerto / embarcadero fluvial", "⚓", "#0b5394")

# (c) escala, norte y datos técnicos
X = 580
north_arrow(bg, 806, P1 - 26, s=13)
bg.text(X, P1 - 7, "ESCALA GRÁFICA", fontsize=7.6, weight="bold", va="center")
scale_bar(bg, X + 12, P1 - 22, SCALE, 100, 25)
bg.text(X, P1 - 31, "Escala numérica 1:850 000  ·  impresión A0 (841 × 1189 mm)", fontsize=6.8, va="center")
info = (
    "Sistema de referencia: WGS 84  ·  Proyección UTM, Zona 18 Sur (EPSG:32718)\n"
    "Cuadrícula geográfica cada 30'  ·  marcas UTM cada 50 km\n\n"
    "FUENTES\n"
    "Límites departamentales, provinciales y distritales: INEI (2019), límites referenciales\n"
    "  (repositorio calderonsamuel/perumapas). Países vecinos: OpenStreetMap.\n"
    "Circunscripciones: R.S. N.° 000980 (1997) y modificatorias (R.S. 391-2014, 188-2015,\n"
    "  070-2016/SUNAT; Ley N.° 28593 – Datem del Marañón).\n"
    "ZTE: art. 3 de la Ley N.° 27037 y modificatorias (incl. Ley N.° 27759 – Huánuco).\n"
    "Red vial, hidrografía, centros poblados, peajes, puertos, aeródromos y puntos de\n"
    "  control: © colaboradores de OpenStreetMap (ODbL), extracto del 30.10.2026.\n"
    "Relieve: AWS Terrain Tiles (SRTM/ETOPO), ~76 m.\n\n"
    "NOTAS\n"
    "1. Límites distritales referenciales (INEI); no constituyen límites oficiales.\n"
    "2. Provincia de Cutervo representada como ZTC. La Ley N.° 32582 (15.04.2026) la incluye\n"
    "   en la ZTE (excepto el distrito de Cutervo); su reglamento no ha sido ubicado.\n"
    "3. Clasificación vial referencial a partir de OSM (códigos PE-, XX-1nn). Para la\n"
    "   clasificación oficial consultar el SINAC – MTC.\n"
    "4. Sólo se muestran puntos operativos de fuentes públicas.\n\n"
    "Elaborado por: Equipo de Gestión de Riesgo – IA Tarapoto"
)
bg.text(X + 4, P1 - 40, info, fontsize=7.6, va="top", linespacing=1.3, color="#222")

if not NOPDF: fig.savefig(OUT + ".pdf")
fig.savefig(OUT + ".png", dpi=DPI)
print("ok", OUT)
