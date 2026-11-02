# Mapas murales A0 – Intendencia de Aduana de Tarapoto

Tres mapas en formato A0 vertical (841 × 1189 mm), con un PDF vectorial para plotter y un PNG de 300 dpi por mapa.

**Página web (GitHub Pages):** https://ia-tarapotodev.github.io/TARAPOTO-Dev/ (visor con zoom y descarga del PDF y del PNG; se publica desde la rama `gh-pages`, con teselas generadas por `scripts/09_dzi.py`).

**Ver en GitHub (mapa 1):** [vista rápida](png/Mapa1_Circunscripcion_IA_Tarapoto_vista.png) (100 dpi, para el celular) · [PNG 300 dpi](png/Mapa1_Circunscripcion_IA_Tarapoto_300dpi.png) · [PDF para plotter](Mapa1_Circunscripcion_IA_Tarapoto.pdf)

El mapa 1 tiene la distribución de mural nueva: el mapa ocupa todo el recuadro, con el título arriba a la izquierda, la ubicación arriba a la derecha, la leyenda abajo a la izquierda, y el zoom de Tarapoto con la tabla de provincias abajo a la derecha. Los mapas 2 y 3 siguen en su versión anterior y se rehacen con la misma distribución cuando se apruebe el mapa 1. El PNG de 300 dpi se obtiene rasterizando el PDF (`pdftoppm -r 300`), así ambos son idénticos.

| Mapa | Archivo | Escala | Contenido |
|---|---|---|---|
| 1 | `Mapa1_Circunscripcion_IA_Tarapoto` | 1:625 000 | Circunscripción de la IA Tarapoto con límites de departamentos, provincias y distritos (los 173 distritos rotulados), ZTE/ZTC, circunscripciones vecinas, red vial con códigos, ríos navegables, puertos, aeródromos, capitales, frontera, sede de la IA, relieve (MDE ~38 m), zoom de Tarapoto (1:40 000) y tabla de provincias |
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
Requiere geopandas, rasterio, rdata, networkx, matplotlib y osmium-tool. Ejecutar los scripts de `scripts/` en orden (01 a 08b) y después `mapa1.py`, `mapa2.py` y `mapa3.py`. El mapa 1 usa un MDE de mayor resolución (`02_dem.py 12 -79.40 -74.68 -8.98 -2.32 dem_m1_z12.tif`); se genera con `mapa1.py <salida> 300 pdf` y el PNG con `pdftoppm -r 300 -png -singlefile <salida>.pdf <salida>`. Las rutas de datos están en `/home/user/data_base` y `/home/user/data_osm`.
