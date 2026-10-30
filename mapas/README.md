# Mapas murales A0 – Intendencia de Aduana de Tarapoto

Tres mapas en formato A0 vertical (841 × 1189 mm), con un PDF vectorial para plotter y un PNG de 300 dpi por mapa. En el repositorio solo van los PDF: los PNG pesan entre 110 y 140 MB, pasan el límite de 100 MB de GitHub y se entregan aparte.

| Mapa | Archivo | Escala | Contenido |
|---|---|---|---|
| 1 | `Mapa1_Circunscripcion_IA_Tarapoto` | 1:850 000 | Circunscripción de la IA Tarapoto con límites de departamentos, provincias y distritos (con el nombre de cada distrito), ZTE/ZTC, circunscripciones vecinas, red vial con códigos, ríos navegables, puertos, aeródromos, capitales, frontera, sede de la IA y relieve |
| 2 | `Mapa2_Corredores_ZTE_ZTC` | 1:1 000 000 | Corredores Oeste, Suroeste, Sur y Fluvial, con km totales, km en ZTE, punto exacto de salida de la ZTE (con zoom), peajes, controles, grifos y comisarías en ruta |
| 3 | `Mapa3_Frontera_Norte_Red_Fluvial` | 1:550 000 | Frontera norte y red fluvial de Condorcanqui al Datem del Marañón: ríos, puertos, poblados ribereños, cruces viales y fluviales de frontera, y zooms de los puertos |

## Resultados de los corredores (OSRM sobre OpenStreetMap, 30.10.2026)

| Corredor | Km total | Km en ZTE | Salida definitiva de la ZTE |
|---|---|---|---|
| Oeste: Corral Quemado → Puente Boliche → Chiclayo | 295,9 (Puente Boliche: km 194,7) | 102,5 | km 130,2, en el límite San Felipe (Jaén, ZTE) / Huarmaca (Huancabamba, Piura, ZTC): 5,78071° S, 79,39372° W |
| Suroeste: Chachapoyas → Balsas → Celendín → Cajamarca | 323,7 | 171,6 | km 171,6, en el puente Balsas sobre el río Marañón (Amazonas / Celendín): 6,84947° S, 78,02940° W |
| Sur: Tocache → Tingo María → Huánuco → Ambo → Cerro de Pasco | 396,2 | 330,4 | km 330,4, en el límite Ambo (ZTE) / San Rafael (ZTC): 10,21960° S, 76,15546° W |
| Fluvial: Iquitos → Yurimaguas | 703,2 | 703,2 | No sale de la ZTE |

En el corredor Oeste, entre los km 34,4 y 58,3 la vía pasa por el distrito de Choros (Cutervo, ZTC) según los límites referenciales del INEI.

## Decisiones y notas
- La provincia de Cutervo se representa como **ZTC**, por decisión del usuario. La Ley N.° 32582 (15.04.2026) la incluye en la ZTE, excepto el distrito de Cutervo, pero no se ubicó su reglamento.
- La ZTE sigue el art. 3 de la Ley N.° 27037 y sus modificatorias. Además de lo verificado, se marcan como ZTE Ucayali y Madre de Dios (departamentos completos), y Oxapampa, Chanchamayo y Satipo (provincias), que figuran en el mismo art. 3.
- Los límites distritales son referenciales (INEI 2019, repositorio `calderonsamuel/perumapas`).
- Solo se usan puntos operativos de fuentes públicas (OpenStreetMap).
- La clasificación vial es referencial, a partir de los códigos OSM (PE- = nacional; XX-1nn = departamental). La clasificación oficial es la del SINAC – MTC.

## Regenerar
Requiere geopandas, rasterio, rdata, networkx, matplotlib y osmium-tool. Ejecutar los scripts de `scripts/` en orden (01 a 08b) y después `mapa1.py`, `mapa2.py` y `mapa3.py`. Las rutas de datos están en `/home/user/data_base` y `/home/user/data_osm`.
