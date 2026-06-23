"""Tests for capture: run_job, the HTTP middleware, and the performance sampler.

All three write to the global ``log`` singleton, which the autouse fixture points
at a temp store. No HANA/lake is touched (the job is a harmless fake).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from fastapi.testclient import TestClient

from pulsar.api.app import create_app
from pulsar.jobs.core import Job, JobContext, run_job
from pulsar.logger import log
from pulsar.logger.capture.resources import PerformanceSampler


@dataclass(frozen=True)
class _Ok(Job):
    name: ClassVar[str] = "_cap-ok"
    description: ClassVar[str] = "fake ok job for capture tests"
    writes_lake: ClassVar[bool] = False

    def run(self, ctx: JobContext) -> int:
        return 7


def test_run_job_emits_job_log() -> None:
    run_job(_Ok())
    log.flush()
    rows = log.query("job_logs", where="job = ?", params=("_cap-ok",))
    assert len(rows) == 1
    assert rows[0]["status"] == "ok"
    assert rows[0]["rows"] == 7
    assert rows[0]["correlation_id"]  # run_job bound a correlation id


def test_http_middleware_emits_api_log() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/health").status_code == 200
        log.flush()
        rows = log.query("api_logs", where="path = ?", params=("/health",))
    assert len(rows) >= 1
    assert rows[0]["method"] == "GET"
    assert rows[0]["status_code"] == 200


def test_performance_sampler_emits_sample() -> None:
    PerformanceSampler(log).sample_once()
    log.flush()
    rows = log.query("performance_logs")
    assert len(rows) >= 1
    assert "rss_mb" in rows[0]
