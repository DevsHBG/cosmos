# cosmos

Monorepo políglota. Agrupa proyectos **independientes y autocontenidos**; la raíz
**no tiene stack, dependencias ni build propios** — cada proyecto gestiona el suyo.

## Proyectos

| Proyecto | Lenguaje | Descripción |
| -------- | -------- | ----------- |
| [`pulsar`](projects/pulsar) | Python | Plataforma de carga, síntesis, análisis y consulta sobre SAP Business One |

## Navegación

- Cada proyecto vive en `projects/<nombre>` y **se documenta a sí mismo**: empieza
  por su `README.md` y su carpeta `docs/`. Lo específico de un proyecto (toolchain,
  arquitectura, estándares) vive ahí, no aquí.
- Trabaja **dentro** de la carpeta del proyecto; no hay comandos a nivel de raíz.

## Documentación

Toda la documentación técnica y teórica de la suite — estándares, decisiones de
arquitectura, investigación, roadmaps — vive en el vault de Obsidian
[`codex/`](codex/00-vault/00-indice.md), fuente única de verdad (reemplaza al
antiguo `docs/`). Empieza por su [índice](codex/00-vault/00-indice.md).

## Estándares globales (Nivel 1)

Las reglas transversales del monorepo viven en
[`codex/10-monorepo/moc-monorepo.md`](codex/10-monorepo/moc-monorepo.md) (marco
de gobernanza en cascada + índice). **Todo proyecto las hereda.** Vigentes hoy:

- **`COSMOS-STD-001`** — un gestor de paquetes idiomático por lenguaje: **pnpm**
  para Node/JS/TS, **uv** para Python.

Otras decisiones transversales de la suite viven en el mismo dominio (p. ej.
[`identidad-y-autorizacion.md`](codex/10-monorepo/decisiones/identidad-y-autorizacion.md)).

## Pendiente

Contexto de negocio global y guía de navegación para herramientas agénticas (un
`CLAUDE.md` en la raíz). Aún por definir.
