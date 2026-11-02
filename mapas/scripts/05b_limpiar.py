# Limpia las capas disueltas (INEI): rellena huecos-astilla entre distritos y elimina fragmentos mínimos,
# para que no aparezcan como falsos tramos de frontera o de límite.
import geopandas as gpd, warnings
from shapely.geometry import Polygon, MultiPolygon
warnings.filterwarnings("ignore")
HUECO, PARTE = 2e7, 1e6          # m²: huecos < 20 km² y partes < 1 km²
def limpiar(geom):
    ps = []
    for p in getattr(geom, "geoms", [geom]):
        if p.geom_type != "Polygon" or p.area < PARTE: continue
        ps.append(Polygon(p.exterior, [r for r in p.interiors if Polygon(r).area >= HUECO]))
    return MultiPolygon(ps) if len(ps) > 1 else ps[0]
for base, crs in [("/home/user/data_base", 4326), ("/home/user/data_base/utm", 32718)]:
    for n in ["peru", "circunscripciones", "regimen", "departamentos", "provincias"]:
        g = gpd.read_file(f"{base}/{n}.gpkg")
        g_m = g.to_crs(32718)
        g_m["geometry"] = g_m.geometry.map(limpiar)
        g_m.to_crs(crs).to_file(f"{base}/{n}.gpkg", driver="GPKG")
        print(base.split("/")[-1], n, "ok")
