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

## Pendiente

Esta raíz alojará lo **global** del monorepo —reglas transversales, contexto de
negocio y guía de navegación para herramientas agénticas (p. ej. Claude Code)—.
Aún por definir.
