---
id: null
type: moc
project: monorepo
parent: "[[00-indice]]"
status: Vigente
alcance: "Nivel 1 — todo cosmos"
created: 2026-06-30
updated: 2026-06-30
relacionado: []
tags: [gobernanza]
---

# Monorepo (Nivel 1)

↑ Pertenece a: [Índice](../00-vault/00-indice.md)

Reglas y decisiones transversales a **todo** `cosmos`: lo que cualquier
proyecto (`pulsar`, `crux`, los que vengan) hereda sin tener que redecidirlo.

## Principio rector: coherencia

Antes que cualquier regla concreta, la suite optimiza por **coherencia**: para
cada preocupación transversal (gestionar dependencias, versionar, commitear,
construir en CI…) **DEBE** existir **una sola forma idiomática**, y todos los
proyectos la siguen. La consistencia del monorepo gana a la preferencia local
de un proyecto, **salvo justificación medida y documentada** (no por gusto ni
por costumbre).

Esto importa porque `cosmos` es **políglota y crecerá sin control**: cada
divergencia "inocente" multiplica el costo de onboarding, CI, revisión y
mantenimiento a lo largo de toda la suite. Un estándar no existe para limitar,
sino para que *no haya que decidir lo mismo dos veces*.

La mecánica de la cascada de gobernanza (herencia, override con
justificación, default seguro) es la misma para todo `cosmos` y vive en
[`CODEX-STD-001`](../00-vault/codex-std-001-estandar-del-codex.md) — no se
repite aquí por dominio.

## Contenido

- [`COSMOS-STD-001` — gestor de paquetes](./estandares/cosmos-std-001-gestor-de-paquetes.md)
- [Identidad y autorización (decisión de arquitectura)](./decisiones/identidad-y-autorizacion.md)

## Estándares vigentes

| ID | Tema | Estado | Archivo |
| --- | --- | --- | --- |
| `COSMOS-STD-001` | Gestor de paquetes y toolchain por lenguaje (pnpm/uv) | Vigente | [`cosmos-std-001-gestor-de-paquetes.md`](./estandares/cosmos-std-001-gestor-de-paquetes.md) |
