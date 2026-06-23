"""Tests for the in-process scheduler wiring (no jobs are actually executed)."""

from __future__ import annotations

from apscheduler.triggers.cron import CronTrigger

from pulsar.jobs.core import get
from pulsar.jobs.scheduler import SCHEDULE, build_scheduler


def test_every_scheduled_name_is_a_registered_job() -> None:
    # A typo in SCHEDULE must fail loudly, not schedule a phantom job.
    for entry in SCHEDULE:
        get(entry.job_name)


def test_build_scheduler_registers_daily_sync_at_midnight() -> None:
    scheduler = build_scheduler()
    scheduler.start(paused=True)  # materialize jobs without starting the worker
    try:
        jobs = {job.id: job for job in scheduler.get_jobs()}
        assert "sync-movements" in jobs
        trigger = jobs["sync-movements"].trigger
        assert isinstance(trigger, CronTrigger)
        text = str(trigger)
        assert "hour='0'" in text
        assert "minute='0'" in text
    finally:
        scheduler.shutdown(wait=False)
