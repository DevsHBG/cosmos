"""Reusable logger service: structured logs to a queryable SQLite store.

Import the singleton and emit from anywhere::

    from pulsar.logger import log, JobLog

    log.emit(JobLog(ts=ts, job="sync-movements", status="ok", rows=42))

Emitting is non-blocking and best-effort. ``log.start()``/``log.shutdown()`` are
wired into the API ``lifespan`` (and the scheduler/CLI for one-shot runs). Read it
back with ``log.query(...)`` or ``log.connect_duckdb()`` for cross-table SQL.
"""

from __future__ import annotations

from pulsar.logger.records import ActivityLog, ApiLog, JobLog, LogRecord, PerformanceLog
from pulsar.logger.service import LoggerService

#: Process-wide logger singleton (configured with environment defaults).
log = LoggerService()

__all__ = [
    "ActivityLog",
    "ApiLog",
    "JobLog",
    "LogRecord",
    "LoggerService",
    "PerformanceLog",
    "log",
]
