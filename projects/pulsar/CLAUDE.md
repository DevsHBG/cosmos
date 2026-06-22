# Pulsar — guía para agentes

Pipeline de extracción → lakehouse sobre SAP Business One (HANA). Layout `src/`
(el paquete es `pulsar`, ver `pyproject.toml`). Tooling: `uv`, `ruff`, `mypy`
(strict), `pytest`.

## Convención de fechas: SIEMPRE calendario retail (4-5-4)

**Toda** lógica de fechas con sentido de negocio —agrupación, clasificación,
particionado, chunking de cargas, periodos/trimestres/años— se basa en el
**calendario retail**, no en el calendario gregoriano. Nunca uses `month`/`year`
gregorianos para agrupar o clasificar datos del negocio.

- Fuente única de verdad: `pulsar.retail.calendar`. Reutiliza sus helpers
  (`from_date`, `retail_year_range`, `week_range`, `period_range`, etc.); no
  reimplementes la aritmética del calendario en otro módulo ni en SQL.
- El año retail está anclado en `ANCHOR_WEEK1_START` (2026-W1 = domingo
  2026-02-01), 52 semanas exactas (364 días), semanas domingo→sábado. El año
  retail se nombra por el año gregoriano de su primera semana.
- Excepción: `create_date` se usa **crudo** como watermark incremental (capturar
  documentos back-dated); eso es mecánica de ingesta, no clasificación de negocio.

## Lakehouse (DuckLake)

- Un solo **catálogo** (`lake/catalog.sqlite`) para todo el proyecto. Los datos
  (parquets) viven bajo `lake/data/` (gitignored).
- Los dominios se separan por **schema**; cada tabla obtiene su propia carpeta:
  `lake/data/<schema>/<tabla>/`. Hoy: **`inventory.movements`**.
- El término **`ledger` queda deprecado**. La tabla de movimientos es
  `inventory.movements` (constante `MOVEMENTS_TABLE` en
  `model/movements/schema.py`); sus columnas, `MOVEMENT_COLUMNS` en
  `sources/oinm.py`.
- `movements` está **particionada por año retail** (Hive): columna materializada
  `retail_year` (calculada en `finalize_oinm_frame` con `retail_year_expr` del
  retail calendar) sobre la que se hace `ALTER TABLE ... SET PARTITIONED BY`. En
  disco: `lake/data/inventory/movements/retail_year=2025/`. El particionado se
  fija una sola vez en `ensure_schema` (DuckLake registra un spec nuevo en cada
  `SET PARTITIONED BY`, por eso se guarda con un check de existencia).
- La carga histórica inicial (backfill) se chunkea por **año retail**
  (`_iter_retail_year_windows` en `model/movements/build.py`): cada ventana se
  alinea con una partición `retail_year`.
- Mantenimiento a largo plazo (**TODO**, bloqueado por la decisión de
  arquitectura de jobs): compactación (`ducklake_merge_adjacent_files`) y
  expiración de snapshots (`ducklake_expire_snapshots` + cleanup, política
  `expire_older_than`). Antes de implementarlo hay que definir cómo se
  estructuran los `pulsar.jobs.*` (orquestación, scheduling, y si el
  mantenimiento es un job aparte o parte de la corrida diaria).

## Validación

`model/movements/validate.py` es el test de oro permanente: la reconstrucción
(suma corrida de OINM) debe igualar el stock actual de SAP `OITW` por
(item, warehouse). 🟢 = cuadra, 🔴 = hay diferencias.
