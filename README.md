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
