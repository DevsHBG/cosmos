---
id: null
type: moc
project: vault
parent: null
status: Vigente
alcance: "Todo el vault codex/"
created: 2026-06-30
updated: 2026-06-30
relacionado: []
tags: [indice]
---

# Índice — codex

↑ Raíz del vault (sin padre).

Fuente única de documentación técnica y teórica de `cosmos`. Esta es la
**única nota que se carga por defecto**; todo lo demás se carga bajo demanda,
por dominio, desde las MOC de abajo.

## Cómo navegar

- Cada nota declara su `parent` en el frontmatter y vive bajo el dominio que
  la contiene. No hay enlaces sueltos entre notas hoja: si hace falta ver cómo
  se relacionan dos temas, se sube a su MOC común.
- Las normas que rigen este vault (tipos de nota, frontmatter, límites de
  enlaces) están en [`CODEX-STD-001`](./codex-std-001-estandar-del-codex.md).

## Dominios

| Dominio | MOC | Qué cubre |
| --- | --- | --- |
| Monorepo (Nivel 1) | [`moc-monorepo`](../10-monorepo/moc-monorepo.md) | Estándares transversales a todo `cosmos`, decisiones de arquitectura de la suite |
| Pulsar (Nivel 2) | [`moc-pulsar`](../20-pulsar/moc-pulsar.md) | Backend de carga/análisis sobre SAP B1: estándares, arquitectura, referencia, investigación, roadmap |
| Crux (Nivel 2) | [`moc-crux`](../30-crux/moc-crux.md) | Frontend de la suite: roadmap (aún sin estándares propios) |

## Meta

- [`CODEX-STD-001` — normas del vault](./codex-std-001-estandar-del-codex.md)
- [Plantillas](./plantillas/) — una por tipo de nota
