"""In-house job layer: a registry and a serialized runner.

The lakehouse uses a single-writer SQLite catalog, so every job that writes to it
must run one at a time. :func:`run_job` enforces this with a process-wide lock
(read-only jobs skip it). The layer is invocation-agnostic: the CLI, the
scheduler and (later) the FastAPI server all execute jobs through ``run_job``, so
behaviour is identical no matter who triggers a run.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from pulsar.logger.context import correlation_scope

#: Default lakehouse locations (overridable per run via :class:`JobContext`).
DEFAULT_CATALOG = Path("lake/catalog.sqlite")
DEFAULT_DATA = Path("lake/data")


@dataclass(frozen=True, slots=True)
class JobContext:
    """Shared configuration handed to every job run."""

    catalog_path: Path = DEFAULT_CATALOG
    data_path: Path = DEFAULT_DATA


@dataclass(frozen=True, slots=True)
class JobResult:
    """The outcome of a single job run (kept as the job's last run)."""

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


class Job(ABC):
    """A runnable unit of work. Concrete jobs carry their own parameters."""

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
    """Return the most recent :class:`JobResult` for ``name`` (or ``None``).

    The run history is persisted by the logger (``logs/logs.sqlite``), so this
    reconstructs the last run from the latest :class:`~pulsar.logger.JobLog`.
    Returns ``None`` if the job has never run or the store is unavailable.
    """
    try:
        from pulsar.logger import log

        rows = log.query(
            "job_logs",
            where="job = ?",
            params=(name,),
            order_by="ts",
            descending=True,
            limit=1,
        )
    except Exception:  # best-effort: a read must never break on the logging layer
        return None
    if not rows:
        return None
    row = rows[0]
    return JobResult(
        job=row["job"],
        status=row["status"],
        rows=int(row["rows"]),
        detail=row["detail"] or "",
        started_at=datetime.fromisoformat(row["started_at"]),
        finished_at=datetime.fromisoformat(row["finished_at"]),
    )


def _record(result: JobResult) -> None:
    """Emit a JobLog for a finished run (best-effort: never raises)."""
    try:
        from pulsar.logger.capture.jobs import record_job_run

        record_job_run(result)
    except Exception:  # best-effort: logging must never break a job
        pass


def run_job(
    job: Job, ctx: JobContext | None = None, *, correlation_id: str | None = None
) -> JobResult:
    """Run a job, serializing lakehouse writers and recording the outcome.

    Never raises: a job exception is captured into a ``failed`` :class:`JobResult`
    so every caller (CLI, scheduler, API) gets a structured result either way. The
    run executes inside a correlation scope and its outcome is persisted as a
    ``JobLog`` (the durable, queryable run history).

    Args:
        job: The job to run.
        ctx: Run configuration; defaults to :class:`JobContext` defaults.
        correlation_id: Correlation id to bind (e.g. propagated from an API
            request); a fresh one is generated when ``None``.

    Returns:
        The run's :class:`JobResult`.
    """
    ctx = ctx or JobContext()
    guard = _write_lock if job.writes_lake else nullcontext()
    started = datetime.now(UTC)
    with correlation_scope(correlation_id):
        try:
            with guard:
                rows = job.run(ctx)
            result = JobResult(job.name, "ok", rows, f"{rows} rows", started, datetime.now(UTC))
        except Exception as exc:
            result = JobResult(job.name, "failed", 0, repr(exc), started, datetime.now(UTC))
        _record(result)
    return result
