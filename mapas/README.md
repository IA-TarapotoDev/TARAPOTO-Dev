# Mapas murales A0 – Intendencia de Aduana de Tarapoto

Tres mapas en formato A0, cada uno con un PDF vectorial para plotter: los mapas 1 y 2 en vertical (841 × 1189 mm) y el mapa 3 en horizontal (1189 × 841 mm). Los tres usan la misma distribución mural: el mapa ocupa todo el recuadro y los recuadros (título, ubicación y leyenda) van encima, sobre zonas que no son relevantes. El relieve se muestra solo en el área relevante de cada mapa y el resto queda con fondo blanco.

**Página web (GitHub Pages):** https://ia-tarapotodev.github.io/TARAPOTO-Dev/ (pestañas para los 3 mapas, visor con zoom y descarga de cada PDF; se publica desde la rama `gh-pages`, con teselas generadas por `scripts/09_dzi.py`).

Vistas livianas (100 dpi) en `png/`: [mapa 1](png/Mapa1_Circunscripcion_IA_Tarapoto_vista.png) · [mapa 2](png/Mapa2_Corredores_ZTE_ZTC_vista.png) · [mapa 3](png/Mapa3_Red_Fluvial_Norte_Peru_vista.png)

| Mapa | Archivo | Escala | Relieve en | Contenido |
|---|---|---|---|---|
| 1 | `Mapa1_Circunscripcion_IA_Tarapoto` | 1:625 000 | Circunscripción IA Tarapoto | Límites de departamentos, provincias y distritos; ZTE; circunscripciones vecinas; red vial con códigos; ríos navegables; puertos; aeródromos; las 173 capitales distritales en su ubicación oficial (INEI) y los centros poblados de más de 2 000 habitantes; frontera; sede de la IA; zoom de Tarapoto (1:40 000) y tabla de provincias. El nombre de un distrito solo se rotula cuando es distinto al de su capital. |
| 2 | `Mapa2_Corredores_ZTE_ZTC` | 1:1 000 000 | ZTE (la ZTC va en blanco) | Corredores Oeste, Suroeste, Sur y Fluvial, con kilometraje, salida definitiva de la ZTE, y peajes, controles, grifos y comisarías en ruta |
| 3 | `Mapa3_Red_Fluvial_Norte_Peru` (A0 horizontal) | 1:1 250 000 | Circunscripción IA Tarapoto | Red fluvial del norte del Perú (de la frontera con Ecuador y Colombia hasta ~9° S, de la costa de Tumbes a Santa Rosa): Hidrovía Amazónica, ríos navegables, puertos fluviales, capitales ribereñas y oficinas SUNAT junto a ríos navegables; salida fluvial de la jurisdicción y las 10 salidas del país del norte; rutas de salida desde los puertos de la IA Tarapoto con kilometraje desde Yurimaguas |

## Salidas fluviales (mapa 3)

Kilometraje medido sobre el eje de los ríos de OpenStreetMap (longitud geodésica, WGS 84), con la ruta más corta por la red navegable.

**Salida de la jurisdicción de la IA Tarapoto**

| Río | Coordenadas | Distancia por río |
|---|---|---|
| Río Marañón → IA Iquitos | 4,9428° S, 75,5149° W | km 236 desde Yurimaguas · km 292 desde Saramiriza |

**Salidas del país (norte del Perú)**

| Río | Hacia | En la IA Tarapoto | Coordenadas | Distancia por río |
|---|---|---|---|---|
| Río Pastaza | Ecuador | Sí | 2,5916° S, 76,6375° W | 381 km desde San Lorenzo |
| Río Huasaga | Ecuador | Sí | 2,7223° S, 77,0252° W | – |
| Río Morona | Ecuador | Sí | 2,9537° S, 77,7128° W | 496 km desde Saramiriza |
| Río Santiago | Ecuador | Sí | 3,0009° S, 77,8433° W | 244 km desde Santa María de Nieva |
| Río Napo | Ecuador | No | 0,9275° S, 75,3840° W | – |
| Río Curaray | Ecuador | No | 1,5895° S, 75,6171° W | – |
| Río Tigre | Ecuador | No | 2,1264° S, 76,0429° W | – |
| Río Putumayo (fronterizo) | Colombia | No | 2,6514° S, 70,0828° W | – |
| Río Amazonas | Colombia (Leticia) y Brasil (Tabatinga) | No | 4,1854° S, 69,9795° W | 1 185 km desde Yurimaguas · 1 241 km desde Saramiriza |
| Río Yavarí (fronterizo) | Brasil | No | 4,2842° S, 70,1298° W | – |

En los ríos fronterizos (Putumayo y Yavarí), el río es el propio límite internacional y el cruce puede hacerse en cualquier punto de su curso; el punto marcado es el extremo aguas abajo del tramo limítrofe.

## Resultados de los corredores (mapa 2; OSRM sobre OpenStreetMap, 30.10.2026)

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
- Navegabilidad: la Hidrovía Amazónica comprende el Amazonas, el Ucayali, el Marañón desde Saramiriza y el Huallaga desde Yurimaguas. Los demás ríos navegables se identifican por nombre y solo en sus tramos de selva baja: los tramos a más de 650 m s. n. m. (cañones y valles andinos) se clasifican como ríos no navegables (`scripts/14_navegabilidad.py`).
- Circunscripciones: R.S. N.° 000980 y modificatorias. La Intendencia de Aduana de Chancay comprende las provincias de Pasco, Daniel Alcides Carrión, Cajatambo, Huaral, Oyón, Barranca y Huaura, y el distrito de Ancón (provincia de Lima).
- Los límites distritales son referenciales (INEI 2019, repositorio `calderonsamuel/perumapas`). Las capitales distritales usan las coordenadas del INEI (repositorio `jmcastagnetto/ubigeo-peru-aumentado`).
- Solo se usan puntos operativos de fuentes públicas (OpenStreetMap).
- La clasificación vial es referencial, a partir de los códigos OSM (PE- = nacional; XX-1nn = departamental). La clasificación oficial es la del SINAC – MTC.

## Regenerar
Requiere geopandas, rasterio, rdata, networkx, scipy, matplotlib, osmium-tool y poppler (`pdftoppm`).

1. Ejecutar los scripts de `scripts/` en orden: 01 a 04, 05, 06 a 08b, `05c_utm.py`, `05b_limpiar.py` y `10_capitales.py`. Este último usa `ubigeo_distrito.csv` de jmcastagnetto/ubigeo-peru-aumentado.
2. Para el mapa 3, extraer de OpenStreetMap el Perú completo (`peru_full.osm.pbf` y sus filtros `pf_*.osm.pbf`) y ejecutar `12_fluvial_nacional.py`, `14_navegabilidad.py` y `13_rutas_fluviales.py`.
3. Ejecutar `mapa1.py`, `mapa2.py` y `mapa3.py`; los tres usan `mural.py` y `carto.py`. Cada mapa se genera con `mapaN.py <salida> 300 pdf`, y su PNG de 300 dpi con `pdftoppm -r 300 -png -singlefile <salida>.pdf <salida>`.

Los modelos de elevación se descargan con `02_dem.py`:
- Mapa 1 y mapa 3: `dem_m1_z12.tif`.
- Mapa 2: `dem_m2_z11.tif`.
- Navegabilidad (todo el Perú): `dem_peru_z8.tif`.

Las rutas de datos están en `/home/user/data_base` y `/home/user/data_osm`.
