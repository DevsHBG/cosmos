"""Shared test fixtures.

The logger is a process-wide singleton. This autouse fixture points it at a fresh
temp store per test and owns its lifecycle, so capture (run_job, the HTTP
middleware, the sampler) writes somewhere isolated — never the real
``logs/logs.sqlite`` — and each test starts from an empty store.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

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
