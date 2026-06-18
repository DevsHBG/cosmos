# ADR-0001: Toolchain de Python de pulsar

- Estado: Aceptado
- Fecha: 2026-06-16

## Contexto

`cosmos` es un monorepo políglota (Python, Node.js, C#, …). Cada proyecto bajo
`projects/*` es **autocontenido**: gestiona sus propias dependencias, su propia
configuración y su propio lockfile. `cosmos` es solo el repositorio git que los
agrupa, sin configuración compartida.

`pulsar` es el proyecto de Python. Este ADR fija su toolchain (válido solo para
pulsar; otros proyectos definen el suyo).

La investigación (junio 2026) se resume en las decisiones siguientes.

## Decisión

### Python `>=3.13`
3.13 es el punto óptimo madurez/compatibilidad: estable, con soporte hasta ~2029
y compatibilidad total de wheels en el ecosistema. 3.14 ya es estable pero algunas
dependencias nativas aún maduran wheels sin beneficio claro para arrancar.

### uv como gestor único
uv es el estándar de facto en 2026 (10-100× más rápido que pip). `uv.lock` y
`pyproject.toml` son estándares PEP, lo que mantiene una salida posible hacia
pip/Poetry. Al ser pulsar independiente, tiene su propio `uv.lock` y `.venv`
dentro de `projects/pulsar`.

**Riesgo asumido:** Astral (uv, Ruff, ty) fue adquirida por OpenAI en marzo 2026,
concentrando la cadena de herramientas en un solo proveedor. Mitigantes: software
open source (Apache/MIT), formatos estándar PEP y portabilidad del lockfile.

### Ruff para lint + formato
Reemplaza Black + Flake8 + isort + pyupgrade en una sola herramienta, configurada
en el `pyproject.toml` de pulsar.

### mypy como puerta de CI (estricto)
mypy es la implementación de referencia, con soporte de plugins (Django,
SQLAlchemy, Pydantic) y alta conformidad con la spec de typing.

**Descartado `ty` (Astral):** ultrarrápido pero en beta (~15% de conformidad,
sin sistema de plugins). Reevaluar cuando alcance estable. Se permite su uso
local como acelerador, pero la puerta de CI es mypy.

### pytest + coverage; seguridad con pip-audit
pytest es el estándar de tests. La seguridad de la cadena de suministro se basa
en `uv.lock` con hashes, `pip-audit` en cada build de CI y (a futuro) SBOM
CycloneDX + Dependabot.

## Consecuencias

- Toda la config de pulsar vive en `projects/pulsar/pyproject.toml`.
- `cosmos` no contiene configuración de Python; otros proyectos son autónomos.
- Reevaluar `ty` y la versión de Python en cada ciclo de release relevante.
- Cambiar cualquiera de estas decisiones requiere un nuevo ADR.
