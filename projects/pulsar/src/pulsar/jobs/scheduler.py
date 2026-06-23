"""In-process scheduler: fires registered jobs on a code-declared cron schedule.

Uses APScheduler's ``BackgroundScheduler`` so jobs run in a thread pool (never on
the event loop), which lets the same scheduler run standalone today and be hosted
in the FastAPI ``lifespan`` later. Every fire goes through
:func:`pulsar.jobs.core.run_job`, so the lakehouse write-lock and run recording
apply exactly as for a manual run.

The schedule lives in code (:data:`SCHEDULE`) — no external cron, no Windows Task
Scheduler. Cron times are interpreted in the server's local timezone.

Run standalone:
    python -m pulsar.jobs.scheduler
"""

from __future__ import annotations

import sys
import threading
from dataclasses import dataclass

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from pulsar.jobs.core import JobContext, get, run_job
from pulsar.logger import log
from pulsar.logger.capture.resources import PerformanceSampler
from pulsar.logger.context import current_correlation_id

#: Defaults applied to every scheduled job.
_JOB_DEFAULTS = {
    "coalesce": True,  # if several fires were missed (downtime), run once, not N times
    "max_instances": 1,  # never overlap a job with itself
    "misfire_grace_time": 3600,  # still run if fired up to 1h late (e.g. slow startup)
}


@dataclass(frozen=True)
class ScheduledJob:
    """A registered job bound to a cron trigger (declared in :data:`SCHEDULE`)."""

    job_name: str
    trigger: CronTrigger
    description: str


#: The schedule, declared in code. First daily job: the 00:00 incremental sync,
#: which captures the previous day's movements (it resumes from each watermark).
SCHEDULE: tuple[ScheduledJob, ...] = (
    ScheduledJob(
        job_name="sync-movements",
        trigger=CronTrigger(hour=0, minute=0),
        description="Daily incremental sync at 00:00 (captures the previous day).",
    ),
)


def _run_scheduled(job_name: str, correlation_id: str | None = None) -> None:
    """Trigger body: run a registered job through the serialized runner.

    ``correlation_id`` is propagated from a manual API trigger so the request and
    the job it spawned share one id; scheduled fires pass ``None`` (fresh id).
    """
    run_job(get(job_name), JobContext(), correlation_id=correlation_id)


def build_scheduler() -> BackgroundScheduler:
    """Build a scheduler with every :data:`SCHEDULE` entry registered.

    Not started — the caller (the standalone runner or the FastAPI lifespan) starts
    and shuts it down. Fails fast if a scheduled name is not a registered job.

    Returns:
        A configured, not-yet-started ``BackgroundScheduler``.
    """
    scheduler = BackgroundScheduler(job_defaults=_JOB_DEFAULTS)
    for entry in SCHEDULE:
        get(entry.job_name)  # fail fast on a typo'd / unregistered job name
        scheduler.add_job(
            _run_scheduled,
            trigger=entry.trigger,
            args=[entry.job_name],
            id=entry.job_name,
            name=entry.description,
            replace_existing=True,
        )
    return scheduler


def run_now(scheduler: BackgroundScheduler, job_name: str) -> None:
    """Enqueue a registered job to run once, now, in the scheduler's thread pool.

    Used by the API's manual-trigger endpoint: it goes through the same executor
    and the same :func:`run_job` path as scheduled fires (write-lock + recording),
    so a manual run behaves identically to a scheduled one.

    Args:
        scheduler: A started scheduler (typically the one in the FastAPI lifespan).
        job_name: Name of a registered job.
    """
    get(job_name)  # fail fast (KeyError) if the name is not registered
    # Propagate the caller's correlation id (if any) into the scheduler thread.
    scheduler.add_job(_run_scheduled, args=[job_name, current_correlation_id()])


def main() -> int:
    """Start the scheduler in the foreground and run until interrupted (Ctrl-C)."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8")

    started_log = log.start()
    sampler = PerformanceSampler(log)
    sampler.start()
    scheduler = build_scheduler()
    scheduler.start()
    print("Scheduler started (Ctrl-C to stop). Scheduled jobs:")
    for job in scheduler.get_jobs():
        print(f"  {job.id:<20} next run: {job.next_run_time}")
    try:
        threading.Event().wait()  # block the main thread until interrupted
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        scheduler.shutdown()
        sampler.stop()
        if started_log:
            log.shutdown()
        print("Scheduler stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
