"""Tests for the job layer: registry and serialized runner (no HANA / no lake)."""

from __future__ import annotations

import threading
import time
from typing import ClassVar

import pytest
from pydantic import ConfigDict

from pulsar.jobs.core import Job, JobContext, all_jobs, get, last_run, register, run_job
from pulsar.jobs.runs import run_store
from pulsar.logger import log


class _Ok(Job):
    rows: int = 3
    name: ClassVar[str] = "_test-ok"
    description: ClassVar[str] = "fake ok job"
    writes_lake: ClassVar[bool] = False

    def run(self, ctx: JobContext) -> int:
        return self.rows


class _Boom(Job):
    name: ClassVar[str] = "_test-boom"
    description: ClassVar[str] = "fake failing job"
    writes_lake: ClassVar[bool] = False

    def run(self, ctx: JobContext) -> int:
        raise ValueError("kaboom")


class _Reg(Job):
    name: ClassVar[str] = "_test-reg"
    description: ClassVar[str] = "fake registry job"
    writes_lake: ClassVar[bool] = False

    def run(self, ctx: JobContext) -> int:
        return 0


def test_run_job_returns_ok_result_and_records_last_run() -> None:
    result = run_job(_Ok(rows=5))
    assert result.ok
    assert result.rows == 5
    assert result.duration_s >= 0.0
    # last_run is graduated to SQLite: flush, then read it back from the store.
    log.flush()
    recorded = last_run("_test-ok")
    assert recorded is not None
    assert recorded.status == "ok"
    assert recorded.rows == 5


def test_run_job_records_the_run_in_the_store() -> None:
    run_job(_Ok(rows=4))
    run = run_store.latest_terminal("_test-ok")
    assert run is not None
    assert run.status == "ok"
    assert run.rows == 4
    assert run.trigger == "manual"
    assert run.duration_s is not None


def test_run_job_captures_failure_without_raising() -> None:
    result = run_job(_Boom())
    assert not result.ok
    assert result.status == "failed"
    assert "kaboom" in result.detail


def test_register_get_and_all_jobs() -> None:
    job = _Reg()
    register(job)
    assert get("_test-reg") is job
    assert job in all_jobs()
    with pytest.raises(ValueError, match="duplicate"):
        register(_Reg())
    with pytest.raises(KeyError):
        get("_does-not-exist")


class _Concurrency:
    """Mutable concurrency tracker (a lock + counters): a stateful object holding a
    live resource, so a normal class, not a Pydantic model."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.active = 0
        self.peak = 0


class _Tracked(Job):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    state: _Concurrency
    name: ClassVar[str] = "_test-tracked"
    description: ClassVar[str] = "fake write job that tracks concurrency"
    writes_lake: ClassVar[bool] = True

    def run(self, ctx: JobContext) -> int:
        with self.state.lock:
            self.state.active += 1
            self.state.peak = max(self.state.peak, self.state.active)
        time.sleep(0.05)
        with self.state.lock:
            self.state.active -= 1
        return 1


def test_write_jobs_run_one_at_a_time() -> None:
    state = _Concurrency()
    threads = [threading.Thread(target=run_job, args=(_Tracked(state=state),)) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # The process-wide write lock must keep concurrent writers from overlapping.
    assert state.peak == 1
