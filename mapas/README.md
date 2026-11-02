# Mapas murales A0 – Intendencia de Aduana de Tarapoto

Tres mapas en formato A0 vertical (841 × 1189 mm), cada uno con un PDF vectorial para plotter. Los tres usan la misma distribución mural: el mapa ocupa todo el recuadro y los recuadros (título, ubicación, leyenda, zooms y tablas) van encima, sobre las zonas que no son relevantes. El relieve se muestra solo en el área relevante de cada mapa y el resto queda con fondo blanco.

**Página web (GitHub Pages):** https://ia-tarapotodev.github.io/TARAPOTO-Dev/ (pestañas para los 3 mapas, visor con zoom y descarga de cada PDF; se publica desde la rama `gh-pages`, con teselas generadas por `scripts/09_dzi.py`).

Vistas livianas (100 dpi) en `png/`: [mapa 1](png/Mapa1_Circunscripcion_IA_Tarapoto_vista.png) · [mapa 2](png/Mapa2_Corredores_ZTE_ZTC_vista.png) · [mapa 3](png/Mapa3_Frontera_Norte_Red_Fluvial_vista.png)

| Mapa | Archivo | Escala | Relieve en | Contenido |
|---|---|---|---|---|
| 1 | `Mapa1_Circunscripcion_IA_Tarapoto` | 1:625 000 | Circunscripción IA Tarapoto | Límites de departamentos, provincias y distritos; ZTE; circunscripciones vecinas; red vial con códigos; ríos navegables; puertos; aeródromos; las 173 capitales distritales en su ubicación oficial (INEI) y los centros poblados de más de 2 000 habitantes; frontera; sede de la IA; zoom de Tarapoto (1:40 000) y tabla de provincias. El nombre de un distrito solo se rotula cuando es distinto al de su capital. |
| 2 | `Mapa2_Corredores_ZTE_ZTC` | 1:1 000 000 | ZTE (la ZTC va en blanco) | Corredores Oeste, Suroeste, Sur y Fluvial, con kilometraje, salida definitiva de la ZTE, y peajes, controles, grifos y comisarías en ruta |
| 3 | `Mapa3_Frontera_Norte_Red_Fluvial` | 1:550 000 | Condorcanqui, Datem del Marañón y Alto Amazonas | Frontera con Ecuador; ríos Santiago, Cenepa, Morona, Pastaza, Marañón y Huallaga; puertos y embarcaderos; poblados ribereños; cruces viales y fluviales de frontera |

## Resultados de los corredores (OSRM sobre OpenStreetMap, 30.10.2026)

| Corredor | Km total | Km en ZTE | Salida definitiva de la ZTE |
|---|---|---|---|
| Oeste: Corral Quemado → Puente Boliche → Chiclayo | 295,9 (Puente Boliche: km 194,7) | 102,5 | km 130,2, en el límite San Felipe (Jaén, ZTE) / Huarmaca (Huancabamba, Piura, ZTC): 5,78071° S, 79,39372° W |
| Suroeste: Chachapoyas → Balsas → Celendín → Cajamarca | 323,7 | 171,6 | km 171,6, en el puente Balsas sobre el río Marañón (Amazonas / Celendín): 6,84947° S, 78,02940° W |
| Sur: Tocache → Tingo María → Huánuco → Ambo → Cerro de Pasco | 396,2 | 330,4 | km 330,4, en el límite Ambo (ZTE) / San Rafael (ZTC): 10,21960° S, 76,15546° W |
| Fluvial: Iquitos → Yurimaguas | 703,2 | 703,2 | No sale de la ZTE |

En el corredor Oeste, entre los km 34,4 y 58,3, la vía pasa por los distritos de Callayuc, Choros, Santa Cruz y Pimpingos (provincia de Cutervo, ZTC) según los límites referenciales del INEI.

## Decisiones y notas
- La provincia de Cutervo se representa como **ZTC**, por decisión del usuario. La Ley N.° 32582 (15.04.2026) la incluye en la ZTE, excepto el distrito de Cutervo, pero no se ubicó su reglamento.
- La ZTE sigue el anexo de SUNAT «Jurisdicción en la Ley de Promoción de la Amazonía – Ley N.° 27037, art. 3°» (procedimiento RECA-PE.05.01): Loreto, Madre de Dios, Amazonas, San Martín y Ucayali; Jaén y San Ignacio (Cajamarca); las provincias y distritos de Huánuco; Chanchamayo y Satipo (Junín); Oxapampa (Pasco); La Convención, Yanatile, Kosñipata, Camanti y Marcapata (Cusco); Sivia, Ayahuanco, Ayna, San Miguel y Santa Rosa (Ayacucho); Huachocolpa y Tintay Puncu (Huancavelica); distritos de Carabaya y Sandia (Puno); Ongón (La Libertad) y El Carmen de la Frontera (Piura). Los distritos creados después por división de los listados no se agregaron.
- Los límites distritales son referenciales (INEI 2019, repositorio `calderonsamuel/perumapas`). Las capitales distritales usan las coordenadas del INEI (repositorio `jmcastagnetto/ubigeo-peru-aumentado`).
- Solo se usan puntos operativos de fuentes públicas (OpenStreetMap).
- La clasificación vial es referencial, a partir de los códigos OSM (PE- = nacional; XX-1nn = departamental). La clasificación oficial es la del SINAC – MTC.

## Regenerar
Requiere geopandas, rasterio, rdata, networkx, scipy, matplotlib, osmium-tool y poppler (`pdftoppm`). Ejecutar los scripts de `scripts/` en orden: 01 a 04, 05, 06 a 08b, `05c_utm.py`, `05b_limpiar.py` y `10_capitales.py`. Este último usa `ubigeo_distrito.csv` de jmcastagnetto/ubigeo-peru-aumentado. Después ejecutar `mapa1.py`, `mapa2.py` y `mapa3.py`; los tres usan `mural.py` y `carto.py`.

Cada mapa se genera con `mapaN.py <salida> 300 pdf`, y su PNG de 300 dpi con `pdftoppm -r 300 -png -singlefile <salida>.pdf <salida>`.

Los modelos de elevación se descargan con `02_dem.py`:
- Mapa 1 y mapa 3: `dem_m1_z12.tif`.
- Mapa 2: `dem_m2_z11.tif`.

Las rutas de datos están en `/home/user/data_base` y `/home/user/data_osm`.
