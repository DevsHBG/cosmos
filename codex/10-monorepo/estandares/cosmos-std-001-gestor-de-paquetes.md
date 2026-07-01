---
id: COSMOS-STD-001
type: standard
project: monorepo
parent: "[[moc-monorepo]]"
status: Vigente
alcance: "Nivel 1 — todo cosmos. Todo proyecto en projects/ y cualquier tooling con dependencias."
created: 2026-06-30
updated: 2026-06-30
relacionado: []
tags: [toolchain]
---

# Gestor de paquetes y toolchain por lenguaje

↑ Pertenece a: [Monorepo](../moc-monorepo.md)

| | |
| --- | --- |
| **ID** | `COSMOS-STD-001` |
| **Estado** | Vigente |
| **Alcance** | Nivel 1 — todo `cosmos`. Todo proyecto en `projects/` y cualquier tooling con dependencias. |
| **Resumen** | **Un solo gestor de paquetes idiomático por lenguaje.** Node/JS/TS → **pnpm**; Python → **uv**. El lockfile se commitea y los builds de CI se hacen *desde* el lockfile. |

## Contexto

`cosmos` es un monorepo **políglota** de proyectos autocontenidos: cada uno
gestiona su propio stack (ver [`README` raíz](../../../../README.md)). Pero
*cuál* gestor de paquetes se usa no es una decisión local: es una
**preocupación transversal**. Si cada proyecto elige distinto (npm aquí, yarn
allá, pip + venv en uno, poetry en otro), se paga en onboarding, en
plantillas de CI, en docs, en reproducibilidad de builds y en el costo de
saltar entre proyectos. Aplicar el [principio de
coherencia](../moc-monorepo.md#principio-rector-coherencia) al toolchain
elimina ese costo: se decide una vez, para toda la suite.

Las elecciones —**pnpm** y **uv**— no son arbitrarias: ambos son gestores
rápidos, con resolución determinista, lockfile de primera clase,
`workspaces`/monorepo nativo y *runner* de scripts integrado. Son el idioma
moderno de cada ecosistema en 2026.

## Regla

### Node / JavaScript / TypeScript → `pnpm`

- Todo proyecto Node **DEBE** usar **pnpm** para instalar, resolver y ejecutar
  scripts. El lockfile **`pnpm-lock.yaml` DEBE** estar commiteado.
- La versión de pnpm **DEBERÍA** fijarse vía **corepack**, declarándola en el
  campo **`packageManager`** de `package.json` (builds reproducibles entre
  máquinas).
- Las tareas del proyecto **DEBERÍAN** correrse con el runner de pnpm
  (`pnpm <script>`, `pnpm dlx` para ejecuciones puntuales).
- **NO** se usan `npm install` / `yarn` / `bun` para gestionar dependencias
  del proyecto. (`npx`/`pnpm dlx` puntual para *scaffolding* de un proyecto
  nuevo está bien; lo que no se mezcla es el gestor de dependencias del repo.)
- En CI, la instalación **DEBE** ser desde lockfile: `pnpm install --frozen-lockfile`.

### Python → `uv`

- Todo proyecto Python **DEBE** usar **uv** para entornos, instalación,
  *lock* y ejecución. El lockfile **`uv.lock` DEBE** estar commiteado y
  `pyproject.toml` (PEP 621 / PEP 735) es el manifiesto.
- Las tareas **DEBERÍAN** correrse con `uv run` y las dependencias
  gestionarse con `uv add` / `uv sync`.
- **NO** se usan `pip` / `pipenv` / `poetry` / `conda` directamente para
  resolver o instalar dependencias del proyecto.
- En CI, la instalación **DEBE** ser desde lockfile: `uv sync --frozen` (o
  `--locked`).

## Excepciones

Un proyecto o módulo **PUEDE** desviarse solo con **justificación técnica
concreta y documentada** (un ID de override + la razón: p. ej. una
herramienta que no soporta pnpm workspaces, o un build upstream que exige
otro gestor). "Me gusta más" o "es a lo que estoy acostumbrado" **no** son
justificación. La excepción se documenta junto al código que la usa (nivel 3)
y **DEBERÍA** listarse aquí para ser descubrible. Ante la duda, se usa el
gestor estándar.

## Estado actual / brechas

- **`pulsar`** (Python) ya usa **uv** (`uv.lock`, `pyproject.toml`, tooling
  vía `uv`) — **cumple**.
- **`crux`** (frontend) nace con **pnpm** desde el día 1 — cumple por
  construcción.
- No hay excepciones registradas.

## Consecuencias

- **Onboarding único:** un solo comando de instalación por lenguaje en toda
  la suite.
- **CI uniforme:** las plantillas de pipeline se reutilizan entre proyectos.
- **Builds reproducibles:** el lockfile commiteado + `--frozen` garantizan la
  misma resolución en cualquier máquina.
- **Menos carga cognitiva** al saltar entre proyectos del monorepo.
