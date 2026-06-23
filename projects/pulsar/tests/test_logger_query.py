"""Tests for unified query: filters and the DuckDB cross-table connector."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from pulsar.logger.config import LoggerSettings
from pulsar.logger.records import JobLog, PerformanceLog
from pulsar.logger.service import LoggerService


def _seeded(tmp_path: Path) -> tuple[LoggerService, datetime]:
    svc = LoggerService(LoggerSettings(db_path=tmp_path / "q.sqlite"))
    svc.start()
    t0 = datetime(2026, 6, 22, 10, 0, 0, tzinfo=UTC)
    svc.emit(JobLog(ts=t0, job="a", status="ok"))
    svc.emit(JobLog(ts=t0 + timedelta(hours=1), job="b", status="failed"))
    svc.emit(PerformanceLog(ts=t0, rss_mb=100.0))
    svc.flush()
    return svc, t0


def test_query_filters_by_where_and_time(tmp_path: Path) -> None:
    svc, t0 = _seeded(tmp_path)
    try:
        failed = svc.query("job_logs", where="status = ?", params=("failed",))
        assert [row["job"] for row in failed] == ["b"]

        recent = svc.query("job_logs", since=t0 + timedelta(minutes=30))
        assert {row["job"] for row in recent} == {"b"}

        newest_first = svc.query("job_logs", descending=True, limit=1)
        assert newest_first[0]["job"] == "b"
    finally:
        svc.shutdown()


def test_connect_duckdb_reads_all_tables(tmp_path: Path) -> None:
    svc, _ = _seeded(tmp_path)
    try:
        con = svc.connect_duckdb()
        try:
            assert con.execute("SELECT count(*) FROM job_logs").fetchone()[0] == 2
            assert con.execute("SELECT count(*) FROM performance_logs").fetchone()[0] == 1
        finally:
            con.close()
    finally:
        svc.shutdown()
