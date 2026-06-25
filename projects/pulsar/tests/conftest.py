"""Shared test fixtures.

The logger and the runs store are process-wide singletons. These autouse fixtures
point each at a fresh temp database per test, so capture (run_job, the HTTP
middleware, the sampler) and run state write somewhere isolated — never the real
``db/logs/logs.sqlite`` / ``db/runs/runs.sqlite`` — and each test starts empty.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from pulsar.jobs.runs import RunStoreSettings, run_store
from pulsar.logger import log
from pulsar.logger.config import LoggerSettings


@pytest.fixture(autouse=True)
def isolate_logger(tmp_path: Path) -> Iterator[None]:
    """Bind the global logger to a per-test temp store; start and stop it."""
    log.shutdown()  # ensure stopped before reconfiguring (idempotent)
    log.configure(LoggerSettings(db_path=tmp_path / "logs.sqlite"))
    log.start()
    try:
        yield
    finally:
        log.shutdown()


@pytest.fixture(autouse=True)
def isolate_runs(tmp_path: Path) -> None:
    """Bind the global runs store to a per-test temp database (synchronous, no worker)."""
    run_store.configure(RunStoreSettings(db_path=tmp_path / "runs.sqlite"))
    run_store.ensure_schema()
