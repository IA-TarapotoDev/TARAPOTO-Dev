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

Formatos de entrada esperados:

- **DAM** (CSV): `COD_ADUANA, ANN_PRESEN, COD_REGIMEN, NUM_DECLARACION, FEC_DECLARACION, COD_ADUDEST, NUM_DOCIDENT, NOM_RAZONSOCIAL, DIR_PARTIC, COD_TIPPARTIC, CANAL, NUM_PARTNANDI, NUM_SECSERIE, CNT_COMER, COD_UNICOMER, MTO_FOBDOL, MTO_FLETEDOL, MTO_SEGDOL, MTO_VALORADU, DES_COMER, DES_FORMAPRESEN, DES_MATECOMP, DES_USOAPLIC, DES_OTROSCARAC, COD_TIPCONVENIO, COD_CONVENIO`
- **CPE emitidos** (TXT con `|`, Latin-1, fechas MM/DD/AAAA): `ruc emisor | tipo cpe | serie | nro cpe | tipo cpe | tipo doc | doc/receptor | nombre receptor | moneda | valor venta | igv | importe total | fecha cpe | indicador estado`
- **Detalle de CPE** (TXT con `|`, Latin-1): `num_ruc | cod_cpe | num_serie_cpe | num_cpe | cod_tipo_cpe | cod_docide_recep | num_docide_recep | des_nombre_recep | fec_emision | moneda | ind_estado | ind_rechazo | cod_unidad | des_detalle_item | num_cant_item | mto_total_venta | mto_total_igv | observacion`

## Criterios de las alertas

| Nivel | Alerta | Criterio |
|---|---|---|
| Alta | Maquinaria vendida con IGV | Factura vigente de la serie de maquinaria (FP) con IGV mayor que cero |
| Alta | Maquinaria vendida a no domiciliado | Factura vigente de maquinaria a un cliente con documento de tipo 0 |
| Media | Venta de maquinaria anulada o devuelta | Nota de crédito de maquinaria con motivo 01 (anulación) o 06 (devolución total) |
| Media | Factura de maquinaria dada de baja | Factura de maquinaria en estado 2 |
| Media | Maquinaria usada importada | Serie de maquinaria con «USED» en la descripción o con un año de fabricación al menos 2 años anterior al de la DAM |
| Media | Cliente con 3 o más máquinas | Cliente con tres o más facturas vigentes de maquinaria |
| Media | Mismo número de parte en varias subpartidas | Misma descripción con número de parte declarada en más de una subpartida |
| Media | Valor unitario atípico | FOB unitario a 50 % o más de la mediana del mismo número de parte (con al menos 3 series en 2 DAM) |
| Baja | Ventas a no domiciliado | Repuestos, servicios u otros ingresos facturados a clientes con documento de tipo 0 |
| Baja | Repuestos o servicios con IGV | Factura vigente de repuestos o servicio técnico con IGV |

Las alertas son indicios para el análisis de riesgo y no constituyen conclusiones. Los CPE no traen el domicilio del cliente, así que la ubicación de los compradores debe cruzarse con el padrón RUC.
