# pulsar

**Python Utility for Loading, Synthesis, Analysis & Retrieval.**

Proyecto de Python del monorepo [`cosmos`](../../README.md), autocontenido. El
toolchain (tabla abajo) es una **decisión inicial de arquitectura** del proyecto;
se formalizará en un ADR (`docs/adr/`) más adelante.

| Aspecto        | Decisión                                  |
| -------------- | ----------------------------------------- |
| Python         | `>=3.13`                                  |
| Gestor         | [uv](https://docs.astral.sh/uv/)          |
| Lint + formato | [Ruff](https://docs.astral.sh/ruff/)      |
| Type checking  | [mypy](https://mypy.readthedocs.io) (estricto, puerta de CI) |
| Tests          | [pytest](https://docs.pytest.org) + coverage |
| Seguridad      | `pip-audit` + `uv.lock` con hashes        |

## Puesta en marcha

Desde esta carpeta (`projects/pulsar`):

```bash
uv sync                # crea .venv e instala el proyecto + dev tools
```

## Comandos comunes

```bash
uv run ruff check .    # lint
uv run ruff format .   # formato
uv run mypy src        # type check
uv run pytest          # tests
uv run pip-audit       # auditoría de vulnerabilidades
uv add <dep>           # añadir dependencia de runtime
```

## Estructura

```
pulsar/
├── pyproject.toml        # metadatos, dependencias y TODA la config (ruff/mypy/pytest)
├── .python-version       # 3.13
├── uv.lock               # lockfile reproducible
├── src/pulsar/           # código (src-layout)
└── tests/                # tests
```

Documentación (estándares, arquitectura, investigación, roadmap):
[`codex/20-pulsar/moc-pulsar.md`](../../codex/20-pulsar/moc-pulsar.md).
