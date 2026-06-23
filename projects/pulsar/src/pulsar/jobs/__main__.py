"""CLI for the in-house job layer: ``python -m pulsar.jobs <list|run> ...``.

Examples:
    python -m pulsar.jobs list
    python -m pulsar.jobs run sync-movements
    python -m pulsar.jobs run backfill-movements --company HR --until 2026-06-18
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from pulsar.config.settings import Company
from pulsar.jobs.core import Job, JobContext, all_jobs, last_run, run_job
from pulsar.jobs.movements import BackfillMovements, SyncMovements
from pulsar.logger import log

_JOB_CHOICES = ("sync-movements", "backfill-movements")


def _companies(value: str) -> tuple[Company, ...]:
    return tuple(Company) if value == "ALL" else (Company(value),)


def _context(args: argparse.Namespace) -> JobContext:
    defaults = JobContext()
    return JobContext(
        catalog_path=args.catalog or defaults.catalog_path,
        data_path=args.data or defaults.data_path,
    )


def _build_job(args: argparse.Namespace) -> Job:
    companies = _companies(args.company)
    if args.job == "sync-movements":
        return SyncMovements(companies)
    return BackfillMovements(companies, since=args.since, until=args.until)


def main() -> int:
    """Parse args and either list jobs or run one; return a process exit code."""
    # Force UTF-8 stdout so 🟢/🔴 and tables never crash a legacy Windows console.
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(prog="pulsar.jobs", description="Run pulsar jobs in-house.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List registered jobs and their last run.")
    runner = sub.add_parser("run", help="Run a job once, now.")
    runner.add_argument("job", choices=_JOB_CHOICES, help="Job to run.")
    runner.add_argument(
        "--company",
        default="ALL",
        choices=[*(c.value for c in Company), "ALL"],
        help="Company to target, or ALL (default).",
    )
    runner.add_argument("--since", type=date.fromisoformat, default=None, help="YYYY-MM-DD start.")
    runner.add_argument("--until", type=date.fromisoformat, default=None, help="YYYY-MM-DD end.")
    runner.add_argument("--catalog", type=Path, default=None, help="Override catalog path.")
    runner.add_argument("--data", type=Path, default=None, help="Override data path.")
    args = parser.parse_args()

    if args.command == "list":
        for job in all_jobs():
            run = last_run(job.name)
            if run is None:
                status = "never run"
            else:
                status = f"{run.status} @ {run.finished_at:%Y-%m-%d %H:%M}"
            print(f"{job.name:<20} writes_lake={job.writes_lake!s:<5} last: {status}")
            print(f"  {job.description}")
        return 0

    # Start the logger around the run so its JobLog is flushed before exit.
    started_log = log.start()
    try:
        result = run_job(_build_job(args), _context(args))
    finally:
        if started_log:
            log.shutdown()
    print(f"[{result.job}] {result.status}: {result.rows} rows in {result.duration_s:.1f}s")
    if not result.ok:
        print(result.detail)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
