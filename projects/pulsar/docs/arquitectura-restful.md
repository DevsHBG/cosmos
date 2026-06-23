# Arquitectura RESTful — guía y estándar de Pulsar

> Documento de referencia + **estándar normativo** para la API de Pulsar. La
> primera mitad explica REST "de verdad" (qué es, de dónde sale, las reglas que
> importan); la segunda fija las **convenciones que la API de Pulsar DEBE seguir**.
> El refactor de los endpoints actuales a este estándar es un paso aparte (ver
> [`ROADMAP.md`](../ROADMAP.md)).
>
> Convención de palabras clave (estilo RFC 2119): **DEBE** = obligatorio,
> **DEBERÍA** = recomendado salvo buena razón, **PUEDE** = opcional.

## Índice

1. [Qué es REST (y qué no)](#1-qué-es-rest-y-qué-no)
2. [Las 6 restricciones de Fielding](#2-las-6-restricciones-de-fielding)
3. [Interfaz uniforme y HATEOAS](#3-interfaz-uniforme-y-hateoas)
4. [Modelo de madurez de Richardson](#4-modelo-de-madurez-de-richardson)
5. [Recursos, colecciones y diseño de URIs](#5-recursos-colecciones-y-diseño-de-uris)
6. [Métodos HTTP: semántica, safe e idempotente](#6-métodos-http-semántica-safe-e-idempotente)
7. [Códigos de estado](#7-códigos-de-estado)
8. [Negociación de contenido y media types](#8-negociación-de-contenido-y-media-types)
9. [Errores: RFC 9457 Problem Details](#9-errores-rfc-9457-problem-details)
10. [Colecciones: filtrado, orden, campos y búsqueda](#10-colecciones-filtrado-orden-campos-y-búsqueda)
11. [Paginación](#11-paginación)
12. [Operaciones asíncronas (jobs)](#12-operaciones-asíncronas-jobs)
13. [Caché y peticiones condicionales](#13-caché-y-peticiones-condicionales)
14. [Idempotencia y reintentos](#14-idempotencia-y-reintentos)
15. [Versionado](#15-versionado)
16. [Seguridad](#16-seguridad)
17. [Documentación (OpenAPI)](#17-documentación-openapi)
18. [Estándar Pulsar (normativo)](#18-estándar-pulsar-normativo)
19. [Referencias](#19-referencias)

---

## 1. Qué es REST (y qué no)

**REST** (Representational State Transfer) es un **estilo arquitectónico** para
sistemas distribuidos, definido por Roy Fielding en el capítulo 5 de su tesis
(2000). No es un protocolo ni un estándar: es un conjunto de **restricciones** que,
si se respetan, dan propiedades deseables (escalabilidad, evolución independiente
cliente/servidor, visibilidad, fiabilidad, reuso de la infraestructura de la web).

Idea central: el cliente y el servidor intercambian **representaciones** (JSON,
por ejemplo) del **estado de recursos**. El servidor no guarda estado de sesión del
cliente entre peticiones; toda la información necesaria viaja en cada request.

Errores comunes ("REST" mal entendido):

- "Usar JSON sobre HTTP" no es REST. Tunelar RPC sobre `POST /api` con un campo
  `action` es **Nivel 0** (ver §4), no REST.
- Verbos en la URL (`/getUser`, `/createOrder`) **no son REST**: el verbo lo da el
  método HTTP, no el path.
- 200 OK con `{"error": "..."}` dentro no es REST: el resultado lo expresa el
  **código de estado** HTTP.

---

## 2. Las 6 restricciones de Fielding

1. **Cliente-servidor**: separación de responsabilidades; la UI y el almacenamiento
   evolucionan por separado.
2. **Stateless (sin estado)**: cada petición es autocontenida; el servidor no
   recuerda contexto entre requests. Mejora visibilidad, fiabilidad y escalado
   horizontal (cualquier nodo atiende cualquier request).
3. **Cacheable**: las respuestas se marcan (explícita o implícitamente) como
   cacheables o no; el cliente/intermediarios pueden reutilizarlas.
4. **Interfaz uniforme**: la restricción que distingue a REST (ver §3).
5. **Sistema en capas**: el cliente no sabe si habla con el servidor de origen o
   con un proxy/gateway/balanceador intermedio. Permite seguridad y escalado por
   capas.
6. **Code-on-demand** (*opcional*): el servidor PUEDE enviar código ejecutable
   (p. ej. JS). Única restricción opcional.

Una API que cumple 1–5 (6 es opcional) es RESTful en sentido arquitectónico.

---

## 3. Interfaz uniforme y HATEOAS

La **interfaz uniforme** es el corazón de REST y se descompone en 4 sub-restricciones:

1. **Identificación de recursos**: cada recurso tiene una URI estable
   (`/jobs/sync-movements`).
2. **Manipulación vía representaciones**: el cliente actúa sobre el recurso
   enviando/recibiendo una representación (el JSON), no tocando el almacenamiento
   directo.
3. **Mensajes auto-descriptivos**: cada mensaje lleva lo necesario para
   procesarlo (método, `Content-Type`, `Cache-Control`, etc.).
4. **HATEOAS** (*Hypermedia As The Engine Of Application State*): las respuestas
   incluyen **enlaces** a las acciones/recursos siguientes; el cliente navega por
   esos links en vez de hardcodear URIs.

**HATEOAS en la práctica**: es la parte más teórica y la que casi nadie implementa
completa. Para APIs internas/de servicio (como Pulsar) es **opcional**: aporta poco
frente a su costo cuando cliente y servidor evolucionan juntos. Pulsar apunta a un
**Nivel 2 sólido** (ver §4) y deja HATEOAS como mejora futura (p. ej. links
`next`/`prev` en paginación, que es hipermedia barata y útil).

---

## 4. Modelo de madurez de Richardson

Leonard Richardson describe 4 niveles de adopción de REST (popularizado por Martin
Fowler):

| Nivel | Nombre | Qué cambia |
|---|---|---|
| **0** | El pantano del POX | HTTP como túnel RPC: un solo endpoint, todo `POST`. |
| **1** | Recursos | URIs por recurso (`/jobs/x`, `/logs/y`) en vez de un endpoint único. |
| **2** | Verbos HTTP | Uso correcto de métodos (GET/POST/PUT/DELETE) y **códigos de estado**. |
| **3** | Controles hipermedia | Respuestas con links que guían las acciones siguientes (HATEOAS). |

**Objetivo de Pulsar: Nivel 2 riguroso.** Recursos bien modelados, métodos y
status codes correctos, errores estándar. El Nivel 3 (HATEOAS) es bienvenido donde
sea barato (paginación), pero no obligatorio.

---

## 5. Recursos, colecciones y diseño de URIs

Un **recurso** es un *sustantivo* (una cosa): un job, un log, una corrida. Hay dos
formas canónicas:

- **Colección**: `/jobs` — el conjunto.
- **Recurso individual** (*item*): `/jobs/{name}` — un elemento identificado.

Reglas de URIs (consolidadas de Zalando y Google AIP):

- **Sustantivos en plural** para colecciones: `/jobs`, `/logs`, `/runs`. (Evitar
  `/job`, `/getJobs`.)
- **Sin verbos en el path**: el verbo es el método HTTP. Una acción que no encaja
  en CRUD se modela como recurso (ver §12) o, excepcionalmente, como *custom method*.
- **`kebab-case` en segmentos de path**: `/job-logs`, `/shipment-orders/{id}`.
  Patrón: `^[a-z][a-z0-9-]*$`.
- **`snake_case` en query params**: `?correlation_id=...&page_size=50`.
- **Sub-recursos anidados** cuando hay relación de pertenencia:
  `/jobs/{name}/runs/{run_id}`. Cada nivel debe ser una URI válida por sí misma.
  **Máximo ~3 niveles** de anidación.
- **La estructura de la API no tiene que reflejar el esquema de la BD** (acoplar
  ambos es deuda técnica). Modela el dominio, no las tablas.
- IDs estables y opacos para el cliente; no exponer detalles internos en la URI.

Google AIP resume las operaciones en **5 métodos estándar** (List, Get, Create,
Update, Delete) y deja los **custom methods** (`POST /resource:verb`) solo para lo
que no encaja (imports, exports, transacciones, "ejecutar").

---

## 6. Métodos HTTP: semántica, safe e idempotente

Definidos en **RFC 9110** (HTTP Semantics, 2022 — consolida y reemplaza las viejas
RFC 723x). Dos propiedades clave:

- **Safe**: sin efectos secundarios observables (solo lectura).
- **Idempotente**: ejecutarla N veces tiene el mismo efecto que una vez (clave para
  **reintentos** seguros tras fallos de red).

| Método | Safe | Idempotente | Cacheable | Uso |
|---|:---:|:---:|:---:|---|
| **GET** | ✅ | ✅ | ✅ | Leer un recurso/colección. |
| **HEAD** | ✅ | ✅ | ✅ | Como GET pero solo headers. |
| **OPTIONS** | ✅ | ✅ | ❌ | Capacidades/CORS. |
| **POST** | ❌ | ❌ | ⚠️ solo con freshness explícita | Crear en colección; acciones no idempotentes. |
| **PUT** | ❌ | ✅ | ❌ | Reemplazo completo / upsert en URI conocida. |
| **PATCH** | ❌ | ❌ | ❌ | Modificación parcial. |
| **DELETE** | ❌ | ✅ | ❌ | Borrar un recurso. |

Notas:

- **Todo método safe es idempotente**, pero no al revés (PUT/DELETE son idempotentes
  y no safe).
- **POST vs PUT**: usa `POST /jobs` cuando el servidor asigna el ID; `PUT /jobs/{id}`
  cuando el cliente conoce/define el ID y manda la representación completa.
- **PATCH** no es idempotente en general (p. ej. `qty += 1`); para parches usar
  JSON Merge Patch (RFC 7386) o JSON Patch (RFC 6902).

---

## 7. Códigos de estado

Usar el código que comunica el resultado; **nunca** 200 con un error embebido.

**2xx — éxito**
- `200 OK` — éxito con cuerpo (GET, o POST/PUT que devuelven el recurso).
- `201 Created` — recurso creado; **DEBE** incluir header `Location` con su URI.
- `202 Accepted` — aceptado para procesamiento **asíncrono** (aún no terminado).
- `204 No Content` — éxito sin cuerpo (típico de DELETE o PUT sin respuesta).

**3xx — redirección**
- `301/308` permanente, `302/307` temporal, `304 Not Modified` (peticiones
  condicionales, ver §13).

**4xx — error del cliente**
- `400 Bad Request` — sintaxis/forma inválida.
- `401 Unauthorized` — falta autenticación (o inválida).
- `403 Forbidden` — autenticado pero sin permiso.
- `404 Not Found` — recurso inexistente.
- `405 Method Not Allowed` — método no soportado por el recurso (incluir `Allow`).
- `406 Not Acceptable` / `415 Unsupported Media Type` — negociación de contenido.
- `409 Conflict` — choca con el estado actual (p. ej. duplicado, lock).
- `410 Gone` — existió y ya no.
- `412 Precondition Failed` / `428 Precondition Required` — peticiones condicionales.
- `422 Unprocessable Content` — sintaxis OK pero semánticamente inválido
  (validación de negocio). Definido en RFC 9110.
- `429 Too Many Requests` — rate limiting (con `Retry-After`).

**5xx — error del servidor**
- `500 Internal Server Error`, `502 Bad Gateway`, `503 Service Unavailable`
  (con `Retry-After`), `504 Gateway Timeout`.

Regla: **4xx = "lo arreglas tú (cliente)"**, **5xx = "lo arreglo yo (servidor)"**.

---

## 8. Negociación de contenido y media types

- El cliente expresa preferencias con `Accept` (p. ej. `application/json`); el
  servidor responde con `Content-Type`.
- Si no puede satisfacer el `Accept` → `406 Not Acceptable`. Si el cuerpo entrante
  tiene un `Content-Type` no soportado → `415 Unsupported Media Type`.
- Pulsar: **JSON** (`application/json`) como único media type de datos; errores en
  `application/problem+json` (§9).

---

## 9. Errores: RFC 9457 Problem Details

**RFC 9457** (2023, reemplaza a la 7807) define un formato estándar y
máquina-legible para errores HTTP. Media type: **`application/problem+json`**.

Miembros estándar (todos opcionales, pero útiles):

| Miembro | Tipo | Significado |
|---|---|---|
| `type` | URI | Identificador del **tipo** de problema (por defecto `about:blank`). |
| `title` | string | Resumen humano del tipo (estable entre ocurrencias). |
| `status` | número | El código HTTP (espejo del de la respuesta). |
| `detail` | string | Explicación específica de **esta** ocurrencia. |
| `instance` | URI | Identifica esta ocurrencia concreta. |

Se PUEDEN añadir **extension members** (campos propios); los clientes DEBEN ignorar
los que no reconozcan (compatibilidad hacia adelante).

Ejemplo (estilo Pulsar):

```json
{
  "type": "https://pulsar/errors/unknown-job",
  "title": "Unknown job",
  "status": 404,
  "detail": "No job named 'sync-moviments' is registered.",
  "instance": "/jobs/sync-moviments",
  "correlation_id": "a1b2c3d4"
}
```

`correlation_id` como extension member enlaza el error con el log (§ observabilidad
en [`observability.md`](./observability.md)).

---

## 10. Colecciones: filtrado, orden, campos y búsqueda

Toda operación sobre una colección se modela con **query parameters** sobre un `GET`
de la colección (no endpoints nuevos por cada combinación). Convenciones consolidadas
(Zalando / JSON:API / Google AIP):

- **Filtrado**: `?status=ok&type=job` — igualdad por campo. Para rangos, sufijos o
  params dedicados: `?since=...&until=...`.
- **Orden**: `?sort=-ts` (prefijo `-` = descendente; `ts` = ascendente). Múltiple:
  `?sort=-ts,job`.
- **Proyección / sparse fieldsets**: `?fields=ts,job,status` para pedir solo
  ciertos campos (reduce payload).
- **Búsqueda libre**: `?q=texto`.
- **Paginación**: `?limit=...&cursor=...` (ver §11).

**Punto de diseño clave (filtrar por tipo en una sola colección).** Cuando varios
sub-tipos comparten una base, es preferible **un solo recurso colección con un
filtro discriminador** que N endpoints paralelos:

```
✅  GET /logs?type=job        (un recurso, escala con nuevos tipos)
❌  GET /job-logs
    GET /api-logs
    GET /performance-logs     (un endpoint nuevo por cada tipo → no escala)
```

Esto es exactamente el mismo patrón que `GET /products?category=electronics`: `logs`
es la colección, `type` es un atributo filtrable. Añadir un tipo mañana
(`type=websocket`) **no agrega endpoints**: solo un valor más al enum. Cada item
lleva un campo discriminador `type` y, además de los campos comunes
(`ts`, `level`, `correlation_id`), los específicos de su tipo (unión discriminada).

Trade-off honesto: la colección es **heterogénea** (un `job` log y un `performance`
log no tienen las mismas columnas). Se acepta porque (a) comparten la base
`LogRecord`, (b) el campo `type` permite al cliente discriminar, y (c) la
escalabilidad y simplicidad de un solo recurso compensan. Si en el futuro un tipo
diverge demasiado, siempre se puede promover a su propio recurso.

---

## 11. Paginación

**Nunca** devolver listas no acotadas. Toda colección DEBE paginar. Dos estrategias:

- **Offset/limit** (`?limit=20&offset=100`): simple, permite saltar a una página
  arbitraria; **degrada** con offsets grandes (escaneo) y sufre *drift* si los datos
  cambian entre páginas (duplicados/saltos).
- **Cursor/keyset** (`?limit=20&cursor=<opaco>`): rendimiento **constante** y
  estable ante inserciones; el cursor apunta a un registro (p. ej. `ts,id`
  indexados). No permite "ir a la página 50" directo. **Recomendada** para
  series de tiempo grandes y crecientes (justo el caso de los logs).

Defaults razonables: `limit` por defecto 100, máximo 1000.

La respuesta DEBERÍA exponer cómo seguir, vía **`Link` header** (RFC 8288,
`rel="next"`/`rel="prev"`) y/o un sobre:

```json
{ "items": [ ... ], "next_cursor": "eyJ0cyI6..." }
```

---

## 12. Operaciones asíncronas (jobs)

Disparar un job es una acción **no idempotente y de larga duración** → no encaja en
GET/PUT/DELETE. Dos patrones válidos:

1. **Recurso "run" (preferido, REST puro)**: una corrida es un recurso.
   - `POST /jobs/{name}/runs` → **`202 Accepted`** + `Location: /jobs/{name}/runs/{id}`
     y un cuerpo con el estado inicial (`status: "queued"`).
   - `GET /jobs/{name}/runs/{id}` → consultar el progreso/resultado (polling).
   - `GET /jobs/{name}/runs` → historial de corridas (que **es** el log de jobs).
   - Ventaja: conecta naturalmente "disparar" → "consultar" → "historial", y el
     `JobLog` persistido es la representación de cada `run`.

2. **Custom method (pragmático)**: `POST /jobs/{name}:run` (estilo Google AIP) o
   `POST /jobs/{name}/run`. Más simple, pero el resultado no es un recurso
   consultable por URI propia.

Para async, el `202` indica "aceptado, aún no terminado"; el cliente hace **polling**
del recurso de estado (o, a futuro, webhooks/SSE).

---

## 13. Caché y peticiones condicionales

- **`Cache-Control`** declara cacheabilidad (`no-store`, `max-age`, `private`…).
- **ETag + `If-None-Match`**: el servidor manda un `ETag` (hash/versión); el cliente
  reenvía con `If-None-Match` y recibe **`304 Not Modified`** si no cambió (ahorra
  ancho de banda).
- **`Last-Modified` + `If-Modified-Since`**: variante por fecha.
- **`If-Match`** en escrituras → control de concurrencia optimista: si el ETag no
  coincide, `412 Precondition Failed` (evita "lost updates").

Para Pulsar (datos operativos que cambian seguido), la caché agresiva no aplica,
pero ETags en recursos individuales (un job, una corrida) son baratos y útiles.

---

## 14. Idempotencia y reintentos

- GET/PUT/DELETE son idempotentes → el cliente PUEDE reintentar sin miedo a duplicar.
- **POST no es idempotente**: reintentar tras un timeout puede crear duplicados. La
  solución estándar es el header **`Idempotency-Key`** (convención de Stripe, hoy
  en draft IETF `httpapi-idempotency-key-header`): el cliente manda una clave única;
  el servidor deduplica reintentos con la misma clave durante una ventana.
- Relevante para `POST .../runs`: una clave de idempotencia evita lanzar dos veces
  el mismo job por un reintento de red.

---

## 15. Versionado

Una vez publicada una versión, **nunca** se le hacen cambios *breaking*: se añaden
campos (no se quitan), y el comportamiento nuevo va en una versión nueva. Estrategias:

- **En la URI** (`/v1/...`): la más visible y simple de rutear/cachear; "contamina"
  la URI del recurso. La más común en la industria.
- **En header / media type** (`Accept: application/vnd.pulsar.v1+json`): mantiene la
  URI limpia (más "purista"), pero es menos visible y más difícil de probar a mano.
- **Query param** (`?version=1`): simple pero frágil; no recomendado.

Cambios *non-breaking* (añadir un campo opcional, un nuevo valor de enum, un endpoint
nuevo) **no** requieren versión nueva. Pulsar DEBERÍA prefijar con **`/v1`** desde el
inicio (barato ahora, caro de retrofitear).

---

## 16. Seguridad

- **TLS siempre** (HTTP→HTTPS).
- **Autenticación** vía esquema estándar (`Authorization: Bearer <token>`); nunca
  credenciales en la URI.
- **Autorización** por recurso/acción (menor privilegio). Distinguir `401` (no
  autenticado) de `403` (sin permiso).
- **No filtrar** detalles internos en errores (stack traces) hacia el cliente; sí
  registrarlos internamente (con `correlation_id`).
- **Rate limiting** (`429` + `Retry-After`) y validación estricta de input (`400`/
  `422`).

(Hoy la API de Pulsar es de un solo proceso/red interna; la auth de identidad es una
entrega futura — ver `ROADMAP.md` §auditoría.)

---

## 17. Documentación (OpenAPI)

FastAPI ya genera **OpenAPI** + Swagger UI (`/docs`) y ReDoc (`/redoc`)
automáticamente desde los modelos Pydantic y las firmas de los endpoints. El estándar
es: cada endpoint, parámetro y modelo de respuesta DEBE quedar reflejado y descrito
en el schema (FastAPI lo hace si tipamos bien response models, query params y status
codes). Documentar también los **errores** (`responses=`) con el modelo Problem Details.

---

## 18. Estándar Pulsar (normativo)

Reglas que la API de Pulsar **DEBE** seguir. (El refactor de los endpoints actuales
para cumplirlas es un paso aparte; ver `ROADMAP.md`.)

### 18.1 Convenciones generales

- Prefijo de versión **`/v1`** en todas las rutas de datos.
- Recursos en **plural**, paths en **`kebab-case`**, query params en **`snake_case`**.
- **Sin verbos** en los paths; el método HTTP es el verbo.
- Respuestas y cuerpos en **`application/json`**; errores en
  **`application/problem+json`** (RFC 9457) con `correlation_id` como extension member.
- Códigos de estado correctos (§7); jamás 200 con error embebido.
- Toda colección **pagina** y acota (`limit` default 100, máx 1000) y soporta
  `sort`, filtros por campo y `since`/`until` donde aplique.

### 18.2 Logs: una sola colección con filtro `type` (la mejora propuesta)

Reemplazar los tres endpoints actuales por **un recurso colección**:

```
GET /v1/logs?type=job|api|performance      # filtra por tipo (omitir = todos)
GET /v1/logs?type=job&status=failed&since=2026-06-01&sort=-ts&limit=50&cursor=...
```

- `logs` es la colección polimórfica de `LogRecord`; `type` es el discriminador
  filtrable. Cada item incluye `type` + campos comunes + campos del subtipo.
- **Escala sin endpoints nuevos**: un tipo futuro (`websocket`) = un valor más de
  `type`.
- Filtros estándar: `type`, `status`, `level`, `correlation_id`, `since`, `until`.
  Orden: `sort=-ts` (default). Paginación: **cursor** (series de tiempo).
- Se descartan `GET /job-logs`, `GET /api-logs`, `GET /performance-logs`.

### 18.3 Jobs y corridas

```
GET    /v1/jobs                      # lista de jobs registrados
GET    /v1/jobs/{name}               # un job + su última corrida
POST   /v1/jobs/{name}/runs          # disparar → 202 + Location: /v1/jobs/{name}/runs/{id}
GET    /v1/jobs/{name}/runs          # historial de corridas (= logs type=job de ese job)
GET    /v1/jobs/{name}/runs/{id}     # estado/resultado de una corrida
```

- `POST .../runs` (no `POST .../run`): la corrida es un **recurso**; el `202` +
  `Location` apuntan al recurso consultable. Admite `Idempotency-Key`.
- `404` con Problem Details para job inexistente (reemplaza el `detail` ad-hoc actual).

### 18.4 Operacional

- `GET /health` (liveness) se mantiene **sin** prefijo de versión (endpoint
  operativo, no recurso de dominio). PUEDE añadirse `GET /health/ready` (readiness).

### 18.5 Mapa de migración (estado actual → estándar)

| Hoy | Estándar |
|---|---|
| `GET /job-logs`, `/api-logs`, `/performance-logs` | `GET /v1/logs?type=…` |
| `POST /jobs/{name}/run` (202) | `POST /v1/jobs/{name}/runs` (202 + `Location`) |
| `GET /jobs`, `GET /jobs/{name}` | `GET /v1/jobs`, `GET /v1/jobs/{name}` |
| `HTTPException(detail=...)` | Problem Details (`application/problem+json`) |
| `?limit=` (offset implícito) | `?limit=&cursor=` + `Link` header / `next_cursor` |
| sin prefijo de versión | prefijo `/v1` |

---

## 19. Referencias

- Fielding, *Architectural Styles… (Cap. 5: REST)* — <https://ics.uci.edu/~fielding/pubs/dissertation/rest_arch_style.htm>
- RFC 9110 — *HTTP Semantics* (métodos, safe/idempotente, status) — <https://www.rfc-editor.org/rfc/rfc9110.html>
- RFC 9457 — *Problem Details for HTTP APIs* — <https://www.rfc-editor.org/rfc/rfc9457.html>
- RFC 8288 — *Web Linking* (`Link` header) — <https://www.rfc-editor.org/rfc/rfc8288.html>
- Martin Fowler — *Richardson Maturity Model* — <https://martinfowler.com/articles/richardsonMaturityModel.html>
- Google — *API Improvement Proposals (resource-oriented design, AIP-121+)* — <https://google.aip.dev/121>
- Zalando — *RESTful API and Event Guidelines* — <https://opensource.zalando.com/restful-api-guidelines/>
- JSON:API — *especificación (filtros, sort, fields, paginación)* — <https://jsonapi.org/>
- HATEOAS — <https://en.wikipedia.org/wiki/HATEOAS>
