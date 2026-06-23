# cosmos

Monorepo políglota. Es únicamente el repositorio que agrupa proyectos
independientes; **no contiene configuración ni dependencias propias**.

Cada proyecto vive bajo `projects/<nombre>` y es **autocontenido**: gestiona su
propio stack (lenguaje, dependencias, herramientas, lockfile, build). Un proyecto
puede ser de Python, otro de Node.js, otro de C#, etc.

## Estructura

```
cosmos/
├── README.md
├── .gitignore            # solo entradas generales (OS/IDE)
└── projects/
    └── pulsar/           # proyecto de Python (ver su propio README)
```

## Proyectos

| Proyecto | Lenguaje | Descripción |
| -------- | -------- | ----------- |
| [`pulsar`](projects/pulsar) | Python | Python Utility for Loading, Synthesis, Analysis & Retrieval |

## Convenciones

- Cada proyecto define su toolchain y sus decisiones (p. ej. `pulsar` lo hace en
  `projects/pulsar/docs/adr/`).
- Trabaja siempre **dentro** de la carpeta del proyecto; no hay comandos a nivel
  de raíz.



  Capa 1 — Lógica de job (YA EXISTE)
           sync_company / backfill_company / maintain(futuro)  ← funciones puras

  Capa 2 — Capa de jobs  (pulsar/jobs/)   ← lo que falta y es la base
           · registry: cada job con nombre, callable, trigger/horario, params
           · runner serializado: write-lock para el lake + estado/historial de corridas

  Capa 3 — Invocadores (todos llaman a la Capa 2, comparten contrato)
           3a CLI (delgado)        python -m pulsar.jobs run sync
           3b Scheduler            APScheduler 3.x, horarios declarados EN código
           3c Servidor FastAPI     hospeda el scheduler en su lifespan;
                                   expone status/historial/trigger manual/health

  