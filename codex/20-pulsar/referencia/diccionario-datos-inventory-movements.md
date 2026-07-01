---
id: null
type: reference
project: pulsar
parent: "[[moc-pulsar]]"
status: Vigente
alcance: "Tabla inventory.movements del lakehouse"
created: 2026-06-30
updated: 2026-06-30
relacionado: []
tags: [datos, sap]
---

# Diccionario de datos — `inventory.movements`

↑ Pertenece a: [Pulsar](../moc-pulsar.md)

| | |
| --- | --- |
| **Tipo** | Referencia (no normativo) |
| **Alcance** | Tabla `inventory.movements` del lakehouse |
| **Origen** | SAP Business One — tabla `OINM` (Whse Journal) |

> **Qué es.** `inventory.movements` es el diario inmutable de movimientos de
> inventario: una fila por línea de asiento de `OINM`. El stock a cualquier fecha
> es la suma corrida de estos movimientos (validado contra `OITW`, ver
> `model/movements/validate.py`). La tabla está particionada por `retail_year`
> (año retail de `doc_date`). La procedencia de cada columna vive en
> `sources/oinm.py` (`MOVEMENT_COLUMNS` / `build_oinm_query`); este documento la
> resume para futuros programadores.

## Columnas

| Columna | Tipo | Origen (`OINM`) | Significado |
| --- | --- | --- | --- |
| `mov_id` | `UBIGINT` | — (derivada) | Hash determinista de la clave natural (`company`, `trans_type`, `base_entry`, `doc_line`, `item_code`, `warehouse`). Conveniencia de auditoría; la idempotencia de cargas **no** depende de él. |
| `company` | `VARCHAR` | — (derivada) | Compañía de origen: `COMERCIAL`, `HR` o `CAP`. |
| `item_code` | `VARCHAR` | `ItemCode` | Código de artículo. |
| `warehouse` | `VARCHAR` | `Warehouse` | Código de almacén. |
| `doc_date` | `DATE` | `DocDate` | Fecha **de negocio** (efectiva) del movimiento. Base del particionado retail. |
| `doc_time` | `SMALLINT` | `DocTime` | Hora intradía como `HHMM` (p. ej. `2340` → 23:40). |
| `doc_ts` | `TIMESTAMP` | — (derivada) | `doc_date` + `doc_time` combinados (timestamp efectivo). |
| `create_date` | `DATE` | `CreateDate` | Fecha de **captura** en SAP. Watermark incremental (capta documentos back-dated). |
| `trans_type` | `BIGINT` | `TransType` | Tipo de documento origen (`ObjType` de SAP B1). Ver tabla abajo. |
| `base_entry` | `BIGINT` | `CreatedBy` | `DocEntry` (clave interna única) del documento origen. *En `OINM`, `CreatedBy` guarda el `DocEntry`, no un usuario.* |
| `base_num` | `BIGINT` | `BASE_REF` | `DocNum` (número visible/impreso) del documento origen. |
| `doc_line` | `BIGINT` | `DocLineNum` | Número de línea dentro del documento origen. |
| `in_qty` | `DOUBLE` | `InQty` | Cantidad que **entra** al almacén (≥ 0). |
| `out_qty` | `DOUBLE` | `OutQty` | Cantidad que **sale** del almacén (≥ 0). |
| `trans_value` | `DOUBLE` | `TransValue` | Valor monetario (a **costo**) del inventario movido. Signo: ver abajo. |
| `retail_year` | `SMALLINT` | — (derivada) | Año retail de `doc_date` (clave de partición). |

La terna **`(trans_type, base_entry, doc_line)`** apunta a la línea exacta del
documento origen en SAP; **`base_num`** es el número legible para buscarlo a mano.

## `trans_type` — tipo de documento origen (SAP B1 `ObjType`)

Códigos presentes en el histórico completo (carga a 2026-06). Verificados
cruzando el `ObjType` estándar de SAP B1 con la dirección real del movimiento
observada en los datos:

| Código | Documento origen | Dirección típica |
| --- | --- | --- |
| `13` | Factura de cliente (A/R Invoice) | salida |
| `14` | Nota de crédito de cliente (A/R Credit Memo) | entrada |
| `15` | Entrega a cliente (Delivery) | salida |
| `16` | Devolución de cliente (Return) | entrada |
| `18` | Factura de proveedor (A/P Invoice) | mayormente solo-valor |
| `19` | Nota de crédito de proveedor (A/P Credit Memo) | salida |
| `20` | Entrada por OC (Goods Receipt PO) | entrada |
| `21` | Devolución a proveedor (Goods Return) | salida |
| `59` | Entrada de inventario (Goods Receipt) | entrada |
| `60` | Salida de inventario (Goods Issue) | salida |
| `67` | Transferencia de inventario (Inventory Transfer) | neta 0 (sale de un almacén, entra en otro) |
| `69` | Costos de importación (Landed Costs) | solo-valor |
| `162` | Revaluación de inventario (Inventory Revaluation) | solo-valor |
| `10000071` | Conteo de inventario (Inventory Counting) — **confirmar** | mixto |

> **⚠️ `10000071`** es el único sin confirmar: el rango `10000000+` corresponde a
> objetos no estándar de SAP B1. Lo más probable es Conteo de inventario, pero
> conviene validarlo contra la instalación antes de tratarlo como verdad.

## `trans_value` — convención de signo

`trans_value` es el cambio en el **valor del inventario** en moneda local, a
**costo** (según el método de valuación del artículo: promedio móvil / FIFO /
estándar). No es cantidad (`in_qty`/`out_qty`) ni precio de venta. El signo sigue
la **dirección del stock** (verificado sobre las ~35.8M filas del histórico):

- **`> 0`** → entra valor al inventario (movimientos de entrada: `20`, `59`, `16`, `14`…).
- **`< 0`** → sale valor del inventario (movimientos de salida: `15`, `60`, `13`, `21`…).
- **`= 0`** → sin impacto de valor (cantidad cero, artículo de costo cero, o ajustes que se netean).

Es **costo, no margen**: una entrega/venta (`15`) registra `trans_value` negativo
= el costo de lo que salió, no el ingreso de la venta. Las transferencias (`67`)
netean ~0 a nivel documento (el valor sale de un almacén y entra en otro).

## TODO — enum de `trans_type`

Hoy `trans_type` se usa como entero crudo. Cuando aparezca el primer **consumidor**
que clasifique movimientos por tipo de documento (analítica, reportes), promover
esta tabla a un `TransType(IntEnum)` en código (probablemente en `sources/oinm.py`
o bajo `model/movements/`) para sustituir números mágicos por nombres. Mientras no
haya consumidor se mantiene como referencia documental, para evitar código muerto
(YAGNI y principio de coherencia, `PULSAR-STD-001`).
