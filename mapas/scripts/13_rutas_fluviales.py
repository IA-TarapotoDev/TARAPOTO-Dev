# Rutas fluviales de salida desde los puertos de la IA Tarapoto y puntos de salida de la jurisdicción y del país.
# El kilometraje se mide sobre el eje de los ríos de OSM (longitud geodésica, WGS 84).
import json, numpy as np, geopandas as gpd, networkx as nx, warnings
from shapely.geometry import Point, LineString, MultiLineString
from shapely.ops import unary_union, linemerge
from pyproj import Geod, Transformer
warnings.filterwarnings("ignore")
U = "/home/user/data_base/utm"; B = "/home/user/data_base"
GEOD = Geod(ellps="WGS84")
TO_LL = Transformer.from_crs(32718, 4326, always_xy=True)
TO_UTM = Transformer.from_crs(4326, 32718, always_xy=True)

rios = gpd.read_file(f"{U}/pf_rios.gpkg")
peru = gpd.read_file(f"{U}/peru.gpkg").geometry.iloc[0].simplify(150)
circ = gpd.read_file(f"{U}/circunscripciones.gpkg"); tara = circ[circ.circ == "IA TARAPOTO"].geometry.iloc[0].simplify(150)
pa = gpd.read_file(f"{U}/paises_ubicacion.gpkg"); pa = pa[pa.name != "Perú"]
nav = rios[rios.clase.isin(["hidrovia", "navegable"])].copy()
nav["name"] = nav["name"].fillna("").str.replace(" / Rio Javari", "", regex=False)   # el Yavarí figura con dos nombres en OSM

# ---------------- grafo de la red navegable
G = nx.Graph()
for g in nav.geometry:
    for ln in getattr(g, "geoms", [g]):
        c = [(round(x, 1), round(y, 1)) for x, y in ln.coords]
        for a, b in zip(c, c[1:]):
            if a != b: G.add_edge(a, b, w=float(np.hypot(a[0] - b[0], a[1] - b[1])))
nodes = np.array(list(G.nodes))
print("grafo:", flush=True) if False else print("grafo:", G.number_of_nodes(), "nodos,", nx.number_connected_components(G), "componentes")
def nodo(x, y):
    i = np.argmin((nodes[:, 0] - x) ** 2 + (nodes[:, 1] - y) ** 2); return tuple(nodes[i])
def km_geo(coords):
    lon, lat = TO_LL.transform(*np.array(coords).T)
    return GEOD.line_length(lon, lat) / 1000

# ---------------- salidas del país: cruces de ríos navegables con el límite nacional
def cruces(lineas, limite, tol):
    """Cruces de cada río con el límite; se deduplican los puntos del mismo río a menos de `tol` m."""
    pts = []
    for g, n in zip(lineas.geometry, lineas["name"]):
        ip = g.intersection(limite)
        for p in getattr(ip, "geoms", [ip]):
            if p.is_empty or p.geom_type != "Point": continue
            if all(p.distance(q) > tol or m != n for q, m, _ in pts): pts.append((p, n, g))
    return pts
borde = peru.boundary.intersection(unary_union(list(pa.geometry)).buffer(5000))   # límite terrestre (sin la costa)
borde_b = borde.buffer(1500)
cerca = nav[nav.intersects(borde_b)]
xs = cruces(cerca, borde, 15000)
crudos = []
for p, n, g in xs:
    vec = pa[pa.distance(p) < 5000]
    lon, lat = TO_LL.transform(p.x, p.y)
    crudos.append(dict(rio=n or "s/n", pais=", ".join(sorted(set(vec.name))), x=p.x, y=p.y, lon=lon, lat=lat,
                       en_ia=bool(tara.buffer(3000).contains(p))))
# ríos fronterizos (el río corre a lo largo del límite): longitud a < 1,5 km del límite
fronterizos = {}
for n, g in cerca.groupby("name"):
    if not n: continue
    lg = unary_union(list(g.geometry)).intersection(borde_b).length / 1000
    if lg > 100: fronterizos[n] = round(lg)
print("ríos fronterizos (km junto al límite):", fronterizos)

# punto representativo de cada río: en los ríos fronterizos, el extremo aguas abajo del tramo limítrofe
REGLA = {"Río Amazonas": "max_x", "Río Putumayo": "max_x", "Río Yavarí": "max_x",
         "Río Purús": "max_x", "Río Heath": "max_y", "Río Napo": "max_y"}
salidas_pais = []
for n in dict.fromkeys(c["rio"] for c in crudos):
    cs = [c for c in crudos if c["rio"] == n]
    regla = REGLA.get(n)
    if regla == "max_x": c = max(cs, key=lambda c: c["x"])
    elif regla == "max_y": c = max(cs, key=lambda c: c["y"])
    else: c = cs[0]
    salidas_pais.append(dict(c, fronterizo=n in fronterizos, n_cruces=len(cs)))
# afluentes que llegan al límite junto a otro río de salida (mismo punto): se omiten
salidas_pais = [s_ for s_ in salidas_pais if s_["rio"] not in ("Río Yaguas", "Río Algodón", "Río Heath")]
# el Heath desemboca en el Madre de Dios en la frontera con Bolivia (Puerto Pardo)
for s_ in salidas_pais:
    if not s_["pais"] and s_["lon"] > -70.5 and s_["lat"] < -10: s_["pais"] = "Bolivia"

# ---------------- salidas de la jurisdicción: cruces de ríos navegables con el límite de la IA Tarapoto (fuera de la frontera)
limite_ia = tara.boundary.difference(borde.buffer(2000))
xi = cruces(nav[nav.intersects(limite_ia.buffer(50))], limite_ia, 8000)
salidas_ia = []
for p, n, g in xi:
    ln = max(getattr(g, "geoms", [g]), key=lambda l: l.distance(p) * -1)
    d = ln.project(p); antes = ln.interpolate(max(0, d - 800)); despues = ln.interpolate(min(ln.length, d + 800))
    if not (tara.contains(antes) and not tara.contains(despues)): continue       # ingreso a la jurisdicción: se omite
    lon, lat = TO_LL.transform(p.x, p.y)
    vec = circ[(circ.circ != "IA TARAPOTO") & (circ.distance(p) < 3000)]
    salidas_ia.append(dict(rio=n or "s/n", hacia=", ".join(vec.circ), x=p.x, y=p.y, lon=lon, lat=lat))
print("salidas de la jurisdicción:", [(s["rio"], s["hacia"]) for s in salidas_ia])

# ---------------- rutas desde los puertos de la IA Tarapoto
PUERTOS = {"Yurimaguas": (-76.087, -5.892), "Saramiriza": (-77.4175, -4.564), "San Lorenzo": (-76.5546, -4.8316),
           "Santa María de Nieva": (-77.8667, -4.5938), "Puerto Galilea": (-77.7583, -4.0151)}
PASO = {"San Lorenzo": (-76.5546, -4.8316), "Lagunas": (-75.6797, -5.227), "Nauta": (-73.5555, -4.5085), "Iquitos": (-73.2472, -3.7437), "Pebas": (-71.82, -3.32),
        "Caballococha": (-70.51, -3.91), "Santa Rosa": (-69.96, -4.23)}
def ruta(origen, destino_xy, etiqueta, paradas=()):
    a = nodo(*TO_UTM.transform(*PUERTOS[origen])); b = nodo(*destino_xy)
    path = nx.shortest_path(G, a, b, weight="w")
    line = LineString(path)
    marcas = []
    P = np.array(path)
    for nm in paradas:
        xy = np.array(TO_UTM.transform(*PASO[nm]))
        dd = np.hypot(P[:, 0] - xy[0], P[:, 1] - xy[1]); i = int(np.argmin(dd))
        if dd[i] < 6000: marcas.append((nm, round(km_geo(path[:i + 1]), 1), list(TO_LL.transform(*path[i]))))
    # cruce con el límite de la IA (salida de la jurisdicción)
    km_ia = None
    ip = line.intersection(limite_ia)
    if not ip.is_empty:
        pts = [q for q in getattr(ip, "geoms", [ip]) if q.geom_type == "Point"]
        if pts:
            q = min(pts, key=lambda q: line.project(q))
            sub = [c for c in path if line.project(Point(c)) <= line.project(q)] + [(q.x, q.y)]
            km_ia = round(km_geo(sub), 1)
    total = round(km_geo(path), 1)
    print(f"{etiqueta}: {total} km | salida IA km {km_ia} | {marcas}")
    return dict(etiqueta=etiqueta, origen=origen, km_total=total, km_salida_ia=km_ia, paradas=marcas,
                coords=[list(TO_LL.transform(x, y)) for x, y in path])

rutas = []
amazonas = [s for s in salidas_pais if "Amazonas" in s["rio"]]
if amazonas:
    dst = max(amazonas, key=lambda s: s["x"])          # el cruce más oriental del Amazonas (Santa Rosa)
    rutas.append(ruta("Yurimaguas", (dst["x"], dst["y"]), "Yurimaguas → frontera (río Amazonas)",
                      ["Lagunas", "Nauta", "Iquitos", "Pebas", "Caballococha", "Santa Rosa"]))
    rutas.append(ruta("Saramiriza", (dst["x"], dst["y"]), "Saramiriza → frontera (río Amazonas)", ["San Lorenzo", "Nauta", "Iquitos"]))
for rio, origen in [("Pastaza", "San Lorenzo"), ("Morona", "Saramiriza"), ("Santiago", "Santa María de Nieva")]:
    cand = [s for s in salidas_pais if rio in s["rio"]]
    if cand:
        d = min(cand, key=lambda s: s["y"])  # cruce más al sur (entrada desde Ecuador)
        rutas.append(ruta(origen, (d["x"], d["y"]), f"{origen} → frontera con Ecuador (río {rio})"))
json.dump(dict(salidas_pais=salidas_pais, salidas_ia=salidas_ia, fronterizos=fronterizos, rutas=rutas),
          open(f"{B}/rutas_fluviales.json", "w"), ensure_ascii=False, indent=1)
print("salidas del país:", [(s["rio"], s["pais"], s["en_ia"], s["fronterizo"], round(s["lon"], 3), round(s["lat"], 3)) for s in salidas_pais])
