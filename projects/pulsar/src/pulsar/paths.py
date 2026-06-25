"""Filesystem anchors for the project's local data stores.

Every on-disk store —the business lakehouse under ``lake/`` and the operational
SQLite stores under ``db/``— defaults to a location **inside the project**, anchored
to :data:`PROJECT_ROOT` rather than the current working directory. This keeps the
data where it is used (``projects/pulsar/``) no matter where a command is launched
from; relying on the CWD used to scatter an empty ``db/`` at the monorepo root when
a process was started from there.

Every path stays overridable: the lake via :class:`~pulsar.jobs.core.JobContext`
and the CLI (``--catalog``/``--data``), the operational stores via their
``PULSAR_*`` env vars.
"""

from __future__ import annotations

from pathlib import Path

#: Project root (``projects/pulsar/``). Derived from this module's location
#: (``src/pulsar/paths.py`` → ``parents[2]``), so it is independent of the CWD.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: Business lakehouse: DuckLake catalog + Parquet data (gitignored).
LAKE_DIR = PROJECT_ROOT / "lake"

#: Operational SQLite stores (logs, runs), kept apart from the lake (gitignored).
DB_DIR = PROJECT_ROOT / "db"
