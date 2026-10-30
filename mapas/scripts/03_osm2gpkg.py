# Convierte los extractos temáticos OSM (.pbf) a GeoPackage
import os, sys, pyogrio, geopandas as gpd, warnings
warnings.filterwarnings("ignore")
os.environ["OSM_CONFIG_FILE"] = "/home/user/mapas_scripts/osmconf.ini"
os.environ["OSM_USE_CUSTOM_INDEXING"] = "NO"
os.environ["OGR_INTERLEAVED_READING"] = "YES"
src = "/home/user/data_osm"; dst = "/home/user/data_base/osm"; os.makedirs(dst, exist_ok=True)
for name in ["vias", "agua", "lugares", "puntos", "limites"]:
    for lyr in ["points", "lines", "multilinestrings", "multipolygons"]:
        try:
            g = pyogrio.read_dataframe(f"{src}/{name}.osm.pbf", layer=lyr)
        except Exception as e:
            print(name, lyr, "ERR", e); continue
        if len(g) == 0: continue
        g = g.dropna(axis=1, how="all")
        g.columns = [c.replace(":", "_") for c in g.columns]
        g.to_file(f"{dst}/{name}_{lyr}.gpkg", driver="GPKG")
        print(name, lyr, len(g), flush=True)
