"""Tests for the logger core: records, sink, service (own temp store)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pulsar.logger.config import LoggerSettings
from pulsar.logger.context import correlation_scope, current_correlation_id
from pulsar.logger.records import JobLog, LogRecord, PerformanceLog
from pulsar.logger.service import LoggerService
from pulsar.logger.sinks import Sink


def _service(tmp_path: Path, name: str = "core.sqlite", **overrides: object) -> LoggerService:
    """A LoggerService on its own temp DB (separate from the autouse singleton)."""
    return LoggerService(LoggerSettings(db_path=tmp_path / name, **overrides))  # type: ignore[arg-type]


def _job(job: str, **kw: object) -> JobLog:
    return JobLog(ts=datetime.now(UTC), job=job, status="ok", **kw)  # type: ignore[arg-type]


def test_emit_flush_query_roundtrip(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    svc.start()
    try:
        svc.emit(_job("job-a", duration_ms=5, rows=3))
        svc.flush()
        rows = svc.query("job_logs")
    finally:
        svc.shutdown()
    assert len(rows) == 1
    assert rows[0]["job"] == "job-a"
    assert rows[0]["status"] == "ok"
    assert rows[0]["rows"] == 3
    # datetimes are stored as ISO-8601 text.
    assert rows[0]["ts"].startswith(str(datetime.now(UTC).year))


def test_shutdown_flushes_queued_records(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    svc.start()
    svc.emit(_job("job-b"))
    svc.shutdown()  # must drain the queue on the way out
    assert len(svc.query("job_logs")) == 1


def test_start_is_idempotent(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    svc.start()
    try:
        assert svc.start() is False  # already running: no-op, schema unaffected
        svc.emit(_job("job-c"))
        svc.flush()
        assert len(svc.query("job_logs")) == 1
    finally:
        svc.shutdown()


def test_query_unknown_kind_raises(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    svc.start()
    try:
        with pytest.raises(KeyError):
            svc.query("does_not_exist")
    finally:
        svc.shutdown()


def test_query_returns_empty_before_any_write(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    svc.start()
    try:
        assert svc.query("job_logs") == []
        assert svc.query("api_logs") == []
        assert svc.query("performance_logs") == []
    finally:
        svc.shutdown()


def test_backpressure_drops_when_queue_full(tmp_path: Path) -> None:
    svc = _service(tmp_path, queue_maxsize=2)  # worker not started: queue fills
    for i in range(5):
        svc.emit(_job(f"j{i}"))
    assert svc.dropped == 3


def test_logging_is_best_effort_on_sink_failure(tmp_path: Path) -> None:
    class _BoomSink(Sink):
        def ensure_schema(self) -> None:
            return None

        def write(self, records: Sequence[LogRecord]) -> None:
            raise RuntimeError("boom")

    svc = _service(tmp_path)
    svc.register(JobLog, _BoomSink())  # default sink replaced by a failing one
    svc.start()
    try:
        svc.emit(_job("job-d"))
        svc.flush()  # the sink raises internally; flush must swallow it
    finally:
        svc.shutdown()


def test_correlation_scope_binds_and_resets() -> None:
    assert current_correlation_id() is None
    with correlation_scope("abc") as cid:
        assert cid == "abc"
        assert current_correlation_id() == "abc"
        with correlation_scope() as nested:
            assert nested != "abc"
            assert current_correlation_id() == nested
        assert current_correlation_id() == "abc"
    assert current_correlation_id() is None


def test_performance_log_columns_are_numeric(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    svc.start()
    try:
        svc.emit(PerformanceLog(ts=datetime.now(UTC), cpu_pct=12.5, rss_mb=100.0))
        svc.flush()
        rows = svc.query("performance_logs")
    finally:
        svc.shutdown()
    assert len(rows) == 1
    assert rows[0]["cpu_pct"] == 12.5
    assert rows[0]["rss_mb"] == 100.0
