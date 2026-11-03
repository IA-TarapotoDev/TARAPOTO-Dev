# Prepara capas clasificadas y reproyectadas a UTM 18S (EPSG:32718) para los tres mapas
import re, geopandas as gpd, pandas as pd, numpy as np, warnings
from shapely.geometry import box
warnings.filterwarnings("ignore")
B = "/home/user/data_base"; O = f"{B}/utm"; import os; os.makedirs(O, exist_ok=True)
EXT = box(-80.6, -11.4, -72.4, -1.8)
def save(g, n): g.to_crs(32718).to_file(f"{O}/{n}.gpkg", driver="GPKG"); print(n, len(g), flush=True)

# --- vías
v = gpd.read_file(f"{B}/osm/vias_lines.gpkg")
def vclase(r):
    ref = (r.ref or "") if isinstance(r.ref, str) else ""
    refs = [x.strip() for x in ref.split(";") if x.strip()]
    if any(x.startswith("PE-") for x in refs): return "nacional"
    if any(re.match(r"^[A-Z]{2}-1\d\d[A-Z]?$", x) for x in refs): return "departamental"
    if any(re.match(r"^[A-Z]{2}-\d{3,4}[A-Z]?$", x) for x in refs): return "vecinal"
    h = r.highway.replace("_link", "")
    if h in ("motorway", "trunk", "primary"): return "nacional"
    if h == "secondary": return "departamental"
    if h in ("tertiary", "unclassified", "road"): return "vecinal"
    return "trocha"
v["clase"] = v.apply(vclase, axis=1)
v["ref1"] = v.ref.fillna("").str.split(";").str[0].str.strip()
save(v[["clase", "highway", "ref1", "name", "surface", "bridge", "geometry"]], "vias")

# --- ríos
w = gpd.read_file(f"{B}/osm/agua_lines.gpkg")
w = w[w.waterway.isin(["river", "stream", "canal"])].copy()
w.loc[w.wikidata == "Q3783", "name"] = "Río Amazonas"
NAV = "Santiago|Morona|Pastaza|Tigre|Napo|Corrientes|Nieva|Cenepa|Potro|Cahuapanas|Paranapura|Samiria|Nanay|Itaya|Chambira|Urituyacu|Apaga|Huasaga|Manit|Aipena|Pacaya|Yanayacu|Tapiche|Shishinahua|Chiriaco|Mayo"
def rclase(r):
    n = r["name"] if isinstance(r["name"], str) else ""
    c = r.geometry.centroid
    if r.waterway != "river": return "quebrada" if r.waterway == "stream" else "canal"
    if "Amazonas" in n or "Ucayali" in n: return "hidrovia"
    if "Marañ" in n:
        if c.y <= -5.5: return "rio"                     # Marañón alto (Andes): no navegable
        return "hidrovia" if c.x > -77.43 else "navegable"
    if "Huallaga" in n:
        return "hidrovia" if c.y > -5.92 else "rio"
    if re.search(NAV, n) and r.geometry.length > 0: return "navegable"
    return "rio"
w["clase"] = w.apply(rclase, axis=1)
save(w[["clase", "waterway", "name", "geometry"]], "rios")
a = gpd.read_file(f"{B}/osm/agua_multipolygons.gpkg")
a = a[(a.natural == "water") | a.water.notna() | (a.waterway == "riverbank")].copy()
a = a.to_crs(32718); a = a[a.area > 20000]
a["tipo"] = np.where(a.water.fillna("").isin(["river", "oxbow"]) | (a.waterway == "riverbank"), "rio", "lago")
a.to_crs(4326).pipe(lambda g: save(g[["tipo", "name", "geometry"]], "agua_poly"))
wl = gpd.read_file(f"{B}/osm/agua_multipolygons.gpkg"); wl = wl[wl.natural == "wetland"]
save(wl[["name", "geometry"]], "humedales")

# --- lugares
p = gpd.read_file(f"{B}/osm/lugares_points.gpkg")
p = p[p.place.isin(["city", "town", "village", "hamlet", "locality", "isolated_dwelling"]) & p.name.notna()]
p["pop"] = pd.to_numeric(p.population.astype(str).str.replace(r"[^\d]", "", regex=True), errors="coerce")
p["cap"] = pd.to_numeric(p.capital, errors="coerce")
save(p[["name", "place", "pop", "cap", "geometry"]], "lugares")

# --- puntos operativos
save(gpd.read_file(f"{B}/puntos_operativos.gpkg"), "puntos")

# --- áreas protegidas
l = gpd.read_file(f"{B}/osm/limites_multipolygons.gpkg")
pa = l[l.boundary.isin(["protected_area", "national_park"]) | (l.leisure == "nature_reserve")].copy()
pa = pa[pa.name.notna()]
save(pa[["name", "protect_class", "protection_title", "geometry"]], "anp")

# --- límites
for n in ["distritos_tematico", "provincias", "departamentos", "circunscripciones", "regimen", "peru"]:
    save(gpd.read_file(f"{B}/{n}.gpkg"), n)
ad = gpd.read_file(f"{B}/osm/admin24.gpkg")
save(ad[(ad.admin_level == "2") & (ad.name != "Perú")], "paises")
save(ad[(ad.admin_level == "4") & ad["ISO3166-2"].fillna("").str[:2].isin(["EC", "CO", "BR"])], "prov_extranjeras")
