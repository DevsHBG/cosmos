---
id: PULSAR-STD-001
type: standard
project: pulsar
parent: "[[moc-pulsar]]"
status: Vigente
alcance: "Proyecto pulsar"
created: 2026-06-30
updated: 2026-06-30
relacionado: []
tags: [pydantic, modelado]
---

# Modelado de datos y coherencia de tipos

↑ Pertenece a: [Pulsar](../moc-pulsar.md)

| | |
| --- | --- |
| **ID** | `PULSAR-STD-001` |
| **Estado** | Vigente |
| **Alcance** | Proyecto (`pulsar`) |
| **Marco** | [Pulsar](../moc-pulsar.md) — aplicación del principio de coherencia |

> **Resumen.** Toda estructura de datos de Pulsar —DTOs, registros, modelos de
> dominio, configuración— se modela con **Pydantic v2** (`BaseModel` /
> `BaseSettings`). `dataclass`, `NamedTuple`, `dict` crudo o tuplas posicionales
> **no** son la forma por defecto: solo se usan como **excepción justificada y
> documentada** a nivel de módulo (§4).

## 1. Contexto

Pulsar mezcla hoy dos formas de modelar datos sin un criterio explícito, a veces
**dentro del mismo módulo**:

- `jobs/runs.py` modela `Run` (estado de una corrida) con Pydantic `BaseModel`.
- `jobs/core.py`, su vecino, modela `JobContext` y `JobResult` con
  `@dataclass(frozen=True, slots=True)`.

Ninguna de las dos es incorrecta en aislamiento, pero conviven sin razón: dos
estilos para el mismo tipo de objeto obligan a quien lee a recordar cuál se usó
dónde, complican la (de)serialización uniforme y abren la puerta a que cada nuevo
módulo elija a dedo. Es justo la divergencia "inocente" que el
[principio de coherencia](../moc-pulsar.md#principio-rector-coherencia) busca evitar.

El proyecto ya apuesta por Pydantic en sus fronteras: esquemas de la API
(`api/schemas.py`), errores (`api/problem.py`), configuración (`config/settings.py`,
`pydantic-settings`) y registros del logger (`logger/records.py`). La decisión
natural es **unificar hacia Pydantic** y tratar `dataclass` como la excepción, no
como una alternativa equivalente.

## 2. Regla

- El código **DEBE** modelar sus estructuras de datos con **Pydantic v2**:
  `BaseModel` para valores, DTOs y **objetos de comando** (los `Job`: parámetros
  tipados + un método que actúa), `BaseSettings` (`pydantic-settings`) para
  configuración cargada del entorno.
- Esto **DEBE** cumplirse para todo dato que cruce una **frontera** —entrada/salida
  de la API, configuración, payloads (de)serializados, registros persistidos o
  logueados, datos que vienen de o van hacia un sistema externo— porque ahí la
  validación y la serialización de Pydantic son una ganancia directa.
- Dentro de un mismo módulo o capa conceptual **NO DEBE** mezclarse Pydantic con
  `dataclass` para objetos del mismo rol. Se elige uno y se mantiene.
- **El límite del estándar son los servicios con estado vivo.** Lo que sostiene
  recursos que no son datos —una conexión abierta, un `Lock`, una cola con su
  hilo— vive en **clases normales**, no en Pydantic (envolverlo solo añadiría
  `PrivateAttr` y fricción). En el repo: el *runs store* (`jobs/runs.py`) y los
  *sinks* del logger. La lógica pura vive en **funciones**. Pydantic es para
  **modelar datos**, no para envolver todo.
- Cuando un modelo Pydantic deba **contener** un objeto de un tipo externo no
  validable (p. ej. un `CronTrigger` de APScheduler en `ScheduledJob`), se habilita
  `model_config = ConfigDict(arbitrary_types_allowed=True)`: sigue siendo un modelo
  de datos, con un campo opaco.

## 3. Convenciones de uso de Pydantic

- **v2 siempre.** API de Pydantic 2 (`model_config`, `model_validate`,
  `model_dump`); nada de la API v1 (`Config` de clase, `.dict()`, `.parse_obj()`).
- **Inmutabilidad por defecto.** Los modelos que representan un valor o un evento
  **DEBERÍAN** ser `model_config = ConfigDict(frozen=True)`, como ya hace `Run`.
- **Configuración con `BaseSettings`.** Todo settings se carga con
  `pydantic-settings` y su `env_prefix` (`PULSAR_*`), como en `config/settings.py`
  y `RunStoreSettings`. No se leen variables de entorno a mano.
- **Tipos explícitos y estrictos.** Anotaciones completas (el proyecto corre `mypy`
  en modo strict); evitar `Any` salvo en límites inevitables.
- **Comportamiento, en propiedades/métodos.** Derivados como `JobResult.ok` o
  `duration_s` siguen siendo `@property`/métodos del modelo; Pydantic no lo impide.

## 4. Excepción: cuándo se permite `dataclass`

Pydantic es el default **incluso para objetos puramente internos** (p. ej.
`RetailDate`, que no cruza ninguna frontera y aun así es Pydantic). Un módulo
**PUEDE** usar `@dataclass` **solo** si se cumple **y se documenta** (nivel 3 del
marco — junto al código, citando este ID y la razón):

- **Rendimiento medido.** Un objeto en un camino caliente donde el overhead de
  construcción de Pydantic se ha **medido** y es relevante. La sospecha no basta:
  hace falta el número.
- **Interoperabilidad.** Una librería externa exige específicamente un `dataclass`
  (p. ej. introspección de `dataclasses.fields`) que Pydantic no satisface.

Cuando aplica, la forma prescrita es `@dataclass(frozen=True, slots=True)`, no una
clase mutable suelta. Una excepción no documentada es una **violación del
estándar**, no una excepción.

> No confundir con los **servicios con estado vivo** (§2): esos no son una
> *excepción* a Pydantic sino otra categoría (clases normales), y no necesitan
> justificación caso por caso.

## 5. Estado actual

**Migración completada:** no quedan `dataclass` en el código de producción ni en
los *fakes* de los tests. Lo migrado a Pydantic:

| Antes (`dataclass`) | Ahora |
| ------------------- | ----- |
| `jobs/core.py` → `JobContext`, `JobResult`, base `Job` | `BaseModel(frozen=True)` |
| `jobs/movements.py` → `SyncMovements`, `BackfillMovements` | `BaseModel` (heredan de `Job`) |
| `jobs/scheduler.py` → `ScheduledJob` | `BaseModel(frozen=True, arbitrary_types_allowed=True)` (lleva un `CronTrigger`) |
| `retail/calendar.py` → `RetailDate` | `BaseModel(frozen=True)` |

Fuera de Pydantic **por diseño** (§2 — servicios con estado vivo, ya eran clases
normales): el *runs store* (`jobs/runs.py`: conexión SQLite + `Lock`) y los *sinks*
del logger (cola + hilo). Toda la suite (`mypy --strict`, `pytest`) pasa tras la
migración.

## 6. Consecuencias

- **A favor.** Un solo modelo mental para todos los datos; validación y
  (de)serialización uniformes y gratis en las fronteras; menos decisiones por
  archivo; revisiones más simples.
- **En contra.** Pydantic añade un pequeño overhead de construcción frente a un
  `dataclass` con `slots`; §4 existe precisamente para los casos donde eso, medido,
  pesa.
- **Migración.** El código nuevo nace cumpliendo §2 desde ya. El existente se
  alinea de forma incremental; la única brecha viva está en §5.
