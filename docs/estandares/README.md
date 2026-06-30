# Estándares de cosmos (Nivel 1 · monorepo)

> **Estándar normativo a nivel de monorepo.** Este directorio es la **cima** de la
> cascada de estándares de la suite: las reglas transversales que **todo** proyecto
> de `cosmos` hereda (git, CI/CD, seguridad transversal, toolchain por lenguaje…).
> Cada estándar vive en su propio archivo; este README es el **marco** que los
> gobierna y su índice.
>
> Convención de palabras clave (estilo RFC 2119): **DEBE** = obligatorio,
> **DEBERÍA** = recomendado salvo buena razón documentada, **PUEDE** = opcional.

## Principio rector: coherencia

Antes que cualquier regla concreta, la suite optimiza por **coherencia**: para cada
preocupación transversal (gestionar dependencias, versionar, commitear, construir en
CI…) **DEBE** existir **una sola forma idiomática**, y todos los proyectos la siguen.
La consistencia del monorepo gana a la preferencia local de un proyecto, **salvo
justificación medida y documentada** (no por gusto ni por costumbre).

Esto importa porque `cosmos` es **políglota y crecerá sin control**: cada divergencia
"inocente" (un proyecto con su propio gestor de paquetes, su propio flujo) multiplica
el costo de onboarding, CI, revisión y mantenimiento a lo largo de toda la suite. Un
estándar no existe para limitar, sino para que *no haya que decidir lo mismo dos
veces*: se decide una vez, se escribe aquí, y deja de ser tema.

## Modelo de gobernanza: 3 niveles en cascada

Las reglas se organizan en tres niveles. Cada nivel **hereda** del superior y solo
**especializa** lo que necesita. De más general a más específico:

| Nivel | Alcance | Vive en | ID | Estado |
| ----- | ------- | ------- | -- | ------ |
| **1 · Monorepo** | Todo `cosmos`: git, commits, flujo de equipo, CI/CD, Docker, seguridad transversal, **toolchain por lenguaje** | **este directorio** (`<raíz>/docs/estandares/`) | `COSMOS-STD-NNN` | **activo** |
| **2 · Proyecto** | Un proyecto concreto (`pulsar`, `crux`, …): patrones, arquitectura, convenciones de código | `projects/<proyecto>/docs/estandares/` | `<PROYECTO>-STD-NNN` | activo (pulsar) |
| **3 · Módulo / servicio** | Un paquete concreto, cuando —y solo cuando— necesita desviarse | Junto al código del módulo | `<PROYECTO>-<MÓDULO>-STD-NNN` | a demanda |

### Cómo funciona la cascada

- **Herencia.** Un proyecto hereda todos los estándares del monorepo; un módulo,
  todos los del proyecto. Lo que no se redefine, aplica tal cual. No se repite una
  regla heredada: se referencia.
- **Especialización (override).** Un nivel inferior **PUEDE** sobrescribir una regla
  del superior, pero solo con **justificación explícita**: una razón técnica concreta
  (límite de una librería, restricción de interoperabilidad, rendimiento medido), no
  preferencia de estilo. "Me gusta más" no es justificación.
- **Dónde se documenta un override.** La excepción se documenta **junto al código que
  la usa** (nivel 3), citando el ID del estándar que sobrescribe y la razón. El
  estándar superior **DEBERÍA** listar las excepciones conocidas para que sean
  descubribles desde arriba.
- **Default seguro.** Ante la duda, se sigue la regla del nivel superior. La carga de
  la prueba recae en quien quiere desviarse, no en quien cumple.

## Relación con el resto de la documentación

- **Estándares** (este directorio) — reglas **vivas**: lo que todo proyecto DEBE hacer
  *ahora*. Se actualizan cuando la regla cambia.
- **ADRs** (`docs/adr/`, *pendientes*) — el **registro de decisiones**: por qué se
  eligió algo, en una fecha, inmutable. Un estándar puede nacer de un ADR y citarlo.
- **Otros docs transversales** — p. ej.
  [`../identidad-y-autorizacion.md`](../identidad-y-autorizacion.md) (arquitectura de
  authn/authz de la suite): conviven con este directorio; la diferencia es de alcance,
  no de autoridad. **PUEDEN** integrarse aquí o quedar referenciados.
- **`CLAUDE.md`** (raíz, *pendiente*) — guía operativa para agentes; apuntará a estos
  estándares, no los duplicará.

## Cómo proponer, añadir o cambiar un estándar

1. **Un estándar = un archivo** en este directorio, en `kebab-case` y por **tema**
   (`gestor-de-paquetes.md`), no por número.
2. **Estructura mínima**: cabecera con `ID`, `Estado`, `Alcance`, `Resumen`; luego
   *Contexto*, *Regla* (con DEBE/DEBERÍA/PUEDE), *Excepciones*, *Estado actual /
   brechas* y *Consecuencias*.
3. **Estados**: `Propuesto` → `Vigente` → `Deprecado` / `Reemplazado por <ID>`.
4. **IDs estables.** El ID (`COSMOS-STD-NNN`) no cambia aunque se renombre el archivo;
   sirve para citarlo desde el código, los commits y otros documentos.
5. **Registrarlo** en el índice de abajo.

## Índice de estándares vigentes

| ID | Tema | Estado | Archivo |
| -- | ---- | ------ | ------- |
| `COSMOS-STD-001` | Gestor de paquetes y toolchain por lenguaje (pnpm para Node/JS/TS, uv para Python) | Vigente | [`gestor-de-paquetes.md`](./gestor-de-paquetes.md) |
