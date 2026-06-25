"""FastAPI app: hosts the in-process scheduler and exposes the RESTful API.

The scheduler is started/stopped in the app ``lifespan`` (single-process topology:
API and scheduler share the process). The surface follows the Pulsar REST standard
(``docs/arquitectura-restful.md`` §18): domain resources live under ``/v1``, errors
are RFC 9457 problem+json, and the three log kinds are one polymorphic collection
(``GET /v1/logs?type=…``). ``/health`` stays unversioned (operational, not a domain
resource).

Run the server:
    python -m pulsar.api
Interactive docs are served at ``/docs`` once running.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, FastAPI, Query, Request, Response

from pulsar.api.logs import LogType, query_logs
from pulsar.api.problem import Problem, ProblemException, register_problem_handlers
from pulsar.api.runs import query_runs, run_to_item
from pulsar.api.schemas import Health, JobInfo, JobRunInfo, LogPage, RunItem, RunPage
from pulsar.jobs.core import Job, all_jobs, get, last_run
from pulsar.jobs.runs import ActiveRunError, Run, run_store
from pulsar.jobs.scheduler import build_scheduler, run_now
from pulsar.logger import log
from pulsar.logger.capture.http import LoggingMiddleware
from pulsar.logger.capture.resources import PerformanceSampler
from pulsar.logger.context import current_correlation_id

#: Pagination bounds for every collection (``docs/arquitectura-restful.md`` §11).
_DEFAULT_LIMIT = 100
_MAX_LIMIT = 1000

#: Reusable OpenAPI doc for endpoints that can 404 with a problem detail.
_NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {"model": Problem, "description": "Unknown job"}
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start logger + scheduler on startup; shut them down on shutdown.

    The logger is a process-wide singleton, so we only shut it down if this app
    actually started it (lets tests own the singleton's lifecycle).
    """
    started_log = log.start()
    run_store.ensure_schema()  # authoritative run state (separate store under db/)
    sampler = PerformanceSampler(log)
    sampler.start()
    scheduler = build_scheduler()
    scheduler.start()
    app.state.scheduler = scheduler
    try:
        yield
    finally:
        scheduler.shutdown()
        sampler.stop()
        if started_log:
            log.shutdown()


def _job_info(job: Job) -> JobInfo:
    """Build the API view of a job from the registry and its last run."""
    run = last_run(job.name)
    run_info = (
        None
        if run is None
        else JobRunInfo(
            status=run.status,
            rows=run.rows,
            detail=run.detail,
            started_at=run.started_at,
            finished_at=run.finished_at,
            duration_s=run.duration_s,
        )
    )
    return JobInfo(
        name=job.name,
        description=job.description,
        writes_lake=job.writes_lake,
        last_run=run_info,
    )


def _require_job(name: str) -> Job:
    """Return the registered job, or raise a 404 problem if it is unknown."""
    try:
        return get(name)
    except KeyError:
        raise ProblemException(
            404,
            "Unknown job",
            detail=f"No job named {name!r} is registered.",
            type_slug="unknown-job",
        ) from None


def _set_next_link(response: Response, request: Request, next_cursor: str | None) -> None:
    """Advertise the next page via an RFC 8288 ``Link`` header (when there is one)."""
    if next_cursor:
        url = request.url.include_query_params(cursor=next_cursor)
        response.headers["Link"] = f'<{url}>; rel="next"'


# Shared query-parameter types for the collections.
_Limit = Annotated[int, Query(ge=1, le=_MAX_LIMIT)]
_Sort = Annotated[str, Query(description="Sort key: 'ts' (asc) or '-ts' (desc, default).")]
#: Sort key for the runs collection (its time field is ``created_at``).
_RunSort = Annotated[str, Query(description="Sort key: 'created_at' or '-created_at' (default).")]


def _run_conflict(name: str) -> ProblemException:
    """Build the 409 problem for triggering a job that already has an active run."""
    return ProblemException(
        409,
        "Run already active",
        detail=f"Job {name!r} already has an active run; retry once it finishes.",
        type_slug="run-conflict",
    )


def _set_run_location(response: Response, run: Run) -> None:
    """Point ``Location`` at the run resource created/replayed by ``POST .../runs``."""
    response.headers["Location"] = f"/v1/jobs/{run.job}/runs/{run.id}"


def create_app() -> FastAPI:
    """Build the FastAPI application (scheduler is started by the lifespan)."""
    app = FastAPI(title="Pulsar", version="0.1.0", lifespan=lifespan)
    app.add_middleware(LoggingMiddleware)
    register_problem_handlers(app)

    @app.get("/health")
    def health() -> Health:
        """Liveness: the process is up and serving."""
        return Health(status="ok")

    @app.get("/health/ready", responses={503: {"model": Problem}})
    def ready(request: Request) -> Health:
        """Readiness: the scheduler is running (i.e. jobs can be triggered)."""
        scheduler = getattr(request.app.state, "scheduler", None)
        if scheduler is None or not scheduler.running:
            raise ProblemException(
                503, "Not ready", detail="Scheduler is not running.", type_slug="not-ready"
            )
        return Health(status="ready")

    v1 = APIRouter(prefix="/v1")

    @v1.get("/jobs")
    def list_jobs() -> list[JobInfo]:
        """List the registered jobs and each one's last run."""
        return [_job_info(job) for job in all_jobs()]

    @v1.get("/jobs/{name}", responses=_NOT_FOUND)
    def get_job(name: str) -> JobInfo:
        """Get one job and its last run."""
        return _job_info(_require_job(name))

    @v1.post(
        "/jobs/{name}/runs",
        status_code=202,
        responses={**_NOT_FOUND, 409: {"model": Problem, "description": "A run is already active"}},
    )
    def create_run(name: str, request: Request, response: Response) -> RunItem:
        """Trigger a run (async): create the run, enqueue it, and return it.

        Returns ``202 Accepted`` with a ``Location`` pointing at the new run resource;
        the job runs in the background, so poll ``GET /v1/jobs/{name}/runs/{id}`` for
        its lifecycle. A repeated ``Idempotency-Key`` replays the original run instead
        of starting a new one; triggering while one is already active → ``409``.
        """
        _require_job(name)
        key = request.headers.get("Idempotency-Key")
        if key is not None:
            existing = run_store.find_by_idempotency_key(key)
            if existing is not None:  # replay: same key → original run, no new enqueue
                _set_run_location(response, existing)
                return run_to_item(existing)
        if run_store.has_active(name):
            raise _run_conflict(name)
        try:
            run, created = run_store.create(
                name,
                trigger="api",
                correlation_id=current_correlation_id(),
                idempotency_key=key,
            )
        except ActiveRunError as exc:  # lost a race with a concurrent trigger
            raise _run_conflict(name) from exc
        if created:  # a replay (created=False) is already enqueued; never enqueue twice
            run_now(request.app.state.scheduler, name, run_id=run.id)
        _set_run_location(response, run)
        return run_to_item(run)

    @v1.get("/jobs/{name}/runs", responses=_NOT_FOUND)
    def list_runs(
        name: str,
        request: Request,
        response: Response,
        status: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        sort: _RunSort = "-created_at",
        limit: _Limit = _DEFAULT_LIMIT,
        cursor: str | None = None,
    ) -> RunPage:
        """List a job's run history (newest first), from the authoritative runs store."""
        _require_job(name)
        items, next_cursor = query_runs(
            name,
            status=status,
            since=since,
            until=until,
            sort=sort,
            limit=limit,
            cursor=cursor,
        )
        _set_next_link(response, request, next_cursor)
        return RunPage(items=items, next_cursor=next_cursor)

    @v1.get("/jobs/{name}/runs/{run_id}", responses=_NOT_FOUND)
    def get_run(name: str, run_id: str) -> RunItem:
        """Get one run of a job by id (its current lifecycle state)."""
        _require_job(name)
        run = run_store.get(name, run_id)
        if run is None:
            raise ProblemException(
                404,
                "Unknown run",
                detail=f"No run {run_id!r} for job {name!r}.",
                type_slug="unknown-run",
            )
        return run_to_item(run)

    @v1.get("/logs")
    def list_logs(
        request: Request,
        response: Response,
        type: Annotated[LogType | None, Query()] = None,
        status: str | None = None,
        level: str | None = None,
        correlation_id: str | None = None,
        job: str | None = None,
        path: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        sort: _Sort = "-ts",
        limit: _Limit = _DEFAULT_LIMIT,
        cursor: str | None = None,
    ) -> LogPage:
        """List log records across kinds. ``type`` filters the kind (omit for all)."""
        items, next_cursor = query_logs(
            type_=type,
            status=status,
            level=level,
            correlation_id=correlation_id,
            job=job,
            path=path,
            since=since,
            until=until,
            sort=sort,
            limit=limit,
            cursor=cursor,
        )
        _set_next_link(response, request, next_cursor)
        return LogPage(items=items, next_cursor=next_cursor)

    app.include_router(v1)
    return app
