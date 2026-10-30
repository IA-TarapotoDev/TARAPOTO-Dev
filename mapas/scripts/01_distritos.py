# Convierte perumapas/mapa_distrital.rda (sf) a GeoPackage
import sys, warnings, rdata, numpy as np, geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
warnings.filterwarnings("ignore")
src, dst = sys.argv[1], sys.argv[2]
c = rdata.conversion.convert(rdata.parser.parse_file(src), default_encoding="utf8")["mapa_distrital"]
geoms = []
for g in c["geometry"]:
    polys = [Polygon(np.asarray(p[0])[:, :2], [np.asarray(h)[:, :2] for h in p[1:]]) for p in g]
    geoms.append(MultiPolygon(polys))
df = c.drop(columns="geometry").astype(str)
gdf = gpd.GeoDataFrame(df, geometry=geoms, crs="EPSG:4326")
gdf["geometry"] = gdf.buffer(0)
gdf.to_file(dst, driver="GPKG")
print(gdf.shape, gdf.total_bounds, gdf.departamento.nunique(), gdf.provincia.nunique())
