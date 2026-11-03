# Navegabilidad por altitud: los tramos de ríos "navegables" o de la hidrovía situados a más de 650 m s. n. m.
# (cañones y valles andinos) pasan a la clase "rio". Se parte cada río en tramos de ~2 km y se toma la cota
# del MDE (AWS Terrain Tiles, nivel 8) en el punto medio de cada tramo.
import numpy as np, pandas as pd, geopandas as gpd, rasterio, warnings
from shapely.ops import substring
from pyproj import Transformer
warnings.filterwarnings("ignore")
U = "/home/user/data_base/utm"; DEM = "/home/user/data_base/dem_peru_z8.tif"
LIM, PASO = 650, 2000
T = Transformer.from_crs(32718, 3857, always_xy=True)

def partir(g):
    out = []
    for ln in getattr(g, "geoms", [g]):
        n = max(1, int(np.ceil(ln.length / PASO)))
        out += [substring(ln, i * ln.length / n, (i + 1) * ln.length / n) for i in range(n)]
    return out

with rasterio.open(DEM) as src:
    for f in ["rios", "pf_rios"]:
        r = gpd.read_file(f"{U}/{f}.gpkg")
        es_nav = r.clase.isin(["navegable", "hidrovia"])
        filas = []
        for row in r[es_nav].itertuples(index=False):
            piezas = partir(row.geometry)
            mids = [p.interpolate(0.5, normalized=True) for p in piezas]
            X, Y = T.transform([m.x for m in mids], [m.y for m in mids])
            z = np.array([v[0] for v in src.sample(zip(X, Y))])
            d = row._asdict()
            for p, zz in zip(piezas, z):
                filas.append({**d, "clase": d["clase"] if zz < LIM else "rio", "geometry": p})
        nav = gpd.GeoDataFrame(filas, geometry="geometry", crs=r.crs)
        antes = r[es_nav].groupby("clase").geometry.apply(lambda s: s.length.sum() / 1000).round()
        despues = nav.groupby("clase").geometry.apply(lambda s: s.length.sum() / 1000).round()
        out = pd.concat([r[~es_nav], nav], ignore_index=True)
        gpd.GeoDataFrame(out, geometry="geometry", crs=r.crs).to_file(f"{U}/{f}.gpkg", driver="GPKG")
        print(f, "km antes:", antes.to_dict(), "→ después:", despues.to_dict())
