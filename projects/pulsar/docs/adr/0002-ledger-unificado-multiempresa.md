# ADR-0002: Ledger unificado multi-empresa como fundación de datos

- Estado: Aceptado
- Fecha: 2026-06-18

## Contexto

El objetivo de `pulsar` es un motor de análisis de retail que arranca por **evitar
quiebres de inventario de productos que se están vendiendo** (productos ganadores).
La fuente es SAP Business One sobre SAP HANA.

El sistema anterior (`hbg-analytics-service`) falló en la capa de datos por un error
de raíz: **horneaba el estado actual** (inventario `OITW.OnHand`, precio de lista,
último costo) **como columnas en renglones de venta históricos**. Al ejecutar la
query en 2026 obtenía valores de 2026 para ventas de 2024. La historia point-in-time
quedaba mal y solo existía data "real" desde enero 2026 (agregación progresiva
diaria hacia adelante).

Diagnóstico de esta investigación (junio 2026), validado contra el SAP real:

- **OINM** (diario de almacén) registra todo movimiento con fecha, almacén, item,
  `InQty/OutQty`, `TransType` y link al documento. El inventario en cualquier fecha
  se **reconstruye** como suma acumulada de movimientos.
- **Validación dorada:** reconstrucción desde OINM vs saldo actual `OITW` →
  diferencia **0** en SKUs antiguos. La reconstrucción es exacta.
- Operamos en **3 esquemas/empresas**: `HBG_COMERCIAL` (CEDIS / fuente de
  suministro), `HBG_THR` (tiendas marca HR), `HBG_CAPRICHOS_2` (tiendas Caprichos y
  Elilu).
- **`ItemCode` es universal**: ~99.99% de traslape de catálogo entre los 3 esquemas,
  mismo código = mismo producto. No se necesita tabla de mapeo cross-empresa.
- **La demanda real** se registra como `TransType` **15** (Entrega), no 13
  (Factura): el POS descuenta inventario en la entrega; la factura no lo re-mueve.
- **La marca** se deriva del **prefijo del almacén**: `A##`=HR, `E##`=Caprichos,
  `L##`=Elilu (Elilu vive en el esquema de Caprichos).
- **Demanda vs reabasto** en COMERCIAL se separa por grupo de cliente: `GroupCode`
  **127** (SUCURSALES) = traspaso interno; el resto = venta externa real. La
  clasificación **no se puede hacer por nombre** (Amazon/TikTok cayeron en el grupo
  100, Mercado Libre en MARKET MAX): requiere mapeo curado.
- Hay **dato sucio**: anomalía de ~47 mil millones de unidades en ajustes `59/60` de
  THR, y stock negativo probable (SAP permite vender sin existencia).
- El **reabasto se decide diario**; no se requiere realtime.

## Decisión

### 1. Ledger inmutable de movimientos como única fuente de verdad
Extraer OINM de los 3 esquemas a un **ledger append-only**. Grano = un renglón por
movimiento. Llave: `(company, warehouse, item_code, doc_date, trans_type, mov_id)`.
Columnas mínimas: `company`, `item_code`, `warehouse`, `doc_date` (fecha de negocio),
`create_date` (captura), `trans_type`, `base_entry`/`base_num` (link a documento),
`in_qty`, `out_qty`, `trans_value`.

### 2. Evento ≠ estado: el inventario y la demanda son derivados, no columnas
No se almacena el estado pegado al evento (ese fue el bug). Se derivan dos series a
partir del ledger:
- `fact_inventario_diario`: `(company, item, warehouse, fecha) → on_hand` (suma
  acumulada).
- `fact_demanda_diaria`: `(company, item, warehouse, fecha) → unidades` de venta
  real.

"¿Cuánto inventario había al momento de la venta?" es un **JOIN** por
`(item, ubicación, fecha)`, nunca una columna materializada.

### 3. `ItemCode` como llave universal
Unificación directa por `ItemCode` entre esquemas. La columna `company` es parte de
la llave porque los códigos de almacén **colisionan** entre empresas (existe `01` en
las tres).

### 4. Extracción incremental por fecha de captura, no de negocio
El watermark incremental es `create_date` (cuándo entró el renglón a OINM), no
`doc_date`. SAP recibe documentos con fecha retroactiva; jalar por `doc_date`
perdería esos movimientos. Se guarda `doc_date` como la fecha efectiva.

### 5. El significado vive en dimensiones curadas y versionadas
El ledger es crudo y neutro. La interpretación de negocio vive en tablas de mapeo
pequeñas, en git, cambiadas con revisión (no como toggles de runtime):
- `dim_canal`: `GroupCode → {reabasto | online | mayoreo | pendiente}` +
  `cuenta_como_demanda` (bool, **default FALSE**). v1: solo MARKET MAX (126) y las
  ventas de tienda cuentan como demanda; el grupo 100 y otros quedan **apagados,
  recuperables**.
- `dim_warehouse`: `prefijo → {marca, tipo (tienda|cedis), vendible, reabastecible}`.
- `dim_transtype`: `TransType → {venta | traspaso | compra | ajuste}`.
- `dim_lead_time`: `origen → días`. **Curado a mano, NO derivado de las órdenes de
  compra.** Razón: las OC en SAP son poco fiables (compras fuera de SAP, OC creada al
  recibir mercancía → lead time 0 sesgado). El promedio por origen (p. ej. NACIONAL
  15, EUA 30, CHINA 90) lo mantiene cadena de suministro.

### 6. Definición de demanda y de quiebre
- **Demanda de cliente** = `TransType` 15/13 menos devoluciones 14/16, en ubicaciones
  vendibles (tiendas por prefijo) + ventas externas de COMERCIAL (`cuenta_como_demanda`).
  Excluye traspasos (67), compras (20) y ajustes (59/60).
- **Quiebre** = `on_hand = 0` en una fecha para un SKU **activo** (con demanda en
  ventana móvil), incluyendo días sin venta (que el sistema viejo no veía).

### 7. Precio y costo históricos correctos
El precio de venta sale de la **línea del documento** (`INV1`/`DLN1`), histórico por
definición. El costo, de `OINM.trans_value`. **No** del precio de lista actual
(`ITM1`) ni de `LastPurPrc` — el error del sistema anterior.

### 8. Capa de cuarentena
Detectar y aislar outliers (anomalía de ~47 mil M, stock negativo) antes de
alimentar análisis de demanda. Se marca y se mide, no se borra silenciosamente.

### 9. Motor de consulta y formato
DuckDB como motor (seguro y excelente a esta escala: decenas a baja centena de
millones de renglones). **DuckLake** como formato lakehouse (ACID, time-travel,
evolución de esquema, concurrencia), asumiendo su madurez reciente (v1.0 abril 2026)
como riesgo consciente y **revisable**.

## Consecuencias

- El primer entregable de `pulsar` (ledger + facts de demanda/inventario) es a la vez
  la fundación del sistema nuevo y la corrección del bug central del viejo.
- El backfill histórico (desde el primer movimiento de cada SKU, ~2019, para tener
  saldo de apertura correcto) es un job pesado **de una sola vez**; de ahí, solo
  incrementos diarios.
- Toda la incongruencia del ERP (almacenes lógicos, grupos inconsistentes, marcas
  compartidas) se encapsula en las dimensiones curadas, no en el pipeline.
- Validar la reconstrucción OINM vs OITW es un test de regresión permanente.
- Cambiar cualquiera de estas decisiones requiere un nuevo ADR.
