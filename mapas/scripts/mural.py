# Utilidades compartidas por los mapas murales 2 y 3 (misma distribución que el mapa 1):
# el mapa ocupa todo el recuadro A0 y los recuadros (título, ubicación, leyenda, zooms, tablas) van encima.
import re
from carto import *
from carto import _key

OLIVA = "#36432f"        # texto de títulos (oliva oscuro)
SALVIA = "#dde5d0"       # fondo de encabezados (salvia claro)
CREMA = "#f4f1e8"        # fondo del título
class Mural:
    def __init__(self, scale, x_oeste, y_norte, horizontal=False):
        self.scale = scale
        self.pw, self.ph = (PAGE_H, PAGE_W) if horizontal else (PAGE_W, PAGE_H)
        self.FR = FR = (20, 20, self.pw - 40, self.ph - 40)   # marco del mapa (mm de página)
        self.fig, self.bg = page(self.pw, self.ph)
        self.ov = self.fig.ov
        self.pn = mm_axes(self.fig, 0, 0, self.pw, self.ph, zorder=50)   # recuadros: sobre el mapa, bajo los insertos
        self.pn.set_xlim(0, self.pw); self.pn.set_ylim(0, self.ph); self.pn.axis("off"); self.pn.patch.set_alpha(0)
        k = scale / 1000
        self.fr = MapFrame(self.fig, FR, (x_oeste + FR[2] * k / 2, y_norte - FR[3] * k / 2), scale)
        self.cajas = []
        self.vis = self.fr.bbox.buffer(-4000, join_style=2)

    def reservar(self, *cajas):
        for b in cajas:
            self.cajas.append(b)
            self.fr.labels.add_box((b[0] - 2.5, b[1] - 2.5, b[0] + b[2] + 2.5, b[1] + b[3] + 2.5))
            self.vis = self.vis.difference(self.mm_a_utm(b).buffer(4000, join_style=2))

    def mm_a_utm(self, b):
        x, y, w, h = b
        fr = self.fr; k = self.scale / 1000; FR = self.FR
        return box(fr.x0 + (x - FR[0]) * k, fr.y0 + (y - FR[1]) * k, fr.x0 + (x + w - FR[0]) * k, fr.y0 + (y + h - FR[1]) * k)

    def ancla(self, geom, tol=500):
        """Polo de inaccesibilidad de la parte visible más grande del polígono (fuera de los recuadros)."""
        gi = geom.intersection(self.vis)
        ps = [g for g in getattr(gi, "geoms", [gi]) if g.geom_type == "Polygon" and not g.is_empty]
        if not ps: return None, None
        part = max(ps, key=lambda a: a.area)
        return polylabel(part, tol), part

    # ---------------------------------------------------------------- recuadros
    def caja(self, b, fc="white", ec="#222", lw=0.9):
        self.pn.add_patch(Rectangle(b[:2], b[2], b[3], fc=fc, ec="none", zorder=1))
        self.ov.add_patch(Rectangle(b[:2], b[2], b[3], fill=False, ec=ec, lw=lw, zorder=40))

    def barra(self, x, y, w, s, h=8.5, size=8.2):
        self.ov.add_patch(Rectangle((x, y), w, h, fc=SALVIA, ec="none", zorder=41))
        self.ov.plot([x, x + w], [y, y], color="#9aab86", lw=0.8, zorder=42)
        self.ov.text(x + 3, y + h / 2, s, fontsize=size, color=OLIVA, weight="bold", va="center", zorder=42)

    def titulo(self, b, l1, l2, sub, escala):
        x, y, w, h = b; ov = self.ov
        self.caja(b, fc=CREMA, ec="#a39c86")
        ov.add_patch(Rectangle((x, y), 4, h, fc="#7d9467", ec="none", zorder=41))
        ov.text(x + 10, y + h - 8, "SUPERINTENDENCIA NACIONAL DE ADUANAS Y DE ADMINISTRACIÓN TRIBUTARIA – SUNAT", fontsize=7.8, color="#6a7060", weight="semibold", va="center", zorder=42)
        ov.text(x + 10, y + h - 14.5, "INTENDENCIA DE ADUANA DE TARAPOTO · EQUIPO DE GESTIÓN DE RIESGO", fontsize=7.8, color="#6a7060", va="center", zorder=42)
        ov.text(x + 10, y + h - 29, l1, fontsize=22, color=OLIVA, weight="bold", va="center", family="Inter Display", zorder=42)
        ov.text(x + 10, y + h - 41, l2, fontsize=22, color=OLIVA, weight="bold", va="center", family="Inter Display", zorder=42)
        ov.text(x + 10, y + h - 54, sub, fontsize=9.6, color="#4f5948", va="center", zorder=42, linespacing=1.25)
        ov.plot([x + 10, x + w - 10], [y + 17, y + 17], color="#c9c2ad", lw=0.7, zorder=42)
        formato = f"A0 {'horizontal' if self.pw > self.ph else 'vertical'} ({self.pw:.0f} × {self.ph:.0f} mm)"
        ov.text(x + 10, y + 9.5, f"Escala {escala}  ·  {formato}  ·  Noviembre 2026", fontsize=9, color="#4f5948", va="center", zorder=42)

    def ubicacion(self, b, titulo, sombrear, etiqueta, peru, circ, tara, color_sombra=None, fondo_ia=False):
        """Recuadro de ubicación en tonos de un solo color: Perú, un ámbito sombreado (`sombrear`) y el marco del mapa."""
        x, y, w, h = b; fr = self.fr
        self.caja(b)
        self.barra(x, y + h - 8.5, w, titulo)
        pu = gpd.read_file(f"{U}/paises_ubicacion.gpkg")
        pb = peru.total_bounds
        mh = h - 13; mw = mh * (pb[2] - pb[0] + 120e3) / (pb[3] - pb[1] + 60e3)
        ax = mm_axes(self.fig, x + (w - mw) / 2, y + 3, mw, mh, zorder=56)
        ax.set_facecolor(UBI["mar"])
        for row in pu[pu.name != "Perú"].itertuples():
            ax.add_patch(PathPatch(poly_path(row.geometry), fc=UBI["vecinos"], ec=UBI["vecinos_borde"], lw=0.4))
        ax.add_patch(PathPatch(poly_path(peru.geometry.iloc[0]), fc=UBI["peru"], ec="none"))
        if fondo_ia:
            ax.add_patch(PathPatch(poly_path(tara), fc=UBI["tonos"][3], ec="none"))
        ax.add_patch(PathPatch(poly_path(sombrear), fc=color_sombra or UBI["medio"], ec="none"))
        for g in circ.geometry: ax.add_patch(PathPatch(poly_path(g), fc="none", ec="white", lw=0.7))
        ax.add_patch(PathPatch(poly_path(peru.geometry.iloc[0]), fc="none", ec=UBI["borde_peru"], lw=0.6))
        ax.add_patch(PathPatch(poly_path(tara), fc="none", ec=UBI["oscuro"], lw=1.1))
        zona = tara.difference(sombrear) if fondo_ia else tara
        zona = max(getattr(zona, "geoms", [zona]), key=lambda a: a.area)
        p = polylabel(zona, 2000)
        ax.text(p.x, p.y, "IA\nTARAPOTO", fontsize=6.5, weight="bold", ha="center", va="center", color=UBI["oscuro"], linespacing=1.0,
                path_effects=halo(1.4, c=UBI["peru"]))
        if etiqueta:
            ax.text(*TO_UTM.transform(-71.9, -3.3), etiqueta, fontsize=6.5, weight="bold", ha="center", va="center", color=UBI["oscuro"], linespacing=1.0)
        ax.add_patch(Rectangle((fr.x0, fr.y0), fr.x1 - fr.x0, fr.y1 - fr.y0, fill=False, ec=UBI["marco"], lw=1.2))
        for n, (lo, la) in {"ECUADOR": (-78.6, -1.2), "COLOMBIA": (-72.6, -1.6), "BRASIL": (-70.4, -8.6), "BOLIVIA": (-68.9, -16.0),
                            "CHILE": (-69.6, -18.0), "OCÉANO\nPACÍFICO": (-79.6, -12.2)}.items():
            ax.text(*TO_UTM.transform(lo, la), n, fontsize=5.6, color=UBI["oceano"] if "OCÉANO" in n else UBI["pais"], ha="center", va="center",
                    style="italic" if "OCÉANO" in n else "normal", weight="bold" if "OCÉANO" not in n else "normal", linespacing=1.0)
        ax.set_xlim(pb[0] - 60e3, pb[2] + 60e3); ax.set_ylim(pb[1] - 30e3, pb[3] + 30e3); ax.set_aspect("equal")
        ax.set_xticks([]); ax.set_yticks([])
        for s in ax.spines.values(): s.set_lw(0.6)
        self.ov.text(x + (w - mw) / 2 + 3, y + 8, "Recuadro: ámbito\ndel mapa principal", fontsize=5.8, color=UBI["marco"], va="center", zorder=45, linespacing=1.1)

    def pie(self, x, y, w):
        """Escala, norte y 'Elaborado por' al pie de la leyenda."""
        pn = self.pn
        pn.plot([x + 4, x + w - 4], [y, y], color="#999", lw=0.5, zorder=5)
        pn.text(x + 6, y - 6, f"ESCALA 1:{self.scale:,.0f}".replace(",", " "), fontsize=9.4, weight="bold", va="center", zorder=5)
        km, paso = (100, 25) if self.scale >= 800_000 else (50, 10)
        scale_bar(pn, x + 52, y - 18, self.scale, km, paso, h=2.8)
        north_arrow(pn, x + w - 20, y - 19, s=13)
        pn.text(x + 6, y - 30, "Elaborado por: Equipo de Gestión de Riesgo – Intendencia de Aduana de Tarapoto – SUNAT", fontsize=8.6,
                weight="semibold", color=OLIVA, va="center", zorder=5)


def nom_cap(n):
    m = re.search(r"\((.*?)\)", n)
    if m: n = m.group(1)
    return nombre(n) if (n.isupper() or not any(ord(ch) > 127 for ch in n)) else n

def clase_pop(p):
    return 0 if p >= 100000 else 1 if p >= 40000 else 2 if p >= 15000 else 3 if p >= 5000 else 4 if p >= 2000 else 5

LAB = {0: (16, "bold"), 1: (13.5, "bold"), 2: (11.5, "bold"), 3: (9.6, "semibold"), 4: (8.4, "medium"), 5: (7.4, "normal")}
SYM = {0: dict(marker="s", mfc="white", mec="black", mew=1.6), 1: dict(marker="o", mfc="white", mec="black", mew=1.5),
       2: dict(marker="o", mfc="#1f1f1f", mec="white", mew=0.6)}
MS = {0: {0: 12, 1: 11, 2: 10, 3: 9, 4: 8.5, 5: 8}, 1: {0: 11, 1: 10, 2: 9, 3: 8, 4: 7.5, 5: 7}, 2: {0: 7.5, 1: 7, 2: 6.4, 3: 5.4, 4: 4.6, 5: 4}}

def dibujar_capitales(fr, caps, escala_txt=1.0):
    """Símbolos de capitales (cuadrado: departamento; círculo con punto: provincia; punto: distrito)."""
    caps = caps.copy()
    caps["txt"] = caps.nombre.map(nom_cap)
    caps["cp"] = caps["pop"].fillna(0).map(clase_pop)
    for r in caps.itertuples():
        ms = MS[r.nivel][r.cp]
        fr.ax.plot([r.geometry.x], [r.geometry.y], ls="none", ms=ms, zorder=26 - r.nivel * 0.1, **SYM[r.nivel])
        if r.nivel == 1:
            fr.ax.plot([r.geometry.x], [r.geometry.y], ls="none", marker="o", ms=ms * 0.32, mfc="black", mec="none", zorder=26.05)
        fr.labels.obstacle(r.geometry.x, r.geometry.y, ms * PT * 0.5)
    return caps

def rotular_capitales(fr, caps, forzar=None, k=1.0, color_fuera="#5e5e5e"):
    """Rótulos por población (los más poblados primero). `forzar`: serie booleana de capitales que deben rotularse."""
    n = 0
    orden = caps.assign(forz=forzar if forzar is not None else False).sort_values(["forz", "pop"], ascending=[False, False])
    for r in orden.itertuples():
        sz, wt = LAB[r.cp]; sz *= k
        d = MS[r.nivel][r.cp] * 0.55 + 2.5
        s = r.txt.upper() if r.nivel == 0 else r.txt
        t = fr.labels.place(r.geometry.x, r.geometry.y, s, size=sz, weight=wt, color=C["texto"] if r.forz else color_fuera,
                            offsets=ring(d) + ring(d * 1.8), h=2.2 if r.cp <= 2 else 1.7, shrink=(sz * 0.88, sz * 0.78), force=bool(r.forz))
        n += t is not None
    return n
