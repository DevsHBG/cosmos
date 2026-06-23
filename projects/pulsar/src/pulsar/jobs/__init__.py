"""In-house job layer: registry, serialized runner, and the job definitions.

Importing this package registers every job (via :mod:`pulsar.jobs.movements`), so
the registry is populated for the CLI, the scheduler and the API alike.
"""

from __future__ import annotations

from pulsar.jobs import movements as _movements  # noqa: F401  (imported to register jobs)
from pulsar.jobs.core import (
    Job,
    JobContext,
    JobResult,
    all_jobs,
    get,
    last_run,
    register,
    run_job,
)

__all__ = [
    "Job",
    "JobContext",
    "JobResult",
    "all_jobs",
    "get",
    "last_run",
    "register",
    "run_job",
]
