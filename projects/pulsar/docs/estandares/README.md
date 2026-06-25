# Estándares de Pulsar

> **Estándar normativo** a nivel de proyecto. Este directorio es la fuente de
> verdad de las reglas que el código de Pulsar **DEBE** seguir: patrones,
> arquitectura, idioma de las herramientas, convenciones transversales. Cada
> estándar vive en su propio archivo; este README es el **marco** que los
> gobierna (cómo se heredan, cómo se especializan, cómo se proponen) y su índice.
>
> Convención de palabras clave (estilo RFC 2119, igual que
> [`../arquitectura-restful.md`](../arquitectura-restful.md)): **DEBE** =
> obligatorio, **DEBERÍA** = recomendado salvo buena razón documentada, **PUEDE**
> = opcional.

## Principio rector: coherencia

Antes que cualquier regla concreta, Pulsar optimiza por **coherencia**: para cada
preocupación (modelar datos, manejar errores, nombrar, configurar, loggear,
testear…) **DEBE** existir **una sola forma idiomática** y todo el código la
sigue. La consistencia de un proyecto gana a la optimización local de un archivo,
**salvo justificación medida y documentada** (no por gusto ni por costumbre de
quien escribe).

Esto importa porque el monorepo crecerá sin control: cada divergencia "inocente"
(un módulo con su propio estilo) multiplica el costo cognitivo de leer, revisar y
mantener. Un estándar no existe para limitar, sino para que *no haya que decidir
lo mismo dos veces*: se decide una vez, se escribe aquí, y deja de ser tema.

Los estándares de este directorio son **aplicaciones** de este principio. El
primero (modelado de datos) elige Pydantic como forma única; los siguientes harán
lo propio con otras preocupaciones.

## Modelo de gobernanza: 3 niveles en cascada

Las reglas se organizan en tres niveles. Cada nivel **hereda** del superior y solo
**especializa** lo que necesita. De más general a más específico:

| Nivel | Alcance | Vive en | ID | Estado |
| ----- | ------- | ------- | -- | ------ |
| **1 · Monorepo** | Todo `cosmos`: git, commits, flujo de equipo, CI/CD, Docker, seguridad transversal, lenguajes permitidos | *(por definir — `<raíz>/docs/estandares/`)* | `COSMOS-STD-NNN` | pendiente |
| **2 · Proyecto** | Todo `pulsar`: patrones, arquitectura, idioma de herramientas, convenciones de código | **este directorio** (`projects/pulsar/docs/estandares/`) | `PULSAR-STD-NNN` | activo |
| **3 · Módulo / servicio** | Un paquete concreto (`pulsar/jobs`, `pulsar/logger`, …) cuando, y solo cuando, necesita desviarse | Junto al código del módulo (docstring del paquete o nota breve en su doc) | `PULSAR-<MÓDULO>-STD-NNN` | a demanda |

> El nivel 1 (monorepo) se escribirá sobre la marcha; hoy solo existe el nivel 2.
> El nivel 3 es **opcional y excepcional**: solo se crea cuando un módulo tiene una
> razón real para no seguir la regla del proyecto.

### Cómo funciona la cascada

- **Herencia.** Un proyecto hereda todos los estándares del monorepo; un módulo,
  todos los del proyecto. Lo que no se redefine, aplica tal cual. No se repite una
  regla heredada: se referencia.
- **Especialización (override).** Un nivel inferior **PUEDE** sobrescribir una
  regla del superior, pero solo con una **justificación explícita**: una razón
  técnica concreta (rendimiento medido, restricción de interoperabilidad, límite de
  una librería), no preferencia de estilo. "Me gusta más" no es justificación.
- **Dónde se documenta un override.** La excepción se documenta **junto al código
  que la usa** (nivel 3): en el docstring del paquete o en una nota breve, citando
  el ID del estándar que sobrescribe y la razón. El estándar del proyecto **DEBERÍA**
  listar las excepciones conocidas para que sean descubribles desde arriba.
- **Default seguro.** Ante la duda, se sigue la regla del nivel superior. La carga
  de la prueba recae en quien quiere desviarse, no en quien cumple.

## Relación con el resto de la documentación

Cada documento tiene un papel distinto; no se solapan:

- **Estándares** (este directorio) — reglas **vivas**: lo que el código DEBE hacer
  *ahora*. Se actualizan cuando la regla cambia.
- **ADRs** (`docs/adr/`, según el README raíz) — el **registro de decisiones**:
  por qué se eligió algo, en una fecha, inmutable. Un estándar puede nacer de un
  ADR y citarlo; el ADR no se reescribe, el estándar sí evoluciona.
- **`CLAUDE.md`** — guía operativa para agentes: el *qué hay* del proyecto, cargado
  cada sesión. Apunta a estos estándares; no los duplica.
- **`docs/arquitectura-restful.md`**, **`docs/observability.md`** — estándares de
  un dominio concreto (la API, la observabilidad). Conviven con este directorio; la
  diferencia es de alcance, no de autoridad. Con el tiempo **PUEDEN** integrarse
  aquí o seguir referenciados desde el índice.
- **`ROADMAP.md`** — lo que **vendrá**, no lo que rige hoy.

## Cómo proponer, añadir o cambiar un estándar

1. **Un estándar = un archivo** en este directorio, en `kebab-case` y por **tema**
   (`modelado-de-datos.md`), no por número (el número es un ID interno, no el
   nombre). Esto lo hace descubrible.
2. **Estructura mínima** de cada archivo (ver `modelado-de-datos.md` como
   plantilla viva): cabecera con `ID`, `Estado`, `Alcance` y `Resumen`; luego
   *Contexto*, *Regla* (con DEBE/DEBERÍA/PUEDE), *Excepciones*, *Estado actual /
   brechas* y *Consecuencias*.
3. **Estados** de un estándar: `Propuesto` → `Vigente` → `Deprecado` /
   `Reemplazado por <ID>`. Un estándar vigente es de cumplimiento obligatorio.
4. **IDs estables.** El ID (`PULSAR-STD-NNN`) no cambia aunque se renombre el
   archivo; sirve para citarlo desde el código, los commits y otros documentos.
5. **Registrarlo** en el índice de abajo.

## Índice de estándares vigentes

| ID | Tema | Estado | Archivo |
| -- | ---- | ------ | ------- |
| `PULSAR-STD-001` | Modelado de datos y coherencia de tipos (Pydantic por defecto) | Vigente | [`modelado-de-datos.md`](./modelado-de-datos.md) |
