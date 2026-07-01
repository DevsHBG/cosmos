---
id: null
type: moc
project: pulsar
parent: "[[moc-monorepo]]"
status: Vigente
alcance: "Proyecto pulsar"
created: 2026-06-30
updated: 2026-06-30
relacionado: []
tags: []
---

# Pulsar

↑ Pertenece a: [Monorepo](../10-monorepo/moc-monorepo.md)

Backend de carga, síntesis, análisis y consulta sobre SAP Business One.
Hereda los estándares del monorepo y especializa los suyos propios aquí.

## Principio rector: coherencia

Antes que cualquier regla concreta, Pulsar optimiza por **coherencia**: para
cada preocupación (modelar datos, manejar errores, nombrar, configurar,
loggear, testear…) **DEBE** existir **una sola forma idiomática** y todo el
código la sigue. La consistencia de un proyecto gana a la optimización local
de un archivo, **salvo justificación medida y documentada** (no por gusto ni
por costumbre de quien escribe).

La mecánica de la cascada (herencia, override con justificación, default
seguro) es la misma para todo `cosmos` y vive en
[`CODEX-STD-001`](../00-vault/codex-std-001-estandar-del-codex.md) — no se
repite aquí por dominio.

## Contenido

- [`PULSAR-STD-001` — modelado de datos](./estandares/pulsar-std-001-modelado-de-datos.md)
- [Arquitectura RESTful](./arquitectura/arquitectura-restful.md)
- [Observabilidad](./arquitectura/observabilidad.md)
- [Diccionario de datos — inventory.movements](./referencia/diccionario-datos-inventory-movements.md)
- [Investigación: reabasto CEDIS](./investigacion/reabasto-cedis.md)
- [Roadmap](./roadmap/roadmap-pulsar.md)

## Estándares vigentes

| ID | Tema | Estado | Archivo |
| --- | --- | --- | --- |
| `PULSAR-STD-001` | Modelado de datos y coherencia de tipos (Pydantic por defecto) | Vigente | [`pulsar-std-001-modelado-de-datos.md`](./estandares/pulsar-std-001-modelado-de-datos.md) |
| `arquitectura-restful.md` §18 | Estándar RESTful normativo de la API de Pulsar | Vigente | [`arquitectura-restful.md`](./arquitectura/arquitectura-restful.md) |
