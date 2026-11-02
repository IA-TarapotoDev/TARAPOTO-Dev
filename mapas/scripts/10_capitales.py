# Capitales distritales con coordenadas oficiales (INEI, vía jmcastagnetto/ubigeo-peru-aumentado),
# cruzadas con OpenStreetMap para el nombre con tildes y la población; más ciudades y pueblos no capitales.
import sys, unicodedata, numpy as np, pandas as pd, geopandas as gpd, warnings
warnings.filterwarnings("ignore")
B = "/home/user/data_base"; U = f"{B}/utm"
def key(s):
    s = "".join(c for c in unicodedata.normalize("NFD", str(s).lower()) if unicodedata.category(c) != "Mn")
    return " ".join(s.replace("-", " ").replace("ñ", "n").split())
c = pd.read_csv(f"{B}/ubg_ubigeo_distrito.csv", dtype={"inei": str})
c["latitude"] = pd.to_numeric(c.latitude, errors="coerce"); c["longitude"] = pd.to_numeric(c.longitude, errors="coerce")
c = c[c.latitude.notna() & c.longitude.notna()].copy()
c["pop_dist"] = pd.to_numeric(c.pob_densidad_2020, errors="coerce") * pd.to_numeric(c.superficie, errors="coerce")
g = gpd.GeoDataFrame(c, geometry=gpd.points_from_xy(c.longitude, c.latitude), crs=4326).to_crs(32718)
g["nivel"] = np.where(g.inei.str[2:] == "0101", 0, np.where(g.inei.str[4:] == "01", 1, 2))
osm = gpd.read_file(f"{U}/lugares.gpkg")
osm = osm[osm.place.isin(["city", "town", "village", "hamlet", "locality"])].copy()
osm["k"] = osm.name.map(key)
sx = osm.sindex
rows = []
for r in g.itertuples():
    kc = key(r.capital)
    cand = osm.iloc[list(sx.query(r.geometry.buffer(4000)))]
    cand = cand.assign(d=cand.distance(r.geometry))
    mask = np.array([bool(set(kc.split()) & set(k.split())) for k in cand.k], dtype=bool)
    ok = cand[mask] if len(cand) else cand
    ok = ok[ok.d < 4000].sort_values("d")
    if len(ok):
        m = ok.iloc[0]
        geom = m.geometry if m.d < 1500 else r.geometry
        rows.append(dict(ubigeo=r.inei, departamento=r.departamento, provincia=r.provincia, distrito=r.distrito, nombre=m["name"],
                         nombre_inei=r.capital, nivel=r.nivel, pop_osm=m["pop"], pop_dist=r.pop_dist, d_osm=m.d, geometry=geom))
    else:
        rows.append(dict(ubigeo=r.inei, departamento=r.departamento, provincia=r.provincia, distrito=r.distrito, nombre=r.capital,
                         nombre_inei=r.capital, nivel=r.nivel, pop_osm=np.nan, pop_dist=r.pop_dist, d_osm=np.nan, geometry=r.geometry))
cap = gpd.GeoDataFrame(rows, crs=32718)
cap["pop"] = cap.pop_osm.fillna(cap.pop_dist * 0.35)
circ = gpd.read_file(f"{U}/circunscripciones.gpkg")
tara = circ[circ.circ == "IA TARAPOTO"].geometry.iloc[0]
cap["in_ia"] = cap.within(tara.buffer(200))
cap.to_file(f"{U}/capitales.gpkg", driver="GPKG")
# otras ciudades/pueblos (no capitales): place=city/town de OSM a más de 2 km de una capital
o = osm[(osm.place.isin(["city", "town"]) | ((osm.place == "village") & (osm["pop"] >= 2000))) & osm.pe].copy()
o = o[o.geometry.apply(lambda p: cap.distance(p).min() > 2000)]
capk = cap.assign(k=cap.nombre.map(key))
o = o[[not ((capk.k == key(n)) & (capk.distance(p) < 15000)).any() for n, p in zip(o.name, o.geometry)]]   # sin duplicados de capitales
o["in_ia"] = o.within(tara)
o[["name", "place", "pop", "in_ia", "geometry"]].to_file(f"{U}/otros_poblados.gpkg", driver="GPKG")
ia = cap[cap.in_ia]
print("capitales en IA:", len(ia), "| con población OSM:", ia.pop_osm.notna().sum(), "| sin cruce OSM:", ia.d_osm.isna().sum(),
      "| desplazadas >1.5 km (se usa INEI):", (ia.d_osm >= 1500).sum())
print(ia.sort_values("pop", ascending=False)[["nombre", "distrito", "nivel", "pop", "pop_osm"]].head(25).to_string())
print("sin cruce OSM:", ia[ia.d_osm.isna()][["nombre", "distrito"]].values.tolist())
print("otros poblados en IA:", int(o.in_ia.sum()), o[o.in_ia].sort_values("pop", ascending=False)[["name", "pop"]].head(15).values.tolist())
