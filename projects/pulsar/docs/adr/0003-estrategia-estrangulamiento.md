# ADR-0003: Estrategia de estrangulamiento del monolito viejo

- Estado: Aceptado
- Fecha: 2026-06-18
- Relacionado: [ADR-0002](0002-ledger-unificado-multiempresa.md), [inventario de salvamento](../salvage-inventory.md)

## Contexto

Existe un sistema anterior en producción, `hbg-analytics-service`: un monolito Flask
de ~112 archivos Python que da valor hoy (reabasto, distribución, márgenes,
reportes, ABC/XYZ) pero está construido sobre el modelo de datos roto que corrige el
[ADR-0002](0002-ledger-unificado-multiempresa.md).

El inventario de salvamento (lectura completa del repo) arrojó dos hechos clave:

1. La lógica analítica cara —**el motor de reabasto periódico (R,S), safety stock,
   ABC/XYZ, calendario retail, semáforos de quiebre**— está **bien hecha y poco
   acoplada** al bug. El bug está contenido en la query de ventas y en `realtime_api`.
2. Hay ~3,500+ LOC de utilidades de calidad y cero acoplamiento (charts, plantillas,
   PDF, Excel, cliente Anthropic, calendario retail, temporadas).

Se evaluaron tres caminos:

- **Refactor in-place del monolito** — descartado: cirugía sobre `server.py` de
  102 KB con credenciales hardcodeadas, arrastrando la estructura monolítica que no
  sirve para un equipo de 5+.
- **Rewrite total desde cero** — descartado: tira lógica que funciona y da valor hoy;
  meses de trabajo y regresiones; el negocio no puede perder features.
- **Estrangulamiento (strangler fig)** — elegido.

## Decisión

### 1. `pulsar` es la fundación nueva; el monolito sigue en producción
Se construye la base correcta (ledger + facts del ADR-0002) en `pulsar`. El sistema
viejo **sigue corriendo y sirviendo al negocio** mientras se migra capacidad por
capacidad. Nada del viejo se apaga hasta que su reemplazo en `pulsar` esté validado.

### 2. Migrar = portar lógica + recablear datos
La mayor parte del trabajo es **portar analítica buena sobre la fundación
corregida**, no reescribir lógica. "PORT" implica mover el código (sólido) y
**recablear su entrada** a los facts derivados del ledger; la lógica se conserva, el
contrato de datos cambia. Clasificación PORT/ADAPT/DROP por archivo en el
[inventario de salvamento](../salvage-inventory.md).

### 3. Secuencia por fases con checkpoints humanos
1. **Fundación** — ledger OINM 3-esquemas → `fact_inventario_diario` +
   `fact_demanda_diaria` + dimensiones curadas. Cierra los huecos de detección de
   quiebre y de ledger incompleto.
2. **Clasificación** — portar ABC/XYZ sobre los facts nuevos (define "ganadores").
3. **Motor anti-quiebres (objetivo v1)** — portar `inventory_replenishment`,
   `min_max`, semáforos; recablear al ledger.
4. **Presentación + orquestación** — charts/Excel/PDF + scheduler diario.
5. **Después** — censado formal de demanda (sobre la base de "días limpios" que ya
   existe en `margin_regimes`), márgenes, agente LLM.

Cada fase se valida contra el sistema viejo antes de retirar la pieza equivalente.

### 4. No "super-prompt" de agentes para la migración
La migración **no es trabajo mecánico paralelizable**: requiere diseño y validación
humana (sutilezas de demanda censurada, calidad de dato, correctitud point-in-time).
Disparar agentes a ciegas produciría migraciones plausibles pero incorrectas. Los
agentes se usan en tareas acotadas **dentro** de cada fase (portar un módulo puro,
generar tests), no como estrategia.

### 5. Prerrequisito de seguridad
Las credenciales hardcodeadas del sistema viejo (`hana.py`, `supabase_client.py`) no
se replican. `pulsar` usa gestión de secretos desde el día uno. La fuga existente en
el repo viejo se trata como incidente aparte (rotación de credenciales).

## Consecuencias

- El negocio no pierde funcionalidad durante la migración (el viejo sigue vivo).
- El primer entregable de `pulsar` arregla el bug central del viejo y a la vez es la
  base del nuevo: no hay trabajo desperdiciado.
- El monolito se apaga de forma incremental, módulo por módulo validado, no en un
  big-bang.
- El alcance de v1 queda acotado a quiebres de productos ganadores; pricing y agente
  LLM se difieren explícitamente.
- Cambiar esta estrategia requiere un nuevo ADR.
