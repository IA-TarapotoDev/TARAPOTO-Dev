# Consolida puntos operativos públicos de OSM (peajes, pesaje, control, grifos, policía, puertos, aeródromos)
import geopandas as gpd, pandas as pd, numpy as np, warnings
warnings.filterwarnings("ignore")
D = "/home/user/data_base/osm"
L = []
for f in ["puntos_points", "puntos_multipolygons", "vias_points", "puntos_lines"]:
    g = gpd.read_file(f"{D}/{f}.gpkg"); g["src"] = f
    g["geometry"] = g.geometry.representative_point(); L.append(g)
g = pd.concat(L, ignore_index=True)
g = gpd.GeoDataFrame(g, geometry="geometry", crs="EPSG:4326")
nm = g["name"].fillna("")
def cls(r):
    n = (r["name"] or "") if isinstance(r["name"], str) else ""
    nl = n.lower()
    if "sunat" in nl or "aduan" in nl or r.get("government") == "customs" or r.get("amenity") == "customs": return "sunat"
    if r.get("barrier") == "border_control" or "cebaf" in nl or "migraci" in nl or r.get("government") == "migration": return "frontera"
    if r.get("barrier") == "toll_booth" or "peaje" in nl: return "peaje"
    if r.get("amenity") == "weighbridge" or "pesaje" in nl or "balanza" in nl: return "pesaje"
    if r.get("military") == "checkpoint" or r.get("barrier") == "checkpoint" or r.get("highway") == "checkpoint" or "garita" in nl or ("control" in nl and "puesto" in nl): return "control"
    if r.get("amenity") == "police": return "policia"
    if r.get("amenity") == "fuel": return "grifo"
    if r.get("aeroway") in ("aerodrome", "airstrip"): return "aerodromo"
    if r.get("aeroway") in ("helipad", "heliport"): return "helipuerto"
    if r.get("amenity") == "ferry_terminal" or r.get("landuse") in ("port", "harbour") or r.get("harbour") == "yes" or r.get("man_made") in ("pier", "jetty") or r.get("leisure") in ("marina", "slipway") or r.get("office") == "harbour_master": return "puerto"
    if r.get("military") in ("base", "barracks", "camp", "naval_base", "airfield") or r.get("landuse") == "military": return "militar"
    if r.get("amenity") == "townhall": return "municipalidad"
    if r.get("natural") == "peak": return "cumbre"
    if r.get("mountain_pass") == "yes" or r.get("natural") == "saddle": return "abra"
    return None
g["clase"] = g.apply(cls, axis=1)
g = g[g["clase"].notna()].copy()
# deduplicar: misma clase a < 250 m
m = g.to_crs(32718); m["x"] = m.geometry.x.round(-2.4 if False else 0); 
keep = []; seen = {}
m["k"] = m["clase"] + "_" + (m.geometry.x // 250).astype(int).astype(str) + "_" + (m.geometry.y // 250).astype(int).astype(str)
m = m.sort_values("name", na_position="last").drop_duplicates("k")
out = m.to_crs(4326)
cols = [c for c in ["clase", "name", "operator", "brand", "amenity", "barrier", "aeroway", "iata", "icao", "military", "government", "office", "ele", "src", "geometry"] if c in out]
out = out[cols]
out.to_file("/home/user/data_base/puntos_operativos.gpkg", driver="GPKG")
print(out.clase.value_counts().to_string())
