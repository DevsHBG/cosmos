# Pulsar — Roadmap y planes futuros

Capacidades futuras, TODOs de mayor alcance y decisiones pendientes. Vive **fuera
de `CLAUDE.md`** a propósito: ese archivo se carga en contexto cada sesión, así
que solo lleva convenciones vigentes (lo que ES), no lo que viene.

## Observabilidad, auditoría y trazabilidad

> Estado: **primera entrega implementada** (servicio de logging reutilizable,
> fases 1–3 — ver abajo). Faltan la auditoría de acceso/identidad y el event
> sourcing de negocio.

Objetivo: logs de nivel empresarial de **todo**, en dos capas distintas:

1. **Observabilidad + auditoría de acceso/operación**: quién accedió a qué
   recurso por la API (quién, cuándo, cómo, qué, resultado), qué job corrió, si
   alguien lo disparó manualmente, etc. → logging estructurado + un **audit log
   consultable** (no texto suelto).
2. **Trazabilidad de eventos de negocio (event sourcing / lineage)**: ciclo de
   vida de cada entidad — orden de compra creada → enrutada a la torre de control
   → alguien cambió la cantidad. Cada paso es un evento **append-only** con actor,
   timestamp y antes/después; la "traza" = reproducir los eventos.

Hilar un **correlation id** API → job → escritura en el lake para seguir una
acción de punta a punta.

### Primera entrega (✅ implementada): servicio de logging reutilizable

**Diseño y estado: [`docs/observability.md`](./docs/observability.md).** Resumen:

- Un **servicio logger** reutilizable en toda la app (`from pulsar.logger import
  log`): tipos de log como clases extensibles (Pydantic + registry), sinks
  pluggables (SQLite hoy; archivos/parquet en la fase 4), escritura **no
  bloqueante** (cola + worker) y **consulta unificada** con DuckDB. Añadir un tipo
  nuevo (p.ej. websockets) = crear una clase y registrarla; el core no cambia.
- Tipos iniciales (se cruzan por timestamp): **`job_logs`** (corridas de jobs) y
  **`api_logs`** (requests HTTP) — ambos heredan de `ActivityLog`, metadata siempre,
  body completo solo si falló y con tope — y **`performance_logs`** (serie de tiempo
  de CPU/RAM/disco cada ~15 s, sampler psutil).
- Captura: `run_job` (jobs) + middleware HTTP (endpoints) + sampler (recursos);
  best-effort. Escribe en `logs/logs.sqlite`, **aparte** del lake. El historial de
  corridas de jobs ya se **graduó** a esta capa (la API lee `last_run` desde ahí).

Después: auditoría de **acceso/identidad** (quién, autorización) y **event
sourcing de negocio** (ciclo de vida de OC, etc.).

### Storage — decisión confirmada: **SQLite**

El motor del sistema de logs/auditoría/eventos es **SQLite**. La captura (un
insert por evento/acceso, durable, alta frecuencia = OLTP) va en una **SQLite
operativa aparte** (`logs/logs.sqlite`), **nunca** dentro del lake de negocio.

DuckDB **no** es el almacén vivo (column-store/OLAP: inserts de a una fila caros,
single-writer); se usa **solo para analizar** los logs después, leyendo la SQLite
directo o rolando a parquet.

El historial de corridas de jobs (`last_run`) fue el **primer cliente** de esta
capa: ya no vive en memoria, se reconstruye desde el último `JobLog` en
`logs/logs.sqlite`.

## API: alinear a estándar RESTful

> Estado: **entregado** (alineación al estándar en
> [`docs/arquitectura-restful.md`](./docs/arquitectura-restful.md) §18). Queda
> pendiente solo el recurso `run` con ciclo de vida pollable (ver abajo).

Implementado:

- **Logs en un solo recurso** `GET /v1/logs?type=job|api|performance` (colección
  polimórfica con filtro discriminador), en vez de los tres endpoints
  `GET /job-logs|/api-logs|/performance-logs`. Escala sin endpoints nuevos.
- **Problem Details** (RFC 9457, `application/problem+json`) para todos los errores,
  con `correlation_id` como extension member.
- Prefijo de versión **`/v1`** en los recursos de dominio (`/health` queda sin
  versión); paginación por **cursor** (`Link: rel="next"` + `next_cursor`); `sort` y
  filtros estándar (`status`/`level`/`correlation_id`/`since`/`until`).
- Corrida disparada como `POST /v1/jobs/{name}/runs` → `202` + `Location`, con
  `GET /v1/jobs/{name}/runs` (historial = `logs?type=job`).

### Pendiente: recurso `run` con ciclo de vida (diferido)

Hoy una corrida es **history-only**: no tiene `id` ni estado pollable propio, y el
`Location` del `202` apunta a la colección de historial (no al recurso creado).
Falta, cuando se justifique:

- Un **store de runs** creado en el *enqueue* (`status: queued→running→ok/failed`),
  para `GET /v1/jobs/{name}/runs/{id}` (polling) y un `Location` que apunte al run.
- Header **`Idempotency-Key`** en `POST .../runs` (dedup de reintentos de red,
  RFC §14), que necesita ese store para deduplicar.

## Mantenimiento del lake (diferido — después de la observabilidad)

Compactación (`ducklake_merge_adjacent_files`) + expiración de snapshots
(`ducklake_expire_snapshots` + cleanup, política `expire_older_than`), como un job
más de la capa de jobs, con su propio horario en el scheduler. Se hará **después**
de la primera entrega de observabilidad.
