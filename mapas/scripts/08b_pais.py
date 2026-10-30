# Marca vías, lugares y puntos dentro/fuera del Perú (columna "pe")
import geopandas as gpd, warnings
warnings.filterwarnings("ignore")
U = "/home/user/data_base/utm"
peru = gpd.read_file(f"{U}/peru.gpkg")[["geometry"]]
for n in ["vias", "lugares", "puntos"]:
    g = gpd.read_file(f"{U}/{n}.gpkg")
    rp = g.copy(); rp["geometry"] = g.geometry.representative_point()
    j = gpd.sjoin(rp, peru, predicate="within", how="left")
    g["pe"] = ~j.index_right.isna().groupby(level=0).first() if False else j.groupby(level=0).index_right.first().notna()
    g.to_file(f"{U}/{n}.gpkg", driver="GPKG"); print(n, g.pe.value_counts().to_dict())
