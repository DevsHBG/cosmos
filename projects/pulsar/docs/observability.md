# Servicio de logging (observabilidad) — diseño

> **Estado: fases 1–3 implementadas** (core + captura + consulta unificada). Vive
> fuera de `CLAUDE.md` a propósito (el contexto de cada sesión se mantiene lean).
> Referenciado desde `ROADMAP.md`. La fase 4 (escalado) sigue pendiente.
>
> **Nota de naming**: el paquete es **`pulsar.logger`** (no `observability`); el
> almacén operativo es **`logs/logs.sqlite`** (no `ops.sqlite`). El directorio
> `logs/` es la raíz de datos del logger (ahí vivirán los sinks de parquet/JSONL de
> la fase 4) y está gitignored, separado del lake. Los settings son
> `LoggerSettings` (`PULSAR_LOGS_*`).

## Objetivo

Un **servicio logger reutilizable en toda la app**: cualquier proceso (jobs,
endpoints, websockets, tareas internas, lo que venga) loguea con un `import`
simple y una llamada uniforme. Extensible por **tipos de log** (clases), con
**sinks** pluggables (distintos archivos/carpetas/tablas por tipo) y **consulta
unificada** por encima de todos. "Algo bien hecho", pensado para escalar.

## Principios

1. **Un solo punto de entrada**: `from pulsar.logger import log`. Emites con
   `log.emit(SomeLog(...))` desde cualquier parte.
2. **Tipos de log como clases** (igual que los `Job`: ABC + registry — patrón ya
   usado en el repo, se siente nativo). Añadir un tipo = crear una clase y
   registrarla; nada del core cambia.
3. **Sinks desacoplados**: cada tipo declara a qué sink va. Un sink sabe
   `write()` y `ensure_schema()`. Implementaciones: SQLite (consultable),
   archivos JSONL rotados (alto volumen), parquet (histórico). Distintos tipos →
   distintos archivos/carpetas.
4. **No bloqueante**: `emit()` encola; un worker en background hace flush por
   lotes. Emitir un log nunca frena el job/request.
5. **Best-effort**: un fallo de logging **nunca** rompe al que loguea (todo en
   try/except; si un sink falla, se degrada a stderr).
6. **Consulta unificada**: `log.query(...)` y un connector **DuckDB** que attachea
   todos los sinks (SQLite + parquet + JSONL) → SQL sobre todos los tipos a la vez,
   cruzables por timestamp y `correlation_id`.
7. **Correlación automática**: un `contextvar` lleva el `correlation_id` de la
   request/job en curso; cualquier log emitido dentro lo hereda solo → hila
   endpoint → job → subprocesos sin pasarlo a mano.

## Arquitectura (componentes)

```
pulsar/logger/
  __init__.py     # expone `log` (el servicio) + re-exporta los tipos de record
  records.py      # LogRecord → ActivityLog → JobLog/ApiLog; PerformanceLog
  sinks.py        # Sink (ABC) + SqliteSink  (+ futuros FileSink / ParquetSink)
  service.py      # LoggerService: registry, emit(), worker de flush, query()
  context.py      # correlation_id (contextvar) + helpers
  config.py       # LoggerSettings (rutas, intervalo de flush, retención)
  capture/
    jobs.py       # hook para run_job   → JobLog
    http.py       # LoggingMiddleware   → ApiLog
    resources.py  # PerformanceSampler  → PerformanceLog
```

### LogRecord (base)

**Pydantic `BaseModel` (frozen)** con lo común a todo log: `ts`, `level`
(info/warn/error), `correlation_id`, `source` y `KIND` (classvar por tipo). Cada
tipo concreto añade sus campos. Se eligió Pydantic sobre dataclass porque un
record es *dato* que se persiste/serializa/consulta (el análogo es
`api/schemas.py`, no `Job`): `model_dump(mode="json")` da serialización correcta
gratis y simplifica tanto el `SqliteSink` como los sinks de archivo futuros.

`ExecutionLog` (un tipo con `exec_kind` para jobs y endpoints) se dividió en dos
tipos distintos (`JobLog`, `ApiLog`) que comparten una base `ActivityLog`: cada uno
tiene sus columnas reales (sin un `meta` opaco) y su propia tabla.

```python
class LogRecord(BaseModel):          # raíz
    model_config = ConfigDict(frozen=True)
    KIND: ClassVar[str]              # cada subtipo concreto lo fija; define su sink/tabla
    ts: datetime
    level: str = "info"
    correlation_id: str | None = None
    source: str | None = None

class ActivityLog(LogRecord):        # base abstracta: algo que corrió con un resultado
    status: str = ""                 # ok | failed
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int = 0
    detail: str | None = None        # resultado libre; body completo solo si failed (con tope)

class JobLog(ActivityLog):           # una corrida de job → tabla `job_logs`
    KIND: ClassVar[str] = "job_logs"
    job: str = ""                    # nombre en el registry, p.ej. "sync-movements"
    rows: int = 0

class ApiLog(ActivityLog):           # un request HTTP → tabla `api_logs`
    KIND: ClassVar[str] = "api_logs"
    method: str = ""
    path: str = ""
    status_code: int = 0

class PerformanceLog(LogRecord):     # serie de tiempo → tabla `performance_logs`
    KIND: ClassVar[str] = "performance_logs"
    cpu_pct: float = 0.0
    rss_mb: float = 0.0
    mem_pct: float = 0.0
    disk_pct: float = 0.0
    disk_io_mb: float = 0.0
```

### Sink (ABC)

```python
class Sink(ABC):
    @abstractmethod
    def ensure_schema(self) -> None: ...
    @abstractmethod
    def write(self, records: Sequence[LogRecord]) -> None: ...   # por lotes
```

- `SqliteSink(db_path, table, record_type)` — WAL, insert batch, una tabla por
  tipo en `logs/logs.sqlite`; columnas derivadas de los campos del record. Sinks
  para `job_logs`, `api_logs` y `performance_logs`.
- `FileSink(dir)` — JSONL rotado por día: `logs/<kind>/YYYY-MM-DD.jsonl` (alto
  volumen, futuro).
- `ParquetSink(dir)` — roll-off histórico para análisis (futuro).

### LoggerService (fachada)

```python
class LoggerService:
    def register(self, record_type: type[LogRecord], sink: Sink) -> None: ...
    def emit(self, record: LogRecord) -> None:    # no bloqueante: encola
    def query(self, kind: str, *, since=None, until=None, where=None) -> list[dict]:
    def connect_duckdb(self):    # DuckDB con todos los sinks attacheados (consulta unificada)
    def start(self) -> None: ...  # arranca el worker de flush
    def shutdown(self) -> None: ...  # flush final + cierre
```

Un singleton `log = LoggerService()` se expone en `__init__.py`. `start()`/
`shutdown()` se enganchan al `lifespan` de FastAPI (junto al scheduler).

## Cómo se usa (y se extiende)

Emitir desde cualquier parte:

```python
from pulsar.logger import log, JobLog
log.emit(JobLog(ts=now, job="sync-movements", status="ok", rows=42))
```

Añadir un tipo nuevo mañana (p.ej. websockets) — **sin tocar el core**:

```python
# records.py
class WebsocketLog(LogRecord):
    KIND: ClassVar[str] = "websocket_logs"
    event: str = ""
    client: str = ""
    payload_size: int = 0

# en el arranque:
log.register(WebsocketLog, SqliteSink(DB, "websocket_logs", WebsocketLog))

# en cada evento de websocket:
log.emit(WebsocketLog(ts=now, event="message", client=cid, payload_size=n))
```

## Captura de los tipos iniciales

- **`job_logs`** (JobLog): `run_job` captura cada corrida de job. `detail` lleva
  "N rows" o el repr del error; `rows` la cuenta.
- **`api_logs`** (ApiLog): `LoggingMiddleware` captura cada request. Metadata
  siempre; body completo solo si `failed` (con tope de tamaño; redacción a futuro).
- **`performance_logs`** (PerformanceLog): un thread sampler con **psutil** cada
  ~15 s (CPU/RAM/disco del host+proceso). Independiente de las ejecuciones.

Se cruzan por **timestamp** (y `correlation_id`): "RAM alta 3-4 pm → qué corrió".

## Consulta unificada

`log.connect_duckdb()` devuelve una conexión DuckDB que attachea `logs/logs.sqlite`
(y a futuro los parquet/JSONL). Permite SQL sobre todos los tipos a la vez:

```sql
-- requests durante la ventana de RAM alta
SELECT a.* FROM api_logs a
JOIN performance_logs p ON a.started_at <= p.ts AND p.ts <= a.finished_at
WHERE p.rss_mb > 4000;
```

## Escalado futuro (lo que lo hace "bien hecho")

- **Niveles** (info/warn/error) y filtrado por nivel.
- **Retención/rotación**: pruning de SQLite + roll-off a parquet; rotación de
  archivos JSONL.
- **Redacción/scrubbing** de campos sensibles antes de persistir (PII/compliance).
- **Sampling** de bodies de éxito (no solo error) cuando se quiera muestrear.
- **Colector externo** de recursos (proceso aparte) para sobrevivir caídas del
  server y capturar el instante del crash.
- **Backpressure**: si la cola se llena, drop con contador (nunca bloquear).
- **Endpoints de consulta** en el API: ya implementados como una sola colección
  polimórfica `GET /v1/logs?type=job|api|performance` (estándar RESTful,
  [`arquitectura-restful.md`](./arquitectura-restful.md) §18.2).

## Plan de implementación (por fases)

1. ✅ **Core del framework** — `LogRecord`, `Sink` (ABC) + `SqliteSink`,
   `LoggerService` (registry + emit + worker de flush + shutdown), `log`
   singleton, `context.py` (correlation), `config.py`. + tests.
2. ✅ **Tipos iniciales + captura** — `JobLog` en `run_job` + `ApiLog` vía
   `LoggingMiddleware`; `PerformanceLog` con el sampler psutil. Arranque/cierre en
   el `lifespan` del API. + tests.
3. ✅ **Consulta unificada** — `query()` + `connect_duckdb()`; endpoint de
   lectura unificado `GET /v1/logs?type=job|api|performance` (colección polimórfica
   RESTful, ver `arquitectura-restful.md` §18.2). + tests.
4. ⏳ **Escalado (futuro, no ahora)** — FileSink/ParquetSink, retención, redacción,
   sampling, colector externo.

`logs/logs.sqlite` siempre **aparte** del lake de negocio. `psutil` se añadió como
dependencia en la fase 2.

