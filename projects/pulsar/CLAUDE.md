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

## Jobs (in-house)

Toda la orquestación vive en el repo (`pulsar/jobs/`), sin schedulers de Windows
ni brokers externos. Topología elegida: **un solo proceso** (eventualmente
FastAPI con el scheduler en su `lifespan`).

- `jobs/core.py`: capa agnóstica del invocador. `Job` (ABC: `name`,
  `description`, `writes_lake`, `run(ctx)`), `JobContext`, `JobResult`, un
  registry y `run_job(job, ctx)`.
- **Serialización de escrituras**: como el catálogo DuckLake es single-writer,
  `run_job` toma un lock global de proceso (`_write_lock`) para todo job con
  `writes_lake=True`; los de solo-lectura lo saltan. Ese lock es la costura para
  pasar a API+worker en el futuro (se cambiaría por un lock de DB/archivo).
- `jobs/movements.py`: `SyncMovements` (sync incremental + validación) y
  `BackfillMovements` (backfill por año retail + validación). Cada job corre su
  golden check; un mismatch ⇒ job `failed`.
- CLI: `python -m pulsar.jobs list` y
  `python -m pulsar.jobs run <job> [--company HR|ALL] [--since] [--until]`.
- `jobs/scheduler.py`: scheduler in-process (APScheduler 3.x `BackgroundScheduler`,
  corre jobs en threads, embebible luego en el `lifespan` de FastAPI). Horarios
  declarados en código (`SCHEDULE`); cada disparo pasa por `run_job` (respeta el
  write-lock). Hoy: **`sync-movements` diario a las 00:00** (hora local del
  servidor) → captura el día anterior. Standalone: `python -m pulsar.jobs.scheduler`.
- `api/` (FastAPI): hospeda el scheduler en su `lifespan` (un solo proceso) y
  expone la **API RESTful** (estándar normativo en
  [`docs/arquitectura-restful.md`](./docs/arquitectura-restful.md) §18). Operativos
  sin versión: `GET /health` (liveness) y `GET /health/ready` (readiness). Bajo
  `/v1`: `GET /v1/jobs`, `GET /v1/jobs/{name}`, `POST /v1/jobs/{name}/runs` (trigger
  manual → `202` + header `Location` + corre en background vía el scheduler),
  `GET /v1/jobs/{name}/runs` (historial de corridas) y `GET /v1/logs` (logs). Errores
  en `application/problem+json` (RFC 9457) con `correlation_id`; colecciones paginan
  por **cursor** (`Link: rel="next"` + `next_cursor`). Arranca con
  `python -m pulsar.api`; docs interactivas en `/docs`.
- El recurso `run` es **history-only** hoy: una corrida no tiene `id` ni estado
  pollable propio (el `Location` apunta a la colección de historial). El
  `{id}` pollable (`queued→running→ok/failed`) y la `Idempotency-Key` quedan en
  `ROADMAP.md` (requieren un store de runs creado en el enqueue).
- El historial de corridas (`last_run`) está **graduado a SQLite**: `run_job`
  emite un `JobLog` y `last_run` reconstruye la última corrida desde
  `logs/logs.sqlite` (ver Logger).
- Pendiente (ver `ROADMAP.md`): el **job de mantenimiento** del lake (diferido,
  después de la observabilidad).

## Logger (observabilidad)

Servicio de logging reutilizable en `pulsar/logger/` (diseño y estado en
[`docs/observability.md`](./docs/observability.md)). Emite desde cualquier parte:

- `from pulsar.logger import log` → `log.emit(JobLog(...))`. Tipos de log = clases
  **Pydantic** (`records.py`) con `KIND` (classvar) que mapea a un sink/tabla;
  **registry + sinks pluggables** (hoy `SqliteSink`). Jerarquía: `LogRecord` →
  `ActivityLog` → `JobLog`/`ApiLog`, y `PerformanceLog` aparte. Emisión **no
  bloqueante** (cola + worker de flush) y **best-effort** (un fallo de logging
  nunca rompe al emisor).
- Captura automática: `run_job` (`JobLog`), `LoggingMiddleware` del API (`ApiLog`)
  y `PerformanceSampler` con `psutil` (`PerformanceLog` cada ~15 s). Un
  `correlation_id` (contextvar) hila request → job.
- Store: **`logs/logs.sqlite`**, operativo y **aparte** del lake (gitignored).
  Tablas `job_logs`, `api_logs` y `performance_logs`. Consulta: `log.query(...)` o
  `log.connect_duckdb()` (SQL cross-tabla). En la API se exponen como **una sola
  colección polimórfica** `GET /v1/logs?type=job|api|performance` (discriminador
  `type`; filtros `status`/`level`/`correlation_id`/`since`/`until`, `sort=-ts`,
  paginación cursor), no un endpoint por tipo.
- Config en `LoggerSettings` (`PULSAR_LOGS_*`). Lifecycle: `log.start()`/
  `shutdown()` en el `lifespan` del API (y en el scheduler/CLI standalone para que
  las corridas one-shot persistan).

## Validación

`model/movements/validate.py` es el test de oro permanente: la reconstrucción
(suma corrida de OINM) debe igualar el stock actual de SAP `OITW` por
(item, warehouse). 🟢 = cuadra, 🔴 = hay diferencias.

---

Capacidades futuras y decisiones de mayor alcance (observabilidad, auditoría,
trazabilidad, etc.): ver [`ROADMAP.md`](./ROADMAP.md) — se mantiene fuera de este
archivo para no saturar el contexto que se carga cada sesión.
