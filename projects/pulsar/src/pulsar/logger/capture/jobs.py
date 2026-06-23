"""Capture for the job layer: turn a finished :class:`JobResult` into a ``JobLog``.

Called from :func:`pulsar.jobs.core.run_job` (the single choke point through which
the CLI, scheduler and API all run jobs), so every run is captured the same way.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pulsar.logger import JobLog, log
from pulsar.logger.context import current_correlation_id

if TYPE_CHECKING:
    from pulsar.jobs.core import JobResult


def record_job_run(result: JobResult) -> None:
    """Emit a :class:`JobLog` for a finished job run (best-effort)."""
    failed = result.status != "ok"
    log.emit(
        JobLog(
            ts=result.finished_at,
            level="error" if failed else "info",
            correlation_id=current_correlation_id(),
            source="job",
            job=result.job,
            status=result.status,
            started_at=result.started_at,
            finished_at=result.finished_at,
            duration_ms=int(result.duration_s * 1000),
            detail=result.detail,  # small for jobs ("N rows" or the error repr)
            rows=result.rows,
        )
    )
