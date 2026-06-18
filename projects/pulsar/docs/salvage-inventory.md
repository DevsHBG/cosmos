# Inventario de salvamento — `hbg-analytics-service` → `pulsar`

- Fecha: 2026-06-18
- Estado: Vivo (se actualiza conforme avanza la migración)
- Repo origen: `C:\Users\carlo\hbg\hbg-analytics-service` (monolito Flask, ~112 archivos Python)
- Relacionado: [ADR-0002](adr/0002-ledger-unificado-multiempresa.md), [ADR-0003](adr/0003-estrategia-estrangulamiento.md)

## Propósito

Decidir, archivo por archivo, qué del sistema viejo se **porta** (PORT), se
**adapta** (ADAPT) o se **descarta** (DROP) al construir `pulsar`. La conclusión
estratégica: el sistema viejo es **mucho más rescatable de lo esperado** porque la
lógica analítica cara (reabasto, ABC/XYZ, calendario retail) está **bien hecha y
poco acoplada** al bug del modelo de datos. El bug está **contenido** en la query
de ventas.

> Números de línea y LOC son aproximados (lectura por extractos); verificar al
> portar cada módulo.

## El bug está contenido

El pecado de raíz —hornear estado actual (`OITW.OnHand`, precio/costo de hoy) en
renglones de venta históricos como columnas `"...ACTUAL"`— vive en **un solo
lugar**:

- `db/root_querys.py:46-96` (`build_daily_sales_query`): columnas `PRECIO DE LISTA
  ACTUAL`, `COSTO ACTUAL`, `EXISTENCIA SUCURSAL`, `EXISTENCIA CEDIS`, vía subqueries
  correlacionadas por renglón (también el origen del problema de rendimiento contra
  HANA).
- `realtime_api.py`: SQL directo a HANA sobre estado actual.

La query de movimientos de OINM (`db/root_querys.py:592-628`) **ya es correcta**
(suma `InQty - OutQty` por fecha, sin joins de estado actual), pero **incompleta**:
solo lee HR y CAP (falta COMERCIAL), agrega por día (pierde `TransType` y cliente).

## Mapa PORT / ADAPT / DROP por capa

### Fundación de datos
| Archivo (viejo) | Acción | Nota |
|---|---|---|
| `db/root_querys.py` — query OINM (`:592-628`) | ADAPT | Base correcta; extender a 3 esquemas, grano de movimiento (no diario), conservar `TransType` y link a documento. |
| `db/root_querys.py` — query ventas (`:46-96`) | DROP | El bug. Se reemplaza por facts derivados del ledger. |
| `utils/data_builder.py` | PORT | Lake Polars+DuckDB: escrituras atómicas, merge incremental, partición. Subir a capas/DuckLake. |
| `scripts/backfill_inventory_movements.py`, `check_sales_global_integrity.py` | PORT | Chunking mensual + chequeo de integridad. |
| `hana.py` | ADAPT | Conexión 3-esquemas correcta; **quitar credenciales hardcodeadas** (`:11`). |
| `db/sap_sync_queries.py`, `skus.py`, `replenishment.py`, `suppliers_products.py`, `store_price_lists.py`, `cedis.py`, `purchase_prices.py` | PORT/ADAPT | Lookups y reglas de negocio (impuestos, origen, prefijos). Recablear a ledger. |

### Clasificación
| Archivo | Acción | Nota |
|---|---|---|
| `utils/classification.py` (ABC/XYZ) | PORT | Puro, validado, polars. Define "ganadores" (A, AX/AY). |
| `controllers/internal_tools.py` (builders ABC/XYZ, infra parquet) | ADAPT | Pareto + coef. variación + ventana retail. Recablear a facts nuevos. |
| `services/abc_xyz_global_scheduler.py` | PORT | Parámetros congelados, ventana móvil 52 semanas retail. |

### Motor anti-quiebres (núcleo de v1)
| Archivo | Acción | Nota |
|---|---|---|
| `controllers/inventory_replenishment.py` | PORT | **Corazón.** Política periódica (R,S): ROP, order-up-to, demanda de red excluyendo CEDIS. |
| `controllers/min_max.py` (v2) | PORT | Safety stock `z·σ·√(LT+R)`, min/max, redondeo display-pack, regla slow-mover. |
| `controllers/retail_traffic_light.py`, `petca_traffic_light.py` | PORT/unificar | Definición de quiebre, semáforos, demanda hub-vs-tienda. |
| `controllers/inventory_ops_dashboard.py` | ADAPT | Flags de quiebre/dead-stock/overstock, días de cobertura. Derivar del ledger diario, no del snapshot. |
| `controllers/distribution.py`, `services/distribution.py` | ADAPT | Ponderación por sucursal; falta terminar la asignación de surtido. |
| `controllers/margin_regimes.py` — "días limpios" | ADAPT | 🔑 Ya excluye días de promo y **de quiebre** del baseline: media máquina de demanda censurada. Reusar para descensurar demanda. |

### Presentación
| Archivo | Acción |
|---|---|
| `utils/retail_calendar.py`, `models/seasons.py` | PORT (puros, excelentes) |
| `utils/chart_renderers.py`, `report_template.py`, `pdf_engine.py` | PORT |
| `utils/replenishment_po_excel.py`, `top_skus_buyer_excel.py`, `inventory_ops_excel.py` | PORT/ADAPT |
| `anthropic_client.py` | PORT (cliente con costeo de tokens) |

### Orquestación e integración
| Archivo | Acción | Nota |
|---|---|---|
| `server.py` — registro de blueprints + scheduler | ADAPT | Conservar patrón; tirar ABC/maximizer embebidos duplicados. |
| `services/sap_syncs.py`, `supabase_sync.py`, `sap_image_sync.py`, `*_sync*.py` | ADAPT | Patrones de retry/concurrencia/backoff, diff-before-overwrite. |
| Blueprints Flask delgados (`services/sales.py`, `classification.py`, `cedis.py`, etc.) | DROP | Reconstruir (baratos, 1-2 días). |

### Fuera de alcance de v1 (DIFERIR, no borrar)
| Archivo | Nota |
|---|---|
| `controllers/margins_agent*.py`, `margin_catalog.py`, `margin_groups.py`, `margin_audit.py` | Pricing/márgenes y agente LLM. Valiosos después; el diseño del agente (tool-use, guardrails) se reusa. |
| `realtime_api.py` | Reescribir desde el ledger cuando aplique. |

## Las 3 fallas del sistema viejo (y cómo `pulsar` las cierra)

1. **Hueco de detección de quiebre** — el viejo detecta quiebres desde el fact de
   ventas, así que no ve el caso "on-hand=0 con 0 ventas" (el quiebre real). El
   ledger de OINM con saldo diario lo cierra. *Es la falla más importante.*
2. **Ledger incompleto** — solo HR y CAP, sin COMERCIAL, agregado por día. El
   diseño de 3 esquemas + grano de movimiento + clasificación por canal lo cierra.
3. **Lead time hardcodeado por origen** — **decisión deliberada, no falla.** Los
   datos de OC en SAP son mentirosos: muchas compras se hacían fuera de SAP y la OC
   se creaba al llegar la mercancía a CEDIS (recepción el mismo día → lead time 0,
   sesgado). El promedio curado por origen funciona para cadena de suministro. En
   `pulsar` el lead time es un **parámetro curado** (`dim_lead_time`), mantenido por
   el equipo, **no derivado** del dato sucio. Ver [ADR-0002](adr/0002-ledger-unificado-multiempresa.md).

## Secuencia de migración (resumen)

1. Fundación: ledger OINM 3-esquemas → `fact_inventario_diario` + `fact_demanda_diaria` + dimensiones curadas. *Cierra huecos 1 y 2.*
2. Clasificación: portar ABC/XYZ sobre los facts nuevos.
3. Motor anti-quiebres: portar reabasto + min/max + semáforos, recableados al ledger. *Objetivo v1.*
4. Presentación + orquestación: charts/Excel/PDF + scheduler diario.
5. Después: censado formal de demanda, márgenes, agente LLM.

Detalle de la estrategia en [ADR-0003](adr/0003-estrategia-estrangulamiento.md).
