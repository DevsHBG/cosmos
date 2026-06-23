"""Log record types: the data the logger persists.

Records are **Pydantic models** (data-at-the-boundary: persisted, serialized to
JSON, and queried back), unlike :class:`~pulsar.jobs.core.Job`, which is
behavioural. Each concrete type sets a ``KIND`` classvar that maps it to a
sink/table; adding a new type is just a new subclass plus a registration, so the
core never changes.

Hierarchy::

    LogRecord                      # ts, level, correlation_id, source
    ├── ActivityLog                # something that ran: status, timing, detail
    │   ├── JobLog   → job_logs     (a job run)
    │   └── ApiLog   → api_logs     (an HTTP request)
    └── PerformanceLog → performance_logs   (a host/process sample)
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, field_serializer


class LogRecord(BaseModel):
    """Base record: the fields common to every log kind."""

    model_config = ConfigDict(frozen=True)

    #: Sink/table key; each concrete subtype sets it (excluded from fields).
    KIND: ClassVar[str]

    ts: datetime
    level: str = "info"  # info | warn | error
    correlation_id: str | None = None
    source: str | None = None

    @field_serializer("ts")
    def _serialize_ts(self, value: datetime) -> str:
        """Pin ``ts`` to ISO-8601 text so stored values match query filters."""
        return value.isoformat()


class ActivityLog(LogRecord):
    """Abstract base for something that ran with an outcome (a job or a request)."""

    status: str = ""  # ok | failed
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int = 0
    detail: str | None = None  # free-text outcome; full body only on failure (capped)

    @field_serializer("started_at", "finished_at")
    def _serialize_optional_ts(self, value: datetime | None) -> str | None:
        """Store the run window as ISO-8601 text (round-trips via ``fromisoformat``)."""
        return value.isoformat() if value is not None else None


class JobLog(ActivityLog):
    """A job run → table ``job_logs``."""

    KIND: ClassVar[str] = "job_logs"

    job: str = ""  # registry name, e.g. "sync-movements"
    rows: int = 0  # rows/affected count reported by the run


class ApiLog(ActivityLog):
    """An HTTP request → table ``api_logs``."""

    KIND: ClassVar[str] = "api_logs"

    method: str = ""  # GET, POST, …
    path: str = ""  # e.g. "/jobs/sync-movements/run"
    status_code: int = 0  # HTTP status


class PerformanceLog(LogRecord):
    """A host/process resource sample → table ``performance_logs``."""

    KIND: ClassVar[str] = "performance_logs"

    cpu_pct: float = 0.0
    rss_mb: float = 0.0
    mem_pct: float = 0.0
    disk_pct: float = 0.0
    disk_io_mb: float = 0.0
