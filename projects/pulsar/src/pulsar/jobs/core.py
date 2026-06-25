"""In-house job layer: a registry and a serialized runner.

The lakehouse uses a single-writer SQLite catalog, so every job that writes to it
must run one at a time. :func:`run_job` enforces this with a process-wide lock
(read-only jobs skip it). The layer is invocation-agnostic: the CLI, the
scheduler and the FastAPI server all execute jobs through ``run_job``, so
behaviour is identical no matter who triggers a run.

Every run is recorded in the authoritative runs store (:mod:`pulsar.jobs.runs`):
``run_job`` creates it (unless the API pre-created it at enqueue and passed a
``run_id``), transitions it ``queued → running`` once it holds the write-lock, and
``finalize``\\ s it to ``ok``/``failed``. Store writes are best-effort here so a
storage hiccup never breaks the run itself; the ``JobLog`` emission is unchanged.
"""

from __future__ import annotations

import sys
import threading
import uuid
from abc import ABC, abstractmethod
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from pulsar.jobs.runs import run_store
from pulsar.logger.context import correlation_scope
from pulsar.paths import LAKE_DIR

#: Default lakehouse locations (overridable per run via :class:`JobContext`).
#: Anchored to the project (see :mod:`pulsar.paths`), not the CWD.
DEFAULT_CATALOG = LAKE_DIR / "catalog.sqlite"
DEFAULT_DATA = LAKE_DIR / "data"


class JobContext(BaseModel):
    """Shared configuration handed to every job run."""

    model_config = ConfigDict(frozen=True)

    catalog_path: Path = DEFAULT_CATALOG
    data_path: Path = DEFAULT_DATA


class JobResult(BaseModel):
    """The outcome of a single job run (kept as the job's last run)."""

    model_config = ConfigDict(frozen=True)

    job: str
    status: str  # "ok" | "failed"
    rows: int
    detail: str
    started_at: datetime
    finished_at: datetime

    @property
    def ok(self) -> bool:
        """Whether the run succeeded."""
        return self.status == "ok"

    @property
    def duration_s(self) -> float:
        """Wall-clock duration of the run, in seconds."""
        return (self.finished_at - self.started_at).total_seconds()


class Job(BaseModel, ABC):
    """A runnable unit of work. Concrete jobs carry their own parameters."""

    model_config = ConfigDict(frozen=True)

    #: Unique registry name (e.g. ``"sync-movements"``).
    name: ClassVar[str]
    #: One-line human description, surfaced by ``list`` and the API.
    description: ClassVar[str]
    #: Whether the job writes to the lakehouse (and so needs the write lock).
    writes_lake: ClassVar[bool]

    @abstractmethod
    def run(self, ctx: JobContext) -> int:
        """Execute the job and return a rows/affected count for the result."""


_registry: dict[str, Job] = {}
#: Process-wide lock serializing every lakehouse writer (DuckLake = single writer).
_write_lock = threading.Lock()


def register(job: Job) -> Job:
    """Register a job under its name; raise ``ValueError`` on a duplicate name."""
    if job.name in _registry:
        raise ValueError(f"duplicate job name: {job.name!r}")
    _registry[job.name] = job
    return job


def get(name: str) -> Job:
    """Return the registered job named ``name``; raise ``KeyError`` if absent."""
    if name not in _registry:
        raise KeyError(f"unknown job: {name!r}; registered: {sorted(_registry)}")
    return _registry[name]


def all_jobs() -> list[Job]:
    """Return every registered job, sorted by name."""
    return [_registry[name] for name in sorted(_registry)]


def last_run(name: str) -> JobResult | None:
    """Return the most recent finished :class:`JobResult` for ``name`` (or ``None``).

    Run state is authoritative in the runs store (:mod:`pulsar.jobs.runs`), so this
    returns the latest terminal (``ok``/``failed``) run there. Returns ``None`` if
    the job has never finished a run or the store is unavailable.
    """
    try:
        run = run_store.latest_terminal(name)
    except Exception:  # best-effort: a read must never break on the store layer
        return None
    if run is None:
        return None
    started = run.started_at or run.created_at
    return JobResult(
        job=run.job,
        status=run.status,
        rows=run.rows,
        detail=run.detail or "",
        started_at=started,
        finished_at=run.finished_at or started,
    )


def _record(result: JobResult) -> None:
    """Emit a JobLog for a finished run (best-effort: never raises)."""
    try:
        from pulsar.logger.capture.jobs import record_job_run

        record_job_run(result)
    except Exception:  # best-effort: logging must never break a job
        pass


def _create_run(job_name: str, *, trigger: str, correlation_id: str | None) -> str:
    """Create a ``queued`` run and return its id (best-effort; a local id on failure)."""
    try:
        run, _ = run_store.create(job_name, trigger=trigger, correlation_id=correlation_id)
        return run.id
    except Exception as exc:  # best-effort: a store hiccup must never break the run
        print(f"[runs] create failed: {exc!r}", file=sys.stderr)
        return uuid.uuid4().hex


def _mark_running(run_id: str, started_at: datetime) -> None:
    """Transition the run to ``running`` (best-effort)."""
    try:
        run_store.mark_running(run_id, started_at)
    except Exception as exc:  # best-effort
        print(f"[runs] mark_running failed: {exc!r}", file=sys.stderr)


def _finalize_run(run_id: str, result: JobResult) -> None:
    """Transition the run to its terminal state (best-effort)."""
    try:
        run_store.finalize(
            run_id,
            status=result.status,
            rows=result.rows,
            detail=result.detail,
            finished_at=result.finished_at,
        )
    except Exception as exc:  # best-effort
        print(f"[runs] finalize failed: {exc!r}", file=sys.stderr)


def run_job(
    job: Job,
    ctx: JobContext | None = None,
    *,
    correlation_id: str | None = None,
    run_id: str | None = None,
    trigger: str = "manual",
) -> JobResult:
    """Run a job, serializing lakehouse writers and recording its lifecycle.

    Never raises: a job exception is captured into a ``failed`` :class:`JobResult`
    so every caller (CLI, scheduler, API) gets a structured result either way. The
    run executes inside a correlation scope; its lifecycle (``queued → running →
    ok/failed``) is persisted in the runs store and its outcome is also emitted as a
    ``JobLog`` (the cross-cutting observability event).

    Args:
        job: The job to run.
        ctx: Run configuration; defaults to :class:`JobContext` defaults.
        correlation_id: Correlation id to bind (e.g. propagated from an API
            request); a fresh one is generated when ``None``.
        run_id: Id of a run already created in the store (the API pre-creates it at
            enqueue to return a ``Location``); when ``None``, ``run_job`` creates one.
        trigger: How this run was triggered (``scheduled``/``cli``/``manual``); used
            only when creating the run here (ignored when ``run_id`` is given).

    Returns:
        The run's :class:`JobResult`.
    """
    ctx = ctx or JobContext()
    guard = _write_lock if job.writes_lake else nullcontext()
    with correlation_scope(correlation_id) as cid:
        if run_id is None:
            run_id = _create_run(job.name, trigger=trigger, correlation_id=cid)
        started = datetime.now(UTC)  # provisional; refined to the post-lock start below
        try:
            with guard:
                started = datetime.now(UTC)  # actual execution start (after the write-lock)
                _mark_running(run_id, started)
                rows = job.run(ctx)
            result = JobResult(
                job=job.name,
                status="ok",
                rows=rows,
                detail=f"{rows} rows",
                started_at=started,
                finished_at=datetime.now(UTC),
            )
        except Exception as exc:
            result = JobResult(
                job=job.name,
                status="failed",
                rows=0,
                detail=repr(exc),
                started_at=started,
                finished_at=datetime.now(UTC),
            )
        _finalize_run(run_id, result)
        _record(result)
    return result
