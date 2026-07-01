"""Pydantic response models for the API (the public shape of the resources).

Logs are exposed as a single **polymorphic collection**: ``type`` is a discriminator
on each item (``job``/``api``/``performance``), so one ``GET /v1/logs`` serves every
kind and a new kind adds an enum value, not an endpoint (see
``codex/20-pulsar/arquitectura/arquitectura-restful.md`` §18.2).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class Health(BaseModel):
    """Liveness/readiness response."""

    status: str


class JobRunInfo(BaseModel):
    """A job's most recent run."""

    status: str
    rows: int
    detail: str
    started_at: datetime
    finished_at: datetime
    duration_s: float


class JobInfo(BaseModel):
    """A registered job and its last run (``null`` if it has not run yet)."""

    name: str
    description: str
    writes_lake: bool
    last_run: JobRunInfo | None = None


class RunItem(BaseModel):
    """A job run: its identity and lifecycle state (the run resource representation)."""

    id: str
    job: str
    status: str  # queued | running | ok | failed
    trigger: str  # api | scheduled | cli | manual
    rows: int
    detail: str | None = None
    correlation_id: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_s: float | None = None


class RunPage(BaseModel):
    """One page of a job's runs collection (cursor pagination, §11).

    ``next_cursor`` is an opaque token for the next page (``null`` on the last page);
    the same value is also surfaced via the ``Link: rel="next"`` response header.
    """

    items: list[RunItem]
    next_cursor: str | None = None


# -- Logs: one polymorphic collection, discriminated by ``type`` -----------------


class _LogItemBase(BaseModel):
    """Fields common to every log item (mirrors ``LogRecord``)."""

    ts: datetime
    level: str
    correlation_id: str | None = None
    source: str | None = None


class _ActivityItem(_LogItemBase):
    """Shared shape for something that ran with an outcome (a run or a request)."""

    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int
    detail: str | None = None


class JobLogItem(_ActivityItem):
    """A job run (``type="job"`` → ``job_logs``)."""

    type: Literal["job"] = "job"
    job: str
    rows: int


class ApiLogItem(_ActivityItem):
    """An HTTP request (``type="api"`` → ``api_logs``)."""

    type: Literal["api"] = "api"
    method: str
    path: str
    status_code: int


class PerformanceLogItem(_LogItemBase):
    """A host/process resource sample (``type="performance"`` → ``performance_logs``)."""

    type: Literal["performance"] = "performance"
    cpu_pct: float
    rss_mb: float
    mem_pct: float
    disk_pct: float
    disk_io_mb: float


#: The bare union of log item models (for typing internal helpers).
LogItemModel = JobLogItem | ApiLogItem | PerformanceLogItem
#: A single log item in a response: the discriminated union over every kind.
LogItem = Annotated[LogItemModel, Field(discriminator="type")]


class LogPage(BaseModel):
    """One page of the logs collection (cursor pagination, §11).

    ``next_cursor`` is an opaque token for the next page (``null`` on the last page);
    the same value is also surfaced via the ``Link: rel="next"`` response header.
    """

    items: list[LogItem]
    next_cursor: str | None = None
