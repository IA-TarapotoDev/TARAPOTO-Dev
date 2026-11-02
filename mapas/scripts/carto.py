# Motor cartográfico común: página A0 vertical, marco de mapa en UTM 18S, relieve, capas y rotulado sin solapes
import math, json, numpy as np, geopandas as gpd, pandas as pd, warnings
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm, patheffects as pe
from matplotlib.path import Path
from matplotlib.patches import PathPatch, Rectangle, FancyBboxPatch, Polygon as MPoly
from matplotlib.collections import LineCollection, PatchCollection
from matplotlib.colors import LinearSegmentedColormap
from shapely.geometry import box, Point, LineString, MultiLineString, Polygon, MultiPolygon
from shapely.ops import linemerge, unary_union, polylabel
from pyproj import Transformer
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_origin
warnings.filterwarnings("ignore")

for f in fm.findSystemFonts():
    if "/inter/" in f: fm.fontManager.addfont(f)
plt.rcParams.update({"font.family": "Inter", "pdf.fonttype": 42, "ps.fonttype": 42, "path.simplify": True,
                     "path.simplify_threshold": 0.3, "agg.path.chunksize": 20000})

PAGE_W, PAGE_H = 841.0, 1189.0
PT = 25.4 / 72  # mm por punto
U = "/home/user/data_base/utm"
TO_UTM = Transformer.from_crs(4326, 32718, always_xy=True)
TO_LL = Transformer.from_crs(32718, 4326, always_xy=True)

# Paleta
C = dict(
    texto="#1f2328", gris="#5b6168", gris2="#8a9097", agua="#8fc1e3", agua_lin="#2f7fbf", agua_txt="#1f5f99",
    mar="#cfe4f2", nacional="#c8102e", departamental="#e8891c", vecinal="#6e5a43", trocha="#8b7d6b",
    zte="#2e7d32", circ="#7b1f5c", tarapoto="#5b2a86", dep="#3c3c3c", prov="#555555", dist="#7a7a7a",
    frontera="#202020", ruta="#1a4fd6", salida="#d81b60", anp="#3f7f3f",
)

def halo(w=1.6, c="white", a=0.9):
    return [pe.withStroke(linewidth=w, foreground=c, alpha=a)]

def mm_axes(fig, x, y, w, h, **kw):
    ax = fig.add_axes([x / PAGE_W, y / PAGE_H, w / PAGE_W, h / PAGE_H], **kw)
    return ax

def page():
    fig = plt.figure(figsize=(PAGE_W / 25.4, PAGE_H / 25.4), dpi=100)
    bg = mm_axes(fig, 0, 0, PAGE_W, PAGE_H, zorder=-10)
    bg.set_xlim(0, PAGE_W); bg.set_ylim(0, PAGE_H); bg.axis("off")
    ov = mm_axes(fig, 0, 0, PAGE_W, PAGE_H, zorder=100)
    ov.set_xlim(0, PAGE_W); ov.set_ylim(0, PAGE_H); ov.axis("off"); ov.patch.set_alpha(0)
    fig.ov = ov
    return fig, bg

# ---------------------------------------------------------------- geometría -> paths
def _ring(coords):
    a = np.asarray(coords)[:, :2]
    codes = np.full(len(a), Path.LINETO, dtype=np.uint8); codes[0] = Path.MOVETO; codes[-1] = Path.CLOSEPOLY
    return a, codes

def poly_path(geom):
    vs, cs = [], []
    for p in getattr(geom, "geoms", [geom]):
        if p.is_empty or p.geom_type != "Polygon": continue
        for r in [p.exterior, *p.interiors]:
            a, c = _ring(r.coords); vs.append(a); cs.append(c)
    if not vs: return None
    return Path(np.concatenate(vs), np.concatenate(cs))

def line_segs(geoms):
    out = []
    for g in geoms:
        if g is None or g.is_empty: continue
        if g.geom_type in ("Polygon", "MultiPolygon"):
            g = g.boundary
        for l in getattr(g, "geoms", [g]):
            if l.geom_type == "LineString" and len(l.coords) > 1:
                out.append(np.asarray(l.coords)[:, :2])
            elif l.geom_type in ("MultiLineString", "GeometryCollection"):
                out.extend(line_segs([l]))
    return out

# ---------------------------------------------------------------- marco de mapa
class MapFrame:
    def __init__(self, fig, rect, center, scale, zorder=1):
        self.fig = fig; self.rect = rect; self.scale = scale
        x, y, w, h = rect
        self.ax = mm_axes(fig, x, y, w, h, zorder=zorder)
        W = w / 1000 * scale; H = h / 1000 * scale
        self.x0, self.x1 = center[0] - W / 2, center[0] + W / 2
        self.y0, self.y1 = center[1] - H / 2, center[1] + H / 2
        self.ax.set_xlim(self.x0, self.x1); self.ax.set_ylim(self.y0, self.y1)
        self.ax.set_aspect("equal"); self.ax.axis("off")
        self.bbox = box(self.x0, self.y0, self.x1, self.y1)
        self.m_pt = PT / 1000 * scale  # metros de terreno por punto tipográfico
        self.labels = LabelManager(self)

    def mm(self, X, Y):  # coordenadas UTM -> mm de página
        x, y, w, h = self.rect
        return x + (X - self.x0) / (self.x1 - self.x0) * w, y + (Y - self.y0) / (self.y1 - self.y0) * h

    def load(self, name, buf=0.15, cols=None):
        g = gpd.read_file(f"{U}/{name}.gpkg", bbox=tuple(self.bbox.buffer((self.x1 - self.x0) * buf).bounds))
        return g

    def clipbox(self, buf=0.02):
        return self.bbox.buffer((self.x1 - self.x0) * buf, join_style=2)

    # -------- dibujo
    def polys(self, geoms, fc="none", ec="none", lw=0, alpha=1, z=2, hatch=None, ls="-", clip=None, **kw):
        ps = [poly_path(g) for g in geoms]
        ps = [p for p in ps if p is not None]
        if not ps: return None
        path = Path.make_compound_path(*ps)
        patch = PathPatch(path, facecolor=fc, edgecolor=ec, lw=lw, alpha=alpha, zorder=z, hatch=hatch, ls=ls, **kw)
        self.ax.add_patch(patch)
        if clip is not None: patch.set_clip_path(clip)
        return patch

    def lines(self, geoms, color="k", lw=1, ls="-", z=3, alpha=1, cap="round", join="round", clip=None, **kw):
        segs = line_segs(geoms)
        if not segs: return None
        lc = LineCollection(segs, colors=color, linewidths=lw, linestyles=ls, zorder=z, alpha=alpha,
                            capstyle=cap, joinstyle=join, **kw)
        self.ax.add_collection(lc)
        if clip is not None: lc.set_clip_path(clip)
        return lc

    def clip_patch(self, geom):
        p = PathPatch(poly_path(geom), transform=self.ax.transData, facecolor="none", edgecolor="none")
        return p

    def text(self, x, y, s, size=7, color=None, weight="normal", style="normal", ha="center", va="center", rot=0,
             z=20, h=1.6, family="Inter", spacing=0, **kw):
        if spacing: s = (" " * spacing).join(s) if spacing > 0 else s
        t = self.ax.text(x, y, s, fontsize=size, color=color or C["texto"], weight=weight, style=style, ha=ha,
                         va=va, rotation=rot, zorder=z, family=family, rotation_mode="anchor",
                         path_effects=halo(h) if h else None, clip_on=True, **kw)
        return t

    # -------- relieve
    def relief(self, dem="/home/user/data_base/dem_z11.tif", res=75, land=None, veil=None, veil_alpha=0.45,
               tint=True, z=0, exag=1.6, shade=(0.55, 0.52), src_res=76):
        """Relieve sombreado multidireccional con tintas hipsométricas (src_res: resolución del MDE de origen, m)."""
        from rasterio.features import rasterize
        nx = int((self.x1 - self.x0) / res); ny = int((self.y1 - self.y0) / res)
        tr = from_origin(self.x0, self.y1, res, res)
        z_ = np.full((ny, nx), np.nan, np.float32)
        rs = Resampling.average if res > src_res * 1.2 else Resampling.bilinear
        with rasterio.open(dem) as src:
            reproject(rasterio.band(src, 1), z_, dst_transform=tr, dst_crs="EPSG:32718", resampling=rs)
        np.nan_to_num(z_, copy=False, nan=0); z_[z_ < -400] = 0
        if res < src_res * 0.6:  # gran escala: suavizar el remuestreo del MDE
            from scipy.ndimage import gaussian_filter
            z_ = gaussian_filter(z_, sigma=src_res / res * 0.6)
        self.dem = (z_, tr)
        # hillshade multidireccional (float32 para contener la memoria)
        gy, gx = np.gradient(z_, res)
        gy *= exag; gx *= exag
        slope = np.arctan(np.hypot(gx, gy)); aspect = np.arctan2(-gx, gy)
        del gx, gy
        sin_s, cos_s = np.sin(slope), np.cos(slope)
        del slope
        hs = np.zeros_like(z_)
        alt = np.radians(42)
        for az, wgt in [(315, 0.45), (270, 0.2), (0, 0.15), (225, 0.2)]:
            a = np.radians(360 - az + 90)
            hs += np.float32(wgt) * (np.float32(np.sin(alt)) * cos_s + np.float32(np.cos(alt)) * sin_s * np.cos(np.float32(a) - aspect))
        del sin_s, cos_s, aspect
        np.clip(hs, 0, 1, out=hs)
        sh = np.float32(shade[0]) + np.float32(shade[1]) * hs
        del hs
        stops = [(0, "#e3ecd6"), (150, "#e1ead0"), (400, "#e9ecd0"), (800, "#efeacc"), (1500, "#ede1c0"),
                 (2500, "#e4d2b2"), (3500, "#dccab0"), (4300, "#ece8e2"), (6500, "#ffffff")]
        lv = np.array([s[0] for s in stops], float); cols = np.array([matplotlib.colors.to_rgb(s[1]) for s in stops])
        rgb = np.empty(z_.shape + (3,), np.uint8)
        for i in range(3):
            ch = np.interp(z_, lv, cols[:, i]).astype(np.float32) if tint else np.full(z_.shape, 0.94, np.float32)
            ch *= sh; np.clip(ch, 0, 1, out=ch); ch *= 255
            rgb[..., i] = ch
            del ch
        del sh
        # mar
        if land is not None:
            m = rasterize([(g, 1) for g in land], out_shape=z_.shape, transform=tr, fill=0, dtype="uint8")
            rgb[m == 0] = (np.array(matplotlib.colors.to_rgb(C["mar"])) * 255).astype(np.uint8)
            del m
        if veil is not None:
            m = rasterize([(g, 1) for g in veil], out_shape=z_.shape, transform=tr, fill=0, dtype="uint8").astype(bool)
            rgb[m] = (rgb[m] * (1 - veil_alpha) + 255 * veil_alpha).astype(np.uint8)
            del m
        self.ax.imshow(rgb, extent=(self.x0, self.x0 + nx * res, self.y1 - ny * res, self.y1),
                       interpolation="bilinear", zorder=z, origin="upper")

    # -------- marco, cuadrícula y coordenadas
    def frame(self, step_deg=0.5, lw=1.2, utm_km=50, skip=()):
        x, y, w, h = self.rect
        bg = self.fig.ov
        def libre(px, py, m=6):  # fuera de los recuadros interiores
            return not any(r[0] - m < px < r[0] + r[2] + m and r[1] - m < py < r[1] + r[3] + m for r in skip)
        # graticule
        lon0, lat0 = TO_LL.transform(self.x0, self.y0); lon1, lat1 = TO_LL.transform(self.x1, self.y1)
        lonA, latA = TO_LL.transform(self.x0, self.y1); lonB, latB = TO_LL.transform(self.x1, self.y0)
        lons = np.arange(math.floor(min(lon0, lonA) / step_deg) * step_deg, max(lon1, lonB) + step_deg, step_deg)
        lats = np.arange(math.floor(min(lat0, latB) / step_deg) * step_deg, max(lat1, latA) + step_deg, step_deg)
        segs = []
        for lo in lons:
            yy = np.linspace(min(lat0, latB) - 1, max(lat1, latA) + 1, 200)
            X, Y = TO_UTM.transform(np.full_like(yy, lo), yy); segs.append(np.c_[X, Y])
        for la in lats:
            xx = np.linspace(min(lon0, lonA) - 1, max(lon1, lonB) + 1, 200)
            X, Y = TO_UTM.transform(xx, np.full_like(xx, la)); segs.append(np.c_[X, Y])
        self.ax.add_collection(LineCollection(segs, colors="#6d7880", linewidths=0.35, alpha=0.55, zorder=15, linestyles=(0, (6, 3))))
        def fmt(v, ns):
            d = abs(v); dd = int(d + 1e-9); mm_ = int(round((d - dd) * 60))
            if mm_ == 60: dd += 1; mm_ = 0
            return f"{dd}°{mm_:02d}'{ns}"
        # etiquetas en bordes (intersección graticule-borde)
        for lo in lons:
            for Yb, side in [(self.y0, "b"), (self.y1, "t")]:
                ln = LineString(np.c_[TO_UTM.transform(np.full(50, lo), np.linspace(-20, 5, 50))])
                ip = ln.intersection(LineString([(self.x0, Yb), (self.x1, Yb)]))
                if ip.is_empty: continue
                px, py = self.mm(ip.x, Yb)
                bg.plot([px, px], [py, py + (-3 if side == "b" else 3)], color="k", lw=0.6)
                bg.text(px, py + (-4.2 if side == "b" else 4.2), fmt(lo, "W"), ha="center", va="top" if side == "b" else "bottom", fontsize=7, color=C["texto"])
        for la in lats:
            for Xb, side in [(self.x0, "l"), (self.x1, "r")]:
                ln = LineString(np.c_[TO_UTM.transform(np.linspace(-85, -65, 50), np.full(50, la))])
                ip = ln.intersection(LineString([(Xb, self.y0), (Xb, self.y1)]))
                if ip.is_empty: continue
                px, py = self.mm(Xb, ip.y)
                bg.plot([px, px + (-3 if side == "l" else 3)], [py, py], color="k", lw=0.6)
                bg.text(px + (-4.2 if side == "l" else 4.2), py, fmt(la, "S"), ha="right" if side == "l" else "left", va="center", fontsize=7, rotation=90, rotation_mode="anchor", color=C["texto"]) if False else \
                bg.text(px + (-4.2 if side == "l" else 4.2), py, fmt(la, "S"), ha="center", va="bottom" if side == "l" else "top", fontsize=7, rotation=90, color=C["texto"])
        # ticks UTM (km) en borde interior
        for X in np.arange(math.ceil(self.x0 / (utm_km * 1000)) * utm_km * 1000, self.x1, utm_km * 1000):
            px, _ = self.mm(X, self.y0)
            for py, d in [(y, 1.8), (y + h, -1.8)]:
                if libre(px, py): bg.plot([px, px], [py, py + d], color="#333", lw=0.5)
            if libre(px, y): bg.text(px, y + 2.3, f"{X/1000:.0f}", fontsize=4.6, color="#444", ha="center", va="bottom")
        for Y in np.arange(math.ceil(self.y0 / (utm_km * 1000)) * utm_km * 1000, self.y1, utm_km * 1000):
            _, py = self.mm(self.x0, Y)
            for px, d in [(x, 1.8), (x + w, -1.8)]:
                if libre(px, py): bg.plot([px, px + d], [py, py], color="#333", lw=0.5)
            if libre(x, py): bg.text(x + 2.3, py, f"{Y/1000:.0f}", fontsize=4.6, color="#444", ha="left", va="center")
        bg.add_patch(Rectangle((x, y), w, h, fill=False, lw=lw, ec="k", zorder=30))
        bg.add_patch(Rectangle((x - 1.6, y - 1.6), w + 3.2, h + 3.2, fill=False, lw=0.4, ec="k", zorder=30))


# ---------------------------------------------------------------- rotulado sin solapes
class LabelManager:
    def __init__(self, fr):
        self.fr = fr; self.boxes = []  # (x0,y0,x1,y1) en mm de página
        self.cell = 20.0; self.grid = {}
        self.renderer = fr.fig.canvas.get_renderer()

    def _cells(self, b):
        for i in range(int(b[0] // self.cell), int(b[2] // self.cell) + 1):
            for j in range(int(b[1] // self.cell), int(b[3] // self.cell) + 1):
                yield (i, j)

    def collides(self, b):
        for c in self._cells(b):
            for o in self.grid.get(c, ()):
                if b[0] < o[2] and b[2] > o[0] and b[1] < o[3] and b[3] > o[1]: return True
        return False

    def add_box(self, b):
        for c in self._cells(b): self.grid.setdefault(c, []).append(b)

    def obstacle(self, X, Y, r_mm):
        x, y = self.fr.mm(X, Y); self.add_box((x - r_mm, y - r_mm, x + r_mm, y + r_mm))

    def bbox_mm(self, t, pad=0.3):
        e = t.get_window_extent(self.renderer)
        f = self.fr.fig; k = 25.4 / f.dpi
        return (e.x0 * k - pad, e.y0 * k - pad, e.x1 * k + pad, e.y1 * k + pad)

    def place(self, X, Y, s, offsets=((0, 0),), force=False, inside=None, shrink=(), inside_min=0.55, **kw):
        """Coloca un texto probando desplazamientos (en pt). Devuelve el Text o None."""
        sizes = [kw.pop("size", 7)] + list(shrink)
        x0, x1, y0, y1 = self.fr.x0, self.fr.x1, self.fr.y0, self.fr.y1
        fx, fy, fw, fh = self.fr.rect
        for size in sizes:
            for dx, dy, *al in offsets:
                ha = al[0] if al else "center"; va = al[1] if len(al) > 1 else "center"
                t = self.fr.text(X + dx * self.fr.m_pt, Y + dy * self.fr.m_pt, s, size=size, ha=ha, va=va, **kw)
                b = self.bbox_mm(t)
                ok = b[0] > fx + 1 and b[2] < fx + fw - 1 and b[1] > fy + 1 and b[3] < fy + fh - 1
                if ok and inside is not None:
                    # el rótulo debe quedar mayormente dentro del polígono
                    k = (self.fr.x1 - self.fr.x0) / fw
                    bb = box(x0 + (b[0] - fx) * k, y0 + (b[1] - fy) * k, x0 + (b[2] - fx) * k, y0 + (b[3] - fy) * k)
                    ok = inside.intersection(bb).area / bb.area > inside_min
                if ok and not self.collides(b):
                    self.add_box(b); return t
                t.remove()
        if force:
            dx, dy, *al = offsets[0]
            t = self.fr.text(X + dx * self.fr.m_pt, Y + dy * self.fr.m_pt, s, size=sizes[0], ha=al[0] if al else "center",
                             va=al[1] if len(al) > 1 else "center", **kw)
            self.add_box(self.bbox_mm(t)); return t
        return None

RING = [(0, 0), (6, 0, "left", "center"), (-6, 0, "right", "center"), (0, 6, "center", "bottom"), (0, -6, "center", "top"),
        (5, 5, "left", "bottom"), (-5, 5, "right", "bottom"), (5, -5, "left", "top"), (-5, -5, "right", "top")]
def ring(d):
    return [(d, 0, "left", "center"), (-d, 0, "right", "center"), (0, d, "center", "bottom"), (0, -d, "center", "top"),
            (d * .8, d * .8, "left", "bottom"), (-d * .8, d * .8, "right", "bottom"), (d * .8, -d * .8, "left", "top"), (-d * .8, -d * .8, "right", "top")]

def title_case(s):
    small = {"de", "del", "la", "las", "los", "y", "el", "en"}
    w = s.lower().split()
    return " ".join(x if (i and x in small) else x.capitalize() for i, x in enumerate(w))

ACC = {"Maranon": "Marañón", "Marañon": "Marañón", "Jaen": "Jaén", "San Martin": "San Martín", "Huanuco": "Huánuco",
       "Rodriguez De Mendoza": "Rodríguez de Mendoza", "Bongara": "Bongará", "Mariscal Caceres": "Mariscal Cáceres",
       "Celendin": "Celendín", "Contumaza": "Contumazá", "Ferreñafe": "Ferreñafe", "Junin": "Junín",
       "Huamalies": "Huamalíes", "Datem Del Marañon": "Datem del Marañón", "Mariscal Ramon Castilla": "Mariscal Ramón Castilla",
       "Leoncio Prado": "Leoncio Prado", "Sanchez Carrion": "Sánchez Carrión", "Bolivar": "Bolívar", "Daniel Alcides Carrion": "Daniel Alcides Carrión"}
def nice(s):
    t = title_case(s)
    return ACC.get(t, t)

# ---------------------------------------------------------------- utilidades comunes
import unicodedata
def _key(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s).lower()) if unicodedata.category(c) != "Mn").replace("ñ", "n").strip()

_ACC = None
def acentos():
    """Diccionario nombre sin tildes -> nombre con tildes (de los centros poblados OSM)."""
    global _ACC
    if _ACC is None:
        p = gpd.read_file(f"{U}/lugares.gpkg", ignore_geometry=True)
        _ACC = {}
        for n in p.sort_values("cap").name:
            k = _key(n)
            if k not in _ACC and any(ord(c) > 127 for c in n): _ACC[k] = n
        for k, v in {"jaen": "Jaén", "maranon": "Marañón", "san martin": "San Martín", "huanuco": "Huánuco"}.items(): _ACC[k] = v
    return _ACC

WORD_ACC = {w.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u"): w for w in
    "Marañón Martín Jaén Huánuco Cáceres Rodríguez Ramón Bongará Celendín Contumazá Junín Huamalíes Carrión Bolívar Río Unión "
    "Perú José María Jesús Andrés Inés López González Pérez Fernández García Sánchez Ramírez Martínez Simón Agustín Sebastián "
    "Cristóbal Nicolás Tomás Lucía Pucará Lámud Elías Soplín Pólvora Juanjuí Asunción Chiliquín Copallín Jazán Yamón Omía "
    "Jerónimo Pisuquía César Concepción Belén Ángel Huallaga Cuñumbuquí Chachapoyas Mariscal Víctor Óscar Raúl Germán Julián".split()}
def nombre(s):
    t = " ".join(WORD_ACC.get(w, w) for w in title_case(s).split())
    a = acentos().get(_key(t))
    if a and _key(a) == _key(t) and a.count(" ") == t.count(" "): return a
    return t

def merged(geoms):
    u = unary_union(list(geoms))
    if u.geom_type == "LineString": return [u]
    if u.geom_type == "MultiLineString":
        m = linemerge(u); return list(getattr(m, "geoms", [m]))
    return [g for g in getattr(u, "geoms", []) if g.geom_type == "LineString"]

def upright(ang):
    ang = (ang + 180) % 360 - 180
    if ang > 90: ang -= 180
    if ang < -90: ang += 180
    return ang

def along_labels(fr, geoms_by_name, every_mm, size, color, style="italic", weight="normal", z=19, spacing_min_mm=40,
                 family="Inter", h=1.4, min_len_mm=25, max_per=99):
    """Rótulos rotados a lo largo de líneas (ríos, vías)."""
    k = fr.scale / 1000  # metros por mm
    for name, geoms in geoms_by_name:
        name = name.replace("Rió ", "Río ").replace("Rio ", "Río ")
        parts = sorted(merged(geoms), key=lambda l: -l.length)
        n_done = 0
        for ln in parts:
            L = ln.length / k
            if L < min_len_mm: continue
            n = max(1, int(L // every_mm))
            for i in range(n):
                if n_done >= max_per: break
                d = (i + 0.5) * ln.length / n
                p = ln.interpolate(d); a = ln.interpolate(max(0, d - 4 * k)); b = ln.interpolate(min(ln.length, d + 4 * k))
                ang = upright(math.degrees(math.atan2(b.y - a.y, b.x - a.x)))
                if not fr.bbox.contains(p): continue
                t = fr.labels.place(p.x, p.y, name, size=size, color=color, style=style, weight=weight, rot=ang, z=z, family=family, h=h)
                if t is not None: n_done += 1

def shields(fr, vias, clase, fc, tc, every_mm=90, size=5.6, z=22, min_len_mm=20):
    k = fr.scale / 1000
    v = vias[(vias.clase == clase) & (vias.ref1 != "")]
    for ref, g in v.groupby("ref1"):
        for ln in merged(g.geometry):
            L = ln.length / k
            if L < min_len_mm: continue
            n = max(1, int(L // every_mm))
            for i in range(n):
                p = ln.interpolate((i + 0.5) / n, normalized=True)
                if not fr.bbox.contains(p): continue
                t = fr.labels.place(p.x, p.y, ref, size=size, color=tc, weight="bold", z=z, h=0,
                                    bbox=dict(boxstyle="round,pad=0.22,rounding_size=0.35", fc=fc, ec="white", lw=0.6))

def north_arrow(ax, x, y, s=12):
    ax.add_patch(MPoly([(x, y + s), (x - s * 0.36, y - s * 0.45), (x, y - s * 0.18)], closed=True, fc="#222", ec="#222", lw=0.5, zorder=40))
    ax.add_patch(MPoly([(x, y + s), (x + s * 0.36, y - s * 0.45), (x, y - s * 0.18)], closed=True, fc="white", ec="#222", lw=0.5, zorder=40))
    ax.text(x, y + s + 1.5, "N", ha="center", va="bottom", fontsize=s * 0.95, weight="bold", zorder=40)

def scale_bar(ax, x, y, scale, km_total, step_km, h=2.4, label=True):
    L = km_total * 1e6 / scale
    n = int(km_total / step_km)
    for i in range(n):
        x0 = x + i * L / n
        ax.add_patch(Rectangle((x0, y), L / n, h, fc="#222" if i % 2 == 0 else "white", ec="#222", lw=0.5, zorder=40))
    # subdivisión del primer tramo
    sub = 4; Ls = L / n / sub
    for i in range(sub):
        ax.add_patch(Rectangle((x - (i + 1) * Ls, y), Ls, h, fc="white" if i % 2 == 0 else "#222", ec="#222", lw=0.5, zorder=40))
    ax.text(x - L / n, y + h + 1.2, f"{step_km:g}", ha="center", va="bottom", fontsize=6.5)
    for i in range(n + 1):
        ax.text(x + i * L / n, y + h + 1.2, f"{i * step_km:g}", ha="center", va="bottom", fontsize=6.5)
    ax.text(x + L + 3, y + h / 2, "km", ha="left", va="center", fontsize=6.5)

class Legend:
    """Leyenda dibujada en mm dentro de un eje de página."""
    def __init__(self, ax, x, y, w, row=6.2, sym_w=11, size=7):
        self.ax, self.x, self.y, self.w, self.row, self.sw, self.size = ax, x, y, w, row, sym_w, size
        self.cy = y
    def header(self, s):
        self.cy -= self.row * 0.35
        self.ax.text(self.x, self.cy, s.upper(), fontsize=self.size + 0.6, weight="bold", va="center", color=C["texto"])
        self.ax.plot([self.x, self.x + self.w], [self.cy - 2.6, self.cy - 2.6], lw=0.4, color="#999")
        self.cy -= self.row * 1.05
    def _lab(self, s):
        self.ax.text(self.x + self.sw + 3, self.cy, s, fontsize=self.size, va="center", color=C["texto"], linespacing=1.05)
    def line(self, s, color, lw, ls="-", casing=None, under=None, alpha=1):
        xs = [self.x, self.x + self.sw]
        if under: self.ax.plot(xs, [self.cy] * 2, color=under[0], lw=under[1], alpha=under[2] if len(under) > 2 else 1, solid_capstyle="butt")
        if casing: self.ax.plot(xs, [self.cy] * 2, color=casing[0], lw=casing[1], solid_capstyle="butt")
        self.ax.plot(xs, [self.cy] * 2, color=color, lw=lw, ls=ls, solid_capstyle="butt", alpha=alpha)
        self._lab(s); self.cy -= self.row
    def box(self, s, fc="none", ec="#333", lw=0.6, hatch=None, alpha=1, ls="-"):
        self.ax.add_patch(Rectangle((self.x, self.cy - 2.1), self.sw, 4.2, fc=fc, ec=ec, lw=lw, hatch=hatch, alpha=alpha, ls=ls))
        self._lab(s); self.cy -= self.row
    def band(self, s, color, lw_line, band_w):
        # banda interior (como en el mapa): línea + franja semitransparente
        self.ax.add_patch(Rectangle((self.x, self.cy - 2.1), self.sw, 4.2, fc=color, alpha=0.10, ec="none"))
        self.ax.add_patch(Rectangle((self.x, self.cy + 2.1 - band_w), self.sw, band_w, fc=color, alpha=0.35, ec="none"))
        self.ax.plot([self.x, self.x + self.sw], [self.cy + 2.1] * 2, color=color, lw=lw_line)
        self._lab(s); self.cy -= self.row
    def marker(self, s, **kw):
        self.ax.plot([self.x + self.sw / 2], [self.cy], ls="none", **kw)
        self._lab(s); self.cy -= self.row
    def glyph(self, s, g, color, size=9, family="DejaVu Sans", bg=None):
        self.ax.text(self.x + self.sw / 2, self.cy, g, fontsize=size, color=color, ha="center", va="center", family=family,
                     bbox=bg)
        self._lab(s); self.cy -= self.row
    def shield(self, s, txt, fc, tc):
        self.ax.text(self.x + self.sw / 2, self.cy, txt, fontsize=5.6, color=tc, weight="bold", ha="center", va="center",
                     bbox=dict(boxstyle="round,pad=0.22,rounding_size=0.35", fc=fc, ec="white", lw=0.6))
        self._lab(s); self.cy -= self.row
    def text(self, s, size=None, color=None, style="normal"):
        self.ax.text(self.x, self.cy, s, fontsize=size or self.size - 0.5, color=color or C["gris"], va="center", style=style, linespacing=1.15)
        self.cy -= self.row * (s.count("\n") + 1) * 0.85
    def gap(self, k=0.5): self.cy -= self.row * k

# símbolos puntuales comunes (glifos DejaVu)
GLYPH = {"aerodromo": "✈", "puerto": "⚓", "helipuerto": "Ⓗ"}

def draw_points(fr, pts, z=24):
    """Dibuja símbolos operativos. Devuelve lista de (x,y,clase,nombre) dibujados."""
    out = []
    st = {
        "peaje":    dict(marker="s", ms=5.2, mfc="#f2c200", mec="#3b3b3b", mew=0.6),
        "pesaje":   dict(marker="D", ms=4.6, mfc="#ff8f00", mec="#3b3b3b", mew=0.6),
        "control":  dict(marker="^", ms=5.4, mfc="#ef5350", mec="#3b0000", mew=0.6),
        "frontera": dict(marker="h", ms=6.4, mfc="#c62828", mec="white", mew=0.7),
        "sunat":    dict(marker="p", ms=6.6, mfc="#0d47a1", mec="white", mew=0.7),
        "policia":  dict(marker="o", ms=3.4, mfc="#1565c0", mec="white", mew=0.4),
        "grifo":    dict(marker="o", ms=2.8, mfc="#6a1b9a", mec="white", mew=0.35),
    }
    for c, s in st.items():
        g = pts[pts.clase == c]
        if len(g):
            fr.ax.plot(g.geometry.x, g.geometry.y, ls="none", zorder=z, **s)
            for p in g.geometry: fr.labels.obstacle(p.x, p.y, s["ms"] * PT * 0.55)
    for c, gl in GLYPH.items():
        g = pts[pts.clase == c]
        for p in g.geometry:
            fr.ax.text(p.x, p.y, gl, fontsize=8.5 if c != "helipuerto" else 6, color="#0b3d91" if c == "aerodromo" else "#0b5394",
                       ha="center", va="center", family="DejaVu Sans", zorder=z, path_effects=halo(1.6), clip_on=True)
            fr.labels.obstacle(p.x, p.y, 1.5)
    return out

# ---------------------------------------------------------------- recuadros de ubicación
# Tonos de un solo color (salvia/oliva), acordes al estilo de los mapas murales
UBI = dict(mar="#e2ecf1", vecinos="#ecebe6", vecinos_borde="#c8c5bb", peru="#eef1e6", borde_peru="#6f7d63",
           tonos=["#f3f5ee", "#e6ebdd", "#d9e1cd", "#ccd7bd", "#bfccad"], medio="#c3cfb2", destaque="#6b8257",
           texto="#4f5948", oscuro="#36432f", marco="#2f3a29", pais="#8a8a8a", oceano="#7d9bb0")

def colorear(geoms, n):
    """Índice de tono (0..n-1) para cada polígono, distinto del de sus vecinos (coloreo voraz por grado)."""
    idx = range(len(geoms))
    vec = {i: [j for j in idx if j != i and geoms[i].distance(geoms[j]) < 2000] for i in idx}
    col = {}
    for i in sorted(idx, key=lambda i: -len(vec[i])):
        usados = {col[j] for j in vec[i] if j in col}
        col[i] = next((c for c in range(n) if c not in usados), 0)
    return [col[i] for i in idx]
