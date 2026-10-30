# Ruta fluvial Iquitos -> Yurimaguas por Amazonas, Marañón y Huallaga (ejes OSM), distancia en km
import json, geopandas as gpd, networkx as nx, numpy as np, warnings
from shapely.geometry import LineString, Point
from shapely.ops import linemerge
warnings.filterwarnings("ignore")
B = "/home/user/data_base"
w = gpd.read_file(f"{B}/osm/agua_lines.gpkg")
r = w[(w.waterway == "river") & (w.name.fillna("").str.contains("Marañ|Huallaga") | (w.wikidata == "Q3783"))].to_crs(32718)
r = r[~r.name.fillna("").str.contains("Brazo")]
G = nx.Graph()
for geom in r.geometry:
    for ln in getattr(geom, "geoms", [geom]):
        c = list(ln.coords)
        for a, b in zip(c, c[1:]):
            a = (round(a[0], 1), round(a[1], 1)); b = (round(b[0], 1), round(b[1], 1))
            G.add_edge(a, b, w=float(np.hypot(a[0] - b[0], a[1] - b[1])))
print("nodos", G.number_of_nodes(), "componentes", nx.number_connected_components(G))
nodes = np.array(list(G.nodes))
def near(lon, lat):
    p = gpd.GeoSeries([Point(lon, lat)], crs=4326).to_crs(32718).iloc[0]
    i = np.argmin((nodes[:, 0] - p.x) ** 2 + (nodes[:, 1] - p.y) ** 2); return tuple(nodes[i])
PTS = {"Iquitos": (-73.2472, -3.7437), "Nauta": (-73.5555, -4.5085), "Lagunas": (-75.6772, -5.2297), "Yurimaguas": (-76.0870, -5.8920)}
path = nx.shortest_path(G, near(*PTS["Iquitos"]), near(*PTS["Yurimaguas"]), weight="w")
line = LineString(path)
km = line.length / 1000 * 1.0004  # factor de escala UTM aprox.
stops = {n: round(line.project(Point(near(*p))) / 1000, 1) for n, p in PTS.items()}
print("Iquitos -> Yurimaguas:", round(km, 1), "km", stops)
ll = gpd.GeoSeries([line], crs=32718).to_crs(4326).iloc[0]
c = json.load(open(f"{B}/corredores.json"))
c["FLUVIAL"] = {"km_total": km, "km_zte": km, "segmentos": [{"desde_km": 0, "hasta_km": km, "regimen": "ZTE"}], "salidas": [],
                "paradas": [{"nombre": n, "km": k} for n, k in sorted(stops.items(), key=lambda x: x[1])],
                "vias": ["Río Amazonas", "Río Marañón", "Río Huallaga"], "coords": [list(p) for p in ll.coords]}
json.dump(c, open(f"{B}/corredores.json", "w"), ensure_ascii=False)
