# Copia a UTM 18S (EPSG:32718) las capas temáticas recalculadas por 05_tematicos.py
import geopandas as gpd, warnings
warnings.filterwarnings("ignore")
B = "/home/user/data_base"
for n in ["distritos_tematico", "provincias", "departamentos", "circunscripciones", "regimen", "peru"]:
    gpd.read_file(f"{B}/{n}.gpkg").to_crs(32718).to_file(f"{B}/utm/{n}.gpkg", driver="GPKG"); print(n, "ok")
