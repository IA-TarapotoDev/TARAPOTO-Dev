# Tablero de gestión de riesgo

Página para el Equipo de Gestión de Riesgo de la Intendencia de Aduana de Tarapoto. Cruza las importaciones de un operador (DAM, régimen 10) con sus ventas (CPE emitidos y su detalle). Muestra indicadores, gráficos, tablas con búsqueda y exportación a CSV, y una lista consolidada de alertas.

**Página publicada:** https://ia-tarapotodev.github.io/TARAPOTO-Dev/riesgo/ (requiere clave de acceso).

## Protección de los datos

Los datos de origen tienen reserva tributaria (art. 85 del Código Tributario) y **no se versionan en este repositorio**. La página publicada lleva los datos comprimidos y cifrados con AES-256-GCM. La llave se deriva de la clave de acceso con PBKDF2-SHA256 (600 000 iteraciones). Sin la clave, el archivo publicado no revela el contribuyente, sus clientes ni los montos. El descifrado se hace en el navegador y la clave no se envía a ningún servidor. La clave se entrega al equipo por un canal interno; no la publique en el repositorio ni en issues.

## Contenido

| Pestaña | Qué muestra |
|---|---|
| Resumen | Indicadores clave, hallazgos para priorizar (enlazados a las alertas) y notas metodológicas |
| Importaciones | CIF mensual (maquinaria y otros), canal de control, tratamiento tributario (código liberatorio, TPI), aduana de despacho, principales subpartidas, descripciones sin número de parte, números de parte en varias subpartidas, valores unitarios atípicos y lista de DAM |
| Maquinaria | Unidades importadas y vendidas por mes, balance por tipo de máquina, precio de venta frente al CIF, registro de máquinas importadas (PIN, serie, motor, año, usada o nueva) y ventas de maquinaria con observaciones |
| Ventas | Ventas mensuales en USD y S/, por línea de negocio, por tipo de cliente, notas de crédito por motivo, comprobantes dados de baja y lista de clientes para cruzar con el padrón RUC |
| Alertas | Indicios por nivel (alta, media y baja), con filtros y descarga en CSV |

## Regenerar la página

```bash
# 1. Datos → JSON (fuera del repositorio)
python3 -I riesgo/scripts/generar_datos.py DAMs.csv CPEs_EMITIDOS.txt CPE_DETALLE_EMITIDO.txt /ruta/privada/datos.json

# 2. JSON → página cifrada (la clave se lee de un archivo privado, no del repositorio)
CLAVE_TABLERO_ARCHIVO=/ruta/privada/clave.txt \
  python3 -I riesgo/scripts/cifrar.py /ruta/privada/datos.json riesgo/plantilla.html /ruta/privada/index.html

# 3. Publicar: copiar index.html a riesgo/index.html en la rama gh-pages
```

### Domicilio fiscal de los clientes (opcional)

Con el padrón reducido del RUC (público: https://www2.sunat.gob.pe/padron_reducido_ruc.zip) cada cliente se ubica por el ubigeo de su domicilio fiscal dentro o fuera de la ZTE (art. 3 de la Ley 27037, con las mismas reglas de `mapas/scripts/05_tematicos.py`):

```bash
# Extrae solo los RUC de los clientes (acepta el ZIP, el TXT o un CSV propio con RUC y UBIGEO)
python3 -I riesgo/scripts/extraer_domicilios.py padron_reducido_ruc.zip CPEs_EMITIDOS.txt /ruta/privada/domicilios.csv

# Genera el JSON con la zona de cada cliente
python3 -I riesgo/scripts/generar_datos.py DAMs.csv CPEs_EMITIDOS.txt CPE_DETALLE_EMITIDO.txt /ruta/privada/datos.json \
  --domicilios /ruta/privada/domicilios.csv
```

Para la actividad económica (CIIU) y la fecha de inscripción, agregue los resultados de la **consulta múltiple de RUC** de SUNAT (ZIP o TXT, hasta 100 RUC por consulta) con `--consulta-ruc resultado1.zip resultado2.zip …`. La consulta pública no muestra el domicilio de las personas naturales.

**Trazabilidad por número de serie:** con `--trazabilidad casos.csv` (columnas `cpe, serie_maquina, serie_motor, modelo, ubicacion_entrega, direccion_entrega, fuente, nota`; `ubicacion_entrega` como «DISTRITO, PROVINCIA, DEPARTAMENTO») cada venta documentada con la factura del emisor se enlaza con su DAM por la serie de la máquina o del motor, y el tablero muestra la cadena importación → venta → destino con acciones sugeridas. El archivo de casos tiene datos de contribuyentes: no se versiona.

**XML de las facturas del emisor:** con `--facturas-xml carpeta_o_zip` se leen los comprobantes en XML (UBL 2.1). De cada ítem se extraen la serie de la máquina y del motor, el modelo, el año, el código de afectación del IGV, el establecimiento emisor, la orden de compra y la dirección del cliente; cada máquina se enlaza automáticamente con su DAM y aparece como ficha en «Trazabilidad por número de serie». Los XML no se versionan.

**Pestaña Alertas:** cada alerta lleva íconos (con IGV, zona del cliente, línea de negocio, tipo de cliente, factura revisada, enlazada con su DAM, con DAM de exportación) y un filtro «Indicador». En comprobantes con IGV, el monto mostrado es el valor de venta más el 18 % calculado.

`referencias/ubigeo_zte.csv` asigna cada distrito INEI a la ZTE o a la ZTC. Se genera con `scripts/zona_ubigeo.py` a partir de la tabla de ubigeos de [jmcastagnetto/ubigeo-peru-aumentado](https://github.com/jmcastagnetto/ubigeo-peru-aumentado) (licencia MIT). Con domicilios, el tablero agrega la zona y el domicilio fiscal en clientes y ventas de maquinaria, un resumen por zona y departamento y dos alertas más.

Formatos de entrada esperados:

- **DAM** (CSV, todas las aduanas de destino y regímenes; los totales usan el régimen 10, el depósito 70 y la exportación 40 se muestran aparte): `COD_ADUANA, ANN_PRESEN, COD_REGIMEN, NUM_DECLARACION, FEC_DECLARACION, COD_ADUDEST, NUM_DOCIDENT, NOM_RAZONSOCIAL, DIR_PARTIC, COD_TIPPARTIC, CANAL, NUM_PARTNANDI, NUM_SECSERIE, CNT_COMER, COD_UNICOMER, MTO_FOBDOL, MTO_FLETEDOL, MTO_SEGDOL, MTO_VALORADU, DES_COMER, DES_FORMAPRESEN, DES_MATECOMP, DES_USOAPLIC, DES_OTROSCARAC, COD_TIPCONVENIO, COD_CONVENIO`
- **CPE emitidos** (TXT con `|`, Latin-1, fechas MM/DD/AAAA): `ruc emisor | tipo cpe | serie | nro cpe | tipo cpe | tipo doc | doc/receptor | nombre receptor | moneda | valor venta | igv | importe total | fecha cpe | indicador estado`
- **Detalle de CPE** (TXT con `|`, Latin-1): `num_ruc | cod_cpe | num_serie_cpe | num_cpe | cod_tipo_cpe | cod_docide_recep | num_docide_recep | des_nombre_recep | fec_emision | moneda | ind_estado | ind_rechazo | cod_unidad | des_detalle_item | num_cant_item | mto_total_venta | mto_total_igv | observacion`

## Criterios de las alertas

| Nivel | Alerta | Criterio |
|---|---|---|
| Alta | Maquinaria vendida con IGV | Factura vigente de la serie de maquinaria (FP) con IGV mayor que cero |
| Alta / Baja | Maquinaria vendida a no domiciliado | Factura vigente de maquinaria a un cliente con documento de tipo 0; baja si hay una DAM de exportación (régimen 40) de maquinaria en los 90 días siguientes |
| Media | Máquina vendida a cliente de otra circunscripción amazónica | Venta de maquinaria a un cliente domiciliado en la ZTE, pero en una circunscripción aduanera distinta de la del establecimiento emisor (inferido por la serie) |
| Media | Venta de maquinaria anulada o devuelta | Nota de crédito de maquinaria con motivo 01 (anulación) o 06 (devolución total) |
| Media | Factura de maquinaria dada de baja | Factura de maquinaria en estado 2 |
| Media | Maquinaria usada importada | Serie de maquinaria con «USED» en la descripción o con un año de fabricación al menos 2 años anterior al de la DAM |
| Media | Cliente con 3 o más máquinas | Cliente con tres o más facturas vigentes de maquinaria |
| Media | Mismo número de parte en varias subpartidas | Misma descripción con número de parte declarada en más de una subpartida |
| Media | Valor unitario atípico | FOB unitario a 50 % o más de la mediana del mismo número de parte (con al menos 3 series en 2 DAM) |
| Alta | Maquinaria vendida a cliente domiciliado fuera de la ZTE | Factura vigente de maquinaria a un cliente cuyo domicilio fiscal (padrón RUC) está en la ZTC |
| Alta / Media | Factura con IGV dada de baja y reemitida sin IGV | Factura con IGV dada de baja y, en los 30 días siguientes, otra factura vigente sin IGV al mismo cliente, en la misma moneda y por el mismo valor (alta si es de maquinaria; fuera de maquinaria, solo si el IGV de la factura dada de baja es de 100 o más) |
| Media | Comprador de maquinaria con RUC reciente | La primera compra de maquinaria ocurre dentro de los 180 días siguientes a la inscripción del RUC |
| Media | Comprador de maquinaria no habido o con RUC no activo | Cliente con facturas de maquinaria cuyo RUC no está activo o cuyo domicilio figura como no habido |
| Baja | Ventas a no domiciliado | Repuestos, servicios u otros ingresos facturados a clientes con documento de tipo 0 |
| Baja | Repuestos o servicios con IGV | Factura vigente de repuestos o servicio técnico con IGV |

Las alertas son indicios para el análisis de riesgo y no constituyen conclusiones. El domicilio fiscal es el vigente en la fecha del padrón: puede diferir del que tenía el cliente al comprar y del lugar donde opera la máquina.
