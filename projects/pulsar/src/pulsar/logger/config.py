"""Settings for the logger (paths, flush cadence, sampler, caps).

The operational store lives under ``db/logs/`` — deliberately separate from the
business lakehouse (``lake/``): high-frequency, single-row inserts are OLTP and
must never touch the analytical lake (see ``codex/20-pulsar/roadmap/roadmap-pulsar.md``).
Operational SQLite
stores are grouped under ``db/<domain>/`` (logs here, runs in
``pulsar.jobs.runs``). Every value is overridable via ``PULSAR_LOGS_*`` env vars.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from pulsar.paths import DB_DIR


class LoggerSettings(BaseSettings):
    """Logger settings, loaded from ``PULSAR_LOGS_*`` env vars.

    All fields have defaults, so the store works with zero configuration.
    """

    model_config = SettingsConfigDict(env_prefix="PULSAR_LOGS_", env_file=".env", extra="ignore")

    #: Operational SQLite store (separate from the business lake), under ``db/``
    #: (anchored to the project, see :mod:`pulsar.paths`).
    db_path: Path = DB_DIR / "logs" / "logs.sqlite"
    #: Background worker flush cadence, in seconds.
    flush_interval_s: float = 2.0
    #: Max records written per ``executemany`` batch.
    batch_size: int = 200
    #: Bounded emit queue; once full, new records are dropped (counted), never blocked.
    queue_maxsize: int = 10_000
    #: Resource sampler cadence, in seconds.
    sampler_interval_s: float = 15.0
    #: Cap (bytes) on a captured response/error body (only stored on failure).
    response_cap_bytes: int = 8_192


@lru_cache
def get_logger_settings() -> LoggerSettings:
    """Return cached logger settings loaded from the environment."""
    return LoggerSettings()
