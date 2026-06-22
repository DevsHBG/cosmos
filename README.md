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


  La mecánica base que describes es cierta: cada INSERT/append escribe un parquet nuevo (así es como el lakehouse logra ACID + time-travel). Sin mantenimiento, sí acumularías archivos. Pero por eso DuckLake trae cuatro herramientas justo para esto:

  1. Compactación — ducklake_merge_adjacent_files
  Junta muchos parquets pequeños en uno grande, sin perder snapshots. Corres esto en un cron (p.ej. semanal o tras la carga diaria) y tus ~14 archivos de la semana se vuelven 1–2. Tus "1095 archivos/año" colapsan a un puñado por mes.
  CALL ducklake_merge_adjacent_files('lake');

  2. Expiración + limpieza — ducklake_expire_snapshots (+ cleanup)
  Borra snapshots viejos y elimina físicamente los parquets que ya nadie referencia. Puedes fijar política:
  CALL lake.set_option('expire_older_than', '1 month');
  Así no guardas cada versión histórica para siempre.

  3. Inlining (activado por defecto, ≤10 filas)
  Escrituras diminutas van dentro del catálogo, sin generar parquet, y se vuelcan luego con ducklake_flush_inlined_data. Para tu carga batch diaria (que es de muchas filas) ayuda poco; sirve más para writes a goteo. Lo menciono para que sepas que los
  parquets "de 1 fila" ni siquiera ocurren.

  4. Particionado (Hive)
  Puedes particionar la tabla por columna (p.ej. company y/o año de doc_date) y los archivos se auto-organizan en subcarpetas navegables:
  ledger/movements/company=HR/year=2026/ducklake-<uuid>.parquet
  Mejora queries (pruning) y la legibilidad humana.