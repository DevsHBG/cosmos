"""Tests for the authoritative runs store (``pulsar.jobs.runs``)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from pulsar.jobs.runs import ActiveRunError, RunStore, RunStoreSettings


def _store(tmp_path: Path, **overrides: object) -> RunStore:
    """A fresh store on a temp database (with optional settings overrides)."""
    settings = RunStoreSettings(db_path=tmp_path / "runs.sqlite", **overrides)  # type: ignore[arg-type]
    store = RunStore(settings)
    store.ensure_schema()
    return store


def test_create_returns_queued_run(tmp_path: Path) -> None:
    store = _store(tmp_path)
    run, created = store.create("sync", trigger="api")
    assert created is True
    assert run.status == "queued"
    assert run.trigger == "api"
    assert run.id
    assert store.get("sync", run.id) is not None


def test_lifecycle_transitions_to_terminal(tmp_path: Path) -> None:
    store = _store(tmp_path)
    run, _ = store.create("sync", trigger="cli")
    started = datetime.now(UTC)
    store.mark_running(run.id, started)
    assert store.get("sync", run.id).status == "running"  # type: ignore[union-attr]
    store.finalize(run.id, status="ok", rows=42, detail="42 rows", finished_at=datetime.now(UTC))
    done = store.get("sync", run.id)
    assert done is not None
    assert done.status == "ok"
    assert done.rows == 42
    assert done.started_at is not None and done.finished_at is not None
    assert done.duration_s is not None and done.duration_s >= 0.0


def test_one_active_api_run_per_job(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create("sync", trigger="api")
    with pytest.raises(ActiveRunError):
        store.create("sync", trigger="api")  # second active API run for the same job


def test_direct_runs_are_not_blocked(tmp_path: Path) -> None:
    store = _store(tmp_path)
    a, _ = store.create("sync", trigger="cli")
    b, _ = store.create("sync", trigger="cli")  # direct triggers may overlap
    assert a.id != b.id


def test_has_active_honours_staleness(tmp_path: Path) -> None:
    fresh = _store(tmp_path)
    fresh.create("sync", trigger="api")
    assert fresh.has_active("sync") is True
    # A zero staleness window treats even a just-created run as no longer active.
    stale = RunStore(RunStoreSettings(db_path=tmp_path / "runs.sqlite", stale_after_s=0.0))
    assert stale.has_active("sync") is False


def test_idempotency_key_replays_instead_of_creating(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first, created1 = store.create("sync", trigger="api", idempotency_key="k1")
    second, created2 = store.create("sync", trigger="api", idempotency_key="k1")
    assert created1 is True
    assert created2 is False  # replay
    assert second.id == first.id
    # A different key while one is active still conflicts.
    with pytest.raises(ActiveRunError):
        store.create("sync", trigger="api", idempotency_key="k2")


def test_latest_terminal_returns_most_recent(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first, _ = store.create("sync", trigger="cli")
    store.finalize(first.id, status="ok", rows=1, detail=None, finished_at=datetime.now(UTC))
    second, _ = store.create("sync", trigger="cli")
    store.finalize(second.id, status="failed", rows=0, detail="boom", finished_at=datetime.now(UTC))
    latest = store.latest_terminal("sync")
    assert latest is not None
    assert latest.id == second.id
    assert latest.status == "failed"


def test_list_keyset_covers_all_runs_without_duplicates(tmp_path: Path) -> None:
    store = _store(tmp_path)
    for _ in range(5):
        run, _ = store.create("sync", trigger="cli")
        store.finalize(run.id, status="ok", rows=1, detail=None, finished_at=datetime.now(UTC))
    seen: list[str] = []
    after: tuple[str, int] | None = None
    while True:
        page = store.list("sync", after=after, limit=2)
        if not page:
            break
        seen.extend(run.id for run, _ in page)
        last_run, last_rowid = page[-1]
        after = (last_run.created_at.isoformat(), last_rowid)
        if len(page) < 2:
            break
    assert len(seen) == 5
    assert len(set(seen)) == 5
