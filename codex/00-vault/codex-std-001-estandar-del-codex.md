---
id: CODEX-STD-001
type: standard
project: vault
parent: "[[00-indice]]"
status: Vigente
alcance: "Nivel 0 — todo codex/. Toda nota nueva DEBE cumplirlo; las existentes se migraron para cumplirlo."
created: 2026-06-30
updated: 2026-06-30
relacionado: []
tags: [gobernanza, meta]
---

# Estándar del codex — árbol, frontmatter y enlaces acotados

↑ Pertenece a: [Índice](./00-indice.md)

| | |
| --- | --- |
| **ID** | `CODEX-STD-001` |
| **Estado** | Vigente |
| **Alcance** | Nivel 0 — todo `codex/`. Toda nota nueva DEBE cumplirlo antes de crearse; toda nota existente se migró para cumplirlo. |
| **Resumen** | El codex es un **árbol, no un grafo**: toda nota (salvo este índice) tiene **exactamente un padre**. El frontmatter (`type`/`project`/`parent`/`status`) es la fuente de verdad para filtrar y navegar — no el grafo de enlaces. Los enlaces "relacionados" (no padre/hijo) están **acotados a 3 por nota**, cada uno con una razón de una línea. Una sola nota — el índice raíz — se carga por defecto; todo lo demás se carga bajo demanda, por dominio. |

## Contexto

`codex/` reemplaza a `docs/` (raíz) y a `<proyecto>/docs/` como fuente única de
verdad de la documentación técnica y teórica de `cosmos`. Esa documentación ya
tenía un sistema de gobernanza sólido (3 niveles en cascada, RFC-2119, IDs
estables) pero vivía en archivos sueltos enlazados a mano. Obsidian añade dos
riesgos si no se gobiernan desde el día uno:

1. **El grafo se vuelve una telaraña.** Una nota enlaza a 4, esas a 7 más, y en
   semanas nadie sabe por dónde "se entra" a un tema ni qué es canónico.
2. **El vault es también fuente de contexto para agentes.** Si la navegación
   depende de seguir enlaces salientes sin límite, cargar contexto se vuelve
   impredecible en tamaño. La disciplina ya existente de mantener un
   `ROADMAP.md` fuera del `CLAUDE.md` que se carga cada sesión es el mismo
   principio aplicado a un solo archivo; este estándar lo generaliza a todo
   el vault.

La solución: portar la cascada (Nivel 1 monorepo / Nivel 2 proyecto / Nivel 3
módulo) a una **forma de árbol explícita** (patrón MOC — Map of Content) y
hacer que **el metadato, no el enlace, sea lo que se filtra**.

## Regla

### R1 — Forma: árbol, no grafo

- Toda nota, salvo el índice raíz (`00-indice.md`), **DEBE** declarar
  exactamente un `parent` en su frontmatter.
- Una nota **NO DEBE** tener más de un padre. Si un tema parece pertenecer a
  dos dominios, se asigna a donde se usa primero/más; desde el otro dominio se
  cita como "relacionado" (R3), nunca como segundo padre.
- Una MOC **DEBE** listar a todos sus hijos directos en `## Contenido`.
- Una nota hoja **DEBE** abrir con una migaja de pan: `↑ Pertenece a: [...](...)`.
- Profundidad recomendada: raíz → MOC de dominio → hoja (2 saltos). Una sección
  de una MOC **PUEDE** promoverse a sub-MOC propia solo al superar ~7 notas.

### R2 — Tipos de nota

Ocho tipos cerrados:

| `type` | Qué es | ¿Normativo? | ¿`id` estable? |
| --- | --- | --- | --- |
| `moc` | Índice de dominio (Map of Content) | no | no |
| `standard` | Regla DEBE/DEBERÍA/PUEDE vigente | **sí** | sí (`<DOMINIO>-STD-NNN`) |
| `decision` | Decisión de arquitectura narrativa, con alternativas y pendientes | parcial | sí una vez formalizada como ADR |
| `concept` | Conocimiento explicativo/tutorial general | no | no |
| `reference` | Tabla o dato de consulta, no normativo | no | no |
| `glossary` | Índice término → definición de un dominio | no | no |
| `research` | Investigación, abierta o cerrada, con etiquetas [V]/[E]/[C] | no | no |
| `roadmap` | Plan a futuro mutable, no normativo | no | no |

`type` es la fuente de verdad; la carpeta donde vive el archivo es solo
navegación humana — nunca una segunda taxonomía compitiendo con `type`.

### R3 — Enlaces "relacionados" (la única excepción a R1)

- Una nota **PUEDE** declarar hasta **3** enlaces `relacionado` en frontmatter
  hacia notas que no son su padre ni su hijo — cubre tanto pares genuinos
  (p. ej. arquitectura↔observabilidad) como citas incidentales entre dominios
  (p. ej. un roadmap que cita una decisión).
- Cada entrada **DEBE** llevar `razon` (una línea). Sin razón, el enlace es
  inválido — se trata como una excepción de código sin justificar.
- El límite es por nota **emisora**, no por par: si A cita a B no obliga a B a
  citar a A.
- Un *backlink* automático de Obsidian no cuenta contra el presupuesto del
  destino — el límite gobierna enlaces declarados, no backlinks derivados.
- Un 4º enlace necesario es señal de diseño: el contenido compartido **DEBE**
  extraerse a una nota nueva con padre propio.
- Se renderizan también en el cuerpo, al final, bajo `## Relacionado`.

### R4 — Frontmatter obligatorio

```yaml
---
id: null                 # "COSMOS-STD-001" | "PULSAR-STD-001" | null si no aplica
type: standard            # moc | standard | decision | concept | reference | glossary | research | roadmap
project: pulsar           # vault | monorepo | pulsar | crux | <futuro>
parent: "[[moc-pulsar]]"  # wikilink al padre único; null SOLO en 00-indice.md
status: Vigente           # Propuesto | Vigente | Deprecado | Reemplazado por <ID>
alcance: "Proyecto pulsar"
created: 2026-06-30
updated: 2026-06-30
relacionado: []           # lista de {nota, razon}, máx. 3 (R3)
tags: []                  # filtro/búsqueda, NUNCA navegación
---
```

`parent` y `relacionado[].nota` usan wikilink (`[[archivo]]`) — el único lugar
del vault donde se usa esa sintaxis (R6). `id` es obligatorio (no `null`) solo
para `type: standard` y para `decision` formalizada como ADR.

### R5 — Nomenclatura

- `kebab-case`, ASCII, sin espacios, en todo archivo y carpeta.
- El archivo de un `standard` se nombra por **tema**, no por ID; el ID vive en
  frontmatter y es estable aunque el archivo se renombre.
- Toda MOC se llama `moc-<dominio>.md` — permite listar todos los índices con
  un glob (`codex/**/moc-*.md`) sin seguir un solo enlace.
- Plantillas: `plantilla-<tipo>.md` en `00-vault/plantillas/`.

### R6 — Sintaxis de enlaces en el cuerpo

- El cuerpo **DEBE** usar Markdown relativo estándar (`[texto](./ruta.md)`),
  no wikilinks — es lo que GitHub renderiza como clicable y lo que un agente
  que lee el archivo en crudo resuelve sin ambigüedad. Excepción: frontmatter
  (R4).
- Ajuste de vault ya aplicado: "Use [[Wikilinks]]" apagado, "New link format"
  = *Relative path to file* (`.obsidian/app.json`).

### R7 — Crear nota nueva vs. extender una existente

- Nota nueva: el tema **DEBE** tener identidad citable propia (ID, `status`
  independiente) o se prevé que más de un padre distinto lo citará como
  "relacionado".
- Extender: el contenido es elaboración del mismo tema, sin ciclo de vida
  propio.
- Tamaño guía: notas hoja DEBERÍAN caber entre ~50–300 líneas. Más de ~400
  DEBERÍA evaluarse para dividir (caso conocido:
  [`arquitectura-restful.md`](../20-pulsar/arquitectura/arquitectura-restful.md),
  494 líneas, dividir es Fase 2 — ver su `## Estado actual`). El índice raíz
  DEBE caber en ≤ 60 líneas.

### R8 — Cascada de gobernanza

`project: monorepo` = Nivel 1; `project: <proyecto>` = Nivel 2; un override de
Nivel 3 sigue documentándose junto al código, citando el ID que sobrescribe —
el codex no obliga a subir cada excepción de módulo a una nota. Herencia,
especialización, override y default-seguro son las reglas ya vigentes en los
README de estándares previos (absorbidas aquí, no duplicadas por dominio).

## Excepciones

Una nota PUEDE desviarse de R1–R7 solo con justificación documentada en su
propio frontmatter + nota en el cuerpo, y DEBERÍA listarse aquí. Hoy no hay
excepciones registradas.

## Estado actual / brechas

- Vault creado 2026-06-30; migración mecánica de la documentación existente
  (Fase 1) — ver `## Estado actual` de cada MOC de dominio para el detalle.
- `arquitectura-restful.md` (494 líneas) excede la guía de tamaño de R7; se
  migró sin dividir (riesgo bajo). Dividirla en una nota `concept` de REST
  genérico + un nuevo `pulsar-std-002` solo con su §18 normativo es una Fase 2
  deliberadamente diferida, para no mezclar una migración mecánica de bajo
  riesgo con un rediseño de contenido.
- No hay aún ninguna nota `glossary` ni `decision` formalizada como ADR.

## Consecuencias

- **A favor.** Profundidad de navegación acotada; cualquier nota se cita por
  ID o ruta sin entender el grafo completo; un agente carga "la MOC del
  dominio" y nada más para la mayoría de tareas; las reglas son
  mecánicamente verificables.
- **En contra.** Migrar un grafo orgánico a árbol fuerza decisiones de "quién
  es el padre"; el límite de 3 relacionados obliga, a veces, a fusionar o
  promover contenido en vez de solo enlazar.
- **Migración.** Contenido existente migrado en una pasada mecánica (Fase 1);
  mejoras de fondo (split de `arquitectura-restful.md`, IDs nuevos) en una
  Fase 2 separada.
