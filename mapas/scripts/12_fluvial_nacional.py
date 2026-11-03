# Capas de la red fluvial de todo el Perú (OSM) para el mapa 3: ríos clasificados, lagos, poblados, puertos y vías principales
import os, re, pyogrio, geopandas as gpd, pandas as pd, numpy as np, warnings
from shapely.ops import unary_union
warnings.filterwarnings("ignore")
os.environ["OSM_CONFIG_FILE"] = "/home/user/mapas_scripts/osmconf.ini"
os.environ["OSM_USE_CUSTOM_INDEXING"] = "NO"
O = "/home/user/data_osm"; U = "/home/user/data_base/utm"

def leer(f, lyr):
    g = pyogrio.read_dataframe(f"{O}/{f}", layer=lyr)
    g.columns = [c.replace(":", "_") for c in g.columns]
    return g

# Hidrovía Amazónica (MTC): Amazonas, Marañón (Saramiriza–confluencia), Huallaga (Yurimaguas–confluencia) y Ucayali
NAV = ("Napo|Putumayo|Yavar|Javari|Tigre|Pastaza|Morona|Santiago|Corrientes|Nanay|Itaya|Samiria|Tapiche|Yaguas|Ampiyacu|Curaray|Arabela|"
       "Mazán|Mazan|Urubamba|Tambo|Ene|Pachitea|Aguayt|Purús|Purus|Yurúa|Yurua|Juruá|Madre de Dios|Tambopata|Las Piedras|Manu|Inambari|"
       "Tahuamanu|Heath|Nieva|Cenepa|Potro|Cahuapanas|Paranapura|Chambira|Urituyacu|Huasaga|Pacaya|Algodón|Algodon|Mayo|Cushabatay|Pisqui|"
       "Pichis|Palcazu|Sepahua|Mishagua|Camisea|Apurímac|Apurimac|Perené|Perene")

w = leer("pf_agua.osm.pbf", "lines")
w = w[w.waterway.isin(["river", "canal"]) & w.geometry.notna()].copy()
w.loc[w.wikidata == "Q3783", "name"] = "Río Amazonas"
w["name"] = w["name"].fillna("").str.replace(r"^Rio ", "Río ", regex=True).str.replace(r"^Rió ", "Río ", regex=True)
w = w.to_crs(32718)
def clase(r):
    n = r["name"]; c = r.geometry.centroid
    lon, lat = gpd.GeoSeries([c], crs=32718).to_crs(4326).iloc[0].coords[0]
    if r.waterway != "river": return "canal"
    if "Amazonas" in n or "Ucayali" in n: return "hidrovia"
    if "Marañ" in n:
        if lat <= -5.5: return "rio"                     # Marañón alto (Andes): no navegable
        return "hidrovia" if lon > -77.43 else "navegable"
    if "Huallaga" in n: return "hidrovia" if lat > -5.92 else "rio"
    if re.search(NAV, n) and not re.search(r"^(Quebrada|Caño|Cocha)\b", n): return "navegable"
    return "rio"
w["clase"] = w.apply(clase, axis=1)
w[["clase", "name", "waterway", "geometry"]].to_file(f"{U}/pf_rios.gpkg", driver="GPKG")
print("ríos:", w.clase.value_counts().to_dict())

a = leer("pf_agua.osm.pbf", "multipolygons")
a = a[(a.natural == "water") | a.water.notna()].to_crs(32718)
a = a[a.area > 3e6]
a["tipo"] = np.where(a.water.fillna("").isin(["river", "oxbow"]), "rio", "lago")
a[["tipo", "name", "geometry"]].to_file(f"{U}/pf_agua.gpkg", driver="GPKG")
print("agua (polígonos > 3 km²):", len(a))

p = leer("pf_lugares.osm.pbf", "points")
p = p[p.name.notna()].to_crs(32718)
p["pop"] = pd.to_numeric(p.population.astype(str).str.replace(r"[^\d]", "", regex=True), errors="coerce")
p["cap"] = pd.to_numeric(p.capital, errors="coerce")
p[["name", "place", "pop", "cap", "geometry"]].to_file(f"{U}/pf_lugares.gpkg", driver="GPKG")
print("poblados:", len(p))

L = []
for lyr in ["points", "multipolygons"]:
    g = leer("pf_puntos.osm.pbf", lyr)
    if len(g):
        g["geometry"] = g.geometry.representative_point(); L.append(g)
q = gpd.GeoDataFrame(pd.concat(L, ignore_index=True), crs=4326).to_crs(32718)
nm = q["name"].fillna("")
def qclase(r):
    n = (r["name"] if isinstance(r["name"], str) else "").lower()
    if "sunat" in n or "aduan" in n or r.get("government") == "customs" or r.get("amenity") == "customs": return "sunat"
    if r.get("barrier") == "border_control" or "migraci" in n or "cebaf" in n: return "frontera"
    if r.get("amenity") == "ferry_terminal" or r.get("landuse") in ("harbour", "port") or r.get("harbour") == "yes" or r.get("office") == "harbour_master" or r.get("man_made") == "pier": return "puerto"
    return None
q["clase"] = q.apply(qclase, axis=1)
q = q[q.clase.notna()]
q[["clase", "name", "geometry"]].to_file(f"{U}/pf_puntos.gpkg", driver="GPKG")
print("puntos:", q.clase.value_counts().to_dict())

v = leer("pf_vias.osm.pbf", "lines").to_crs(32718)
v["ref1"] = v.ref.fillna("").str.split(";").str[0].str.strip()
v = v[v.ref1.str.startswith("PE-") | v.highway.isin(["trunk"])]
v[["highway", "ref1", "geometry"]].to_file(f"{U}/pf_vias.gpkg", driver="GPKG")
print("vías principales:", len(v))
