"""Tests for the FastAPI app (TestClient runs the lifespan → starts the scheduler).

No HANA/lake is touched: read endpoints serve the in-memory registry and the SQLite
log store (isolated per test by the conftest fixture); the trigger test enqueues a
harmless fake job (not the real movement jobs). The surface under test is the v1
RESTful API (``codex/20-pulsar/arquitectura/arquitectura-restful.md`` §18).
"""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime, timedelta
from typing import ClassVar

from fastapi.testclient import TestClient

from pulsar.api.app import create_app
from pulsar.jobs.core import Job, JobContext, register, run_job
from pulsar.logger import JobLog, log

#: Released to let the blocking job (below) finish; keeps a run "active" for the 409 test.
_release = threading.Event()


class _Noop(Job):
    name: ClassVar[str] = "_test-api-noop"
    description: ClassVar[str] = "fake job for the API trigger test"
    writes_lake: ClassVar[bool] = False

    def run(self, ctx: JobContext) -> int:
        return 0


class _Block(Job):
    name: ClassVar[str] = "_test-api-block"
    description: ClassVar[str] = "fake job that blocks until released (for the 409 test)"
    writes_lake: ClassVar[bool] = False

    def run(self, ctx: JobContext) -> int:
        _release.wait(timeout=5.0)
        return 0


# Registered once at import (the registry is process-global, not reset per test).
register(_Noop())
register(_Block())


def _poll_until_terminal(
    client: TestClient, name: str, run_id: str, timeout: float = 5.0
) -> dict[str, object]:
    """Poll a run until it reaches a terminal state; fail if it never does."""
    deadline = time.monotonic() + timeout
    body: dict[str, object] = {}
    while time.monotonic() < deadline:
        body = client.get(f"/v1/jobs/{name}/runs/{run_id}").json()
        if body["status"] in ("ok", "failed"):
            return body
        time.sleep(0.02)
    raise AssertionError(f"run {run_id} did not finish in {timeout}s: {body}")


# -- health (unversioned, operational) -------------------------------------


def test_health() -> None:
    with TestClient(create_app()) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


def test_ready_reports_scheduler_running() -> None:
    with TestClient(create_app()) as client:
        resp = client.get("/health/ready")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"


# -- jobs ------------------------------------------------------------------


def test_list_jobs_includes_the_movement_jobs() -> None:
    with TestClient(create_app()) as client:
        resp = client.get("/v1/jobs")
        assert resp.status_code == 200
        names = {job["name"] for job in resp.json()}
        assert {"sync-movements", "backfill-movements"} <= names


def test_get_unknown_job_returns_problem_404() -> None:
    with TestClient(create_app()) as client:
        resp = client.get("/v1/jobs/does-not-exist")
        assert resp.status_code == 404
        assert resp.headers["content-type"] == "application/problem+json"
        body = resp.json()
        assert body["status"] == 404
        assert body["title"] == "Unknown job"
        assert body["type"].endswith("/unknown-job")
        assert "correlation_id" in body


def test_trigger_unknown_job_returns_problem_404() -> None:
    with TestClient(create_app()) as client:
        resp = client.post("/v1/jobs/does-not-exist/runs")
        assert resp.status_code == 404
        assert resp.headers["content-type"] == "application/problem+json"


def test_create_run_is_accepted_with_location_to_the_run() -> None:
    with TestClient(create_app()) as client:
        resp = client.post("/v1/jobs/_test-api-noop/runs")
        assert resp.status_code == 202
        body = resp.json()
        assert body["job"] == "_test-api-noop"
        assert body["status"] == "queued"
        assert body["id"]
        # Location points at the run resource itself, not the collection.
        assert resp.headers["location"] == f"/v1/jobs/_test-api-noop/runs/{body['id']}"


def test_run_lifecycle_reaches_terminal_via_polling() -> None:
    with TestClient(create_app()) as client:
        resp = client.post("/v1/jobs/_test-api-noop/runs")
        run_id = resp.json()["id"]
        final = _poll_until_terminal(client, "_test-api-noop", run_id)
        assert final["status"] == "ok"
        assert final["id"] == run_id
        assert final["finished_at"] is not None


def test_get_unknown_run_returns_problem_404() -> None:
    with TestClient(create_app()) as client:
        resp = client.get("/v1/jobs/_test-api-noop/runs/does-not-exist")
        assert resp.status_code == 404
        assert resp.headers["content-type"] == "application/problem+json"
        assert resp.json()["type"].endswith("/unknown-run")


def test_triggering_while_active_returns_problem_409() -> None:
    _release.clear()
    with TestClient(create_app()) as client:
        try:
            first = client.post("/v1/jobs/_test-api-block/runs")
            assert first.status_code == 202  # run 1 is queued/running and blocks
            second = client.post("/v1/jobs/_test-api-block/runs")
            assert second.status_code == 409
            assert second.headers["content-type"] == "application/problem+json"
            assert second.json()["type"].endswith("/run-conflict")
        finally:
            _release.set()  # let run 1 finish so shutdown is clean


def test_idempotency_key_replays_the_same_run() -> None:
    headers = {"Idempotency-Key": "abc-123"}
    with TestClient(create_app()) as client:
        first = client.post("/v1/jobs/_test-api-noop/runs", headers=headers)
        second = client.post("/v1/jobs/_test-api-noop/runs", headers=headers)
        assert first.status_code == 202
        assert second.status_code == 202
        assert second.json()["id"] == first.json()["id"]  # replay: same run
        # The retry did not create a second run.
        runs = client.get("/v1/jobs/_test-api-noop/runs").json()["items"]
        assert len(runs) == 1


# -- logs: one polymorphic collection --------------------------------------


def test_logs_filter_by_type_api_returns_request_logs() -> None:
    with TestClient(create_app()) as client:
        client.get("/health")
        log.flush()
        resp = client.get("/v1/logs", params={"type": "api"})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert items and all(item["type"] == "api" for item in items)
        assert "/health" in {item["path"] for item in items}


def test_logs_without_type_is_polymorphic() -> None:
    with TestClient(create_app()) as client:
        client.get("/health")
        log.flush()
        resp = client.get("/v1/logs")
        assert resp.status_code == 200
        kinds = {item["type"] for item in resp.json()["items"]}
        # the request we just made plus a startup performance sample
        assert "api" in kinds
        assert "performance" in kinds


def test_performance_logs_present() -> None:
    with TestClient(create_app()) as client:
        log.flush()  # the sampler takes one sample synchronously on startup
        resp = client.get("/v1/logs", params={"type": "performance"})
        assert resp.status_code == 200
        assert len(resp.json()["items"]) >= 1


def test_runs_history_lists_job_runs() -> None:
    with TestClient(create_app()) as client:
        run_job(_Noop())  # synchronous: creates and finalizes a run in the store
        resp = client.get("/v1/jobs/_test-api-noop/runs")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert items
        assert all(item["job"] == "_test-api-noop" for item in items)
        assert items[0]["status"] == "ok"
        assert "id" in items[0]


def test_runs_cursor_paginates_and_covers_every_run() -> None:
    with TestClient(create_app()) as client:
        for _ in range(3):
            run_job(_Noop())  # three terminal runs, synchronously
        seen: list[str] = []
        cursor: str | None = None
        while True:
            params: dict[str, str | int] = {"limit": 1}
            if cursor:
                params["cursor"] = cursor
            page = client.get("/v1/jobs/_test-api-noop/runs", params=params).json()
            seen.extend(item["id"] for item in page["items"])
            cursor = page["next_cursor"]
            if not cursor:
                break
        assert len(seen) == 3
        assert len(set(seen)) == 3  # no duplicates, no gaps across pages


def test_logs_cursor_paginates_newest_first() -> None:
    base = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    for i in range(3):
        log.emit(JobLog(ts=base + timedelta(minutes=i), job="pager", status="ok"))
    log.flush()
    with TestClient(create_app()) as client:
        page1 = client.get("/v1/logs", params={"type": "job", "job": "pager", "limit": 1}).json()
        assert len(page1["items"]) == 1
        assert page1["next_cursor"]
        page2 = client.get(
            "/v1/logs",
            params={"type": "job", "job": "pager", "limit": 1, "cursor": page1["next_cursor"]},
        ).json()
        assert len(page2["items"]) == 1
        # default sort is -ts → the next page is strictly older
        assert page2["items"][0]["ts"] < page1["items"][0]["ts"]


def test_logs_walking_every_page_covers_all_rows() -> None:
    base = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    for i in range(5):
        log.emit(JobLog(ts=base + timedelta(minutes=i), job="walk", status="ok"))
    log.flush()
    seen: list[str] = []
    with TestClient(create_app()) as client:
        cursor: str | None = None
        while True:
            params: dict[str, str | int] = {"type": "job", "job": "walk", "limit": 2}
            if cursor:
                params["cursor"] = cursor
            page = client.get("/v1/logs", params=params).json()
            seen.extend(item["ts"] for item in page["items"])
            cursor = page["next_cursor"]
            if not cursor:
                break
    assert len(seen) == 5
    assert len(set(seen)) == 5  # no duplicates, no gaps across pages


def test_invalid_cursor_returns_problem_400() -> None:
    with TestClient(create_app()) as client:
        resp = client.get("/v1/logs", params={"cursor": "%%not-a-cursor%%"})
        assert resp.status_code == 400
        assert resp.headers["content-type"] == "application/problem+json"


def test_invalid_sort_returns_problem_400() -> None:
    with TestClient(create_app()) as client:
        resp = client.get("/v1/logs", params={"sort": "name"})
        assert resp.status_code == 400


def test_invalid_type_returns_problem_422() -> None:
    with TestClient(create_app()) as client:
        resp = client.get("/v1/logs", params={"type": "bogus"})
        assert resp.status_code == 422
        assert resp.headers["content-type"] == "application/problem+json"
