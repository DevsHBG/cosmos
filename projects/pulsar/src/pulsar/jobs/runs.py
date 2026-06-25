"""Runs store: the authoritative lifecycle state of every job run.

Unlike the logger (best-effort, append-only, drops under backpressure), a run's
state is **authoritative and mutable** (``queued → running → ok/failed``), so it
lives in its own durable, synchronous SQLite store — not in the log tables. It is
owned by the jobs layer (a peer module), grouped with the other operational stores
under ``db/`` (``db/runs/runs.sqlite``; the logger uses ``db/logs/logs.sqlite``).

The ``JobLog`` emitted by :func:`pulsar.jobs.core.run_job` is unchanged and keeps
feeding the cross-cutting observability collection (``GET /v1/logs?type=job``);
this store is the source of truth for *run state* (live + historical) instead.

Invariants enforced at the DB level (race-safe):

- **One active API-triggered run per job**: a partial unique index on ``job`` where
  ``status`` is active and ``trigger='api'`` backs the API's ``409 Conflict``. Direct
  runs (CLI/scheduler/tests) are exempt, so they can run concurrently and serialize
  on the lakehouse write-lock instead.
- **Idempotency-Key dedup**: a partial unique index on ``idempotency_key`` makes a
  retried ``POST .../runs`` replay the original run instead of creating a new one.
"""

from __future__ import annotations

import sqlite3
import threading
import uuid
from collections.abc import Sequence
from contextlib import closing
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, get_args

from pydantic import BaseModel, ConfigDict, field_serializer
from pydantic_settings import BaseSettings, SettingsConfigDict


class RunStoreSettings(BaseSettings):
    """Runs store settings, loaded from ``PULSAR_RUNS_*`` env vars.

    All fields have defaults, so the store works with zero configuration.
    """

    model_config = SettingsConfigDict(env_prefix="PULSAR_RUNS_", env_file=".env", extra="ignore")

    #: Authoritative SQLite store for run state, grouped with logs under ``db/``.
    db_path: Path = Path("db/runs/runs.sqlite")
    #: A ``queued``/``running`` run older than this is no longer counted "active"
    #: (so a crashed/stuck run never blocks a job's manual trigger forever).
    stale_after_s: float = 3600.0


@lru_cache
def get_run_store_settings() -> RunStoreSettings:
    """Return cached runs-store settings loaded from the environment."""
    return RunStoreSettings()


class Run(BaseModel):
    """One job run: its identity and lifecycle state (persisted in ``runs``)."""

    model_config = ConfigDict(frozen=True)

    id: str  # opaque, stable (uuid4 hex)
    job: str  # registry name, e.g. "sync-movements"
    status: str  # queued | running | ok | failed
    trigger: str  # api | scheduled | cli | manual
    rows: int = 0
    detail: str | None = None
    correlation_id: str | None = None
    idempotency_key: str | None = None
    created_at: datetime  # enqueue time
    started_at: datetime | None = None  # when execution actually began (post write-lock)
    finished_at: datetime | None = None

    @field_serializer("created_at")
    def _ser_created(self, value: datetime) -> str:
        """Pin ``created_at`` to ISO-8601 text (matches the stored/query format)."""
        return value.isoformat()

    @field_serializer("started_at", "finished_at")
    def _ser_optional(self, value: datetime | None) -> str | None:
        """Store the run window as ISO-8601 text (round-trips via ``fromisoformat``)."""
        return value.isoformat() if value is not None else None

    @property
    def duration_s(self) -> float | None:
        """Execution wall-clock in seconds (``None`` until both ends are known)."""
        if self.started_at is not None and self.finished_at is not None:
            return (self.finished_at - self.started_at).total_seconds()
        return None


class ActiveRunError(Exception):
    """Raised when a job already has an active API-triggered run (→ HTTP 409)."""

    def __init__(self, job: str) -> None:
        self.job = job
        super().__init__(f"job {job!r} already has an active run")


def _affinity(column: str) -> str:
    """SQLite column affinity derived from the ``Run`` field's annotation."""
    annotation = Run.model_fields[column].annotation
    args = [a for a in get_args(annotation) if a is not type(None)]
    base = args[0] if args else annotation
    if base in (bool, int):
        return "INTEGER"
    if base is float:
        return "REAL"
    return "TEXT"


class RunStore:
    """Durable, synchronous SQLite store for run lifecycle state.

    Writes are direct (not queued/best-effort): a run's state must not be lost. The
    schema is created lazily on first use, so callers never have to remember to
    initialise it (the API lifespan calls :meth:`ensure_schema` explicitly anyway).
    """

    def __init__(self, settings: RunStoreSettings | None = None) -> None:
        self._settings = settings or get_run_store_settings()
        self._columns: tuple[str, ...] = tuple(Run.model_fields)
        self._ready = False
        self._lock = threading.Lock()

    # -- configuration ----------------------------------------------------

    def configure(self, settings: RunStoreSettings) -> None:
        """Point the store at a new database (used by tests for isolation)."""
        with self._lock:
            self._settings = settings
            self._ready = False

    @property
    def db_path(self) -> Path:
        """Path to the backing SQLite file."""
        return self._settings.db_path

    # -- schema -----------------------------------------------------------

    def ensure_schema(self) -> None:
        """Create the ``runs`` table and indices if absent (idempotent)."""
        self._create_schema()
        self._ready = True

    def _ensure(self) -> None:
        if not self._ready:
            with self._lock:
                if not self._ready:  # re-check under the lock (another thread may have won)
                    self._create_schema()
                    self._ready = True

    def _create_schema(self) -> None:
        cols = ", ".join(f'"{c}" {_affinity(c)}' for c in self._columns)
        with closing(self._connect()) as con, con:
            con.execute(f'CREATE TABLE IF NOT EXISTS "runs" ({cols}, PRIMARY KEY ("id"))')
            con.execute('CREATE INDEX IF NOT EXISTS "runs_job_created" ON "runs" (job, created_at)')
            # Retried POST .../runs with the same key replays the original run.
            con.execute(
                'CREATE UNIQUE INDEX IF NOT EXISTS "runs_idem" ON "runs" (idempotency_key) '
                "WHERE idempotency_key IS NOT NULL"
            )
            # At most one active API-triggered run per job (backs the 409); direct
            # runs (other triggers) are exempt and serialize on the write-lock.
            con.execute(
                'CREATE UNIQUE INDEX IF NOT EXISTS "runs_active_api" ON "runs" (job) '
                "WHERE status IN ('queued','running') AND trigger = 'api'"
            )

    def _connect(self) -> sqlite3.Connection:
        self._settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self._settings.db_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        return con

    # -- writes -----------------------------------------------------------

    def create(
        self,
        job: str,
        *,
        trigger: str,
        correlation_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> tuple[Run, bool]:
        """Insert a fresh ``queued`` run; return ``(run, created)``.

        ``created`` is ``False`` when the same ``idempotency_key`` already maps to a
        run and that original is returned instead (replay) — the caller must then
        **not** enqueue it again.

        Raises:
            ActiveRunError: the job already has an active API-triggered run.
        """
        self._ensure()
        run = Run(
            id=uuid.uuid4().hex,
            job=job,
            status="queued",
            trigger=trigger,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            created_at=datetime.now(UTC),
        )
        cols = ", ".join(f'"{c}"' for c in self._columns)
        placeholders = ", ".join("?" for _ in self._columns)
        try:
            with closing(self._connect()) as con, con:
                con.execute(f'INSERT INTO "runs" ({cols}) VALUES ({placeholders})', self._row(run))
        except sqlite3.IntegrityError as exc:
            if idempotency_key is not None:
                existing = self.find_by_idempotency_key(idempotency_key)
                if existing is not None:
                    return existing, False  # replay: same key → original run
            raise ActiveRunError(job) from exc
        return run, True

    def mark_running(self, run_id: str, started_at: datetime) -> None:
        """Transition a ``queued`` run to ``running`` and stamp ``started_at``."""
        self._ensure()
        with closing(self._connect()) as con, con:
            con.execute(
                "UPDATE runs SET status='running', started_at=? WHERE id=? AND status='queued'",
                (started_at.isoformat(), run_id),
            )

    def finalize(
        self, run_id: str, *, status: str, rows: int, detail: str | None, finished_at: datetime
    ) -> None:
        """Transition a run to its terminal state (``ok``/``failed``)."""
        self._ensure()
        fin = finished_at.isoformat()
        with closing(self._connect()) as con, con:
            con.execute(
                "UPDATE runs SET status=?, rows=?, detail=?, finished_at=?, "
                "started_at=COALESCE(started_at, ?) WHERE id=?",
                (status, rows, detail, fin, fin, run_id),
            )

    # -- reads ------------------------------------------------------------

    def get(self, job: str, run_id: str) -> Run | None:
        """Return one run of ``job`` by id (or ``None``)."""
        self._ensure()
        return self._query_one("SELECT * FROM runs WHERE job = ? AND id = ?", (job, run_id))

    def find_by_idempotency_key(self, key: str) -> Run | None:
        """Return the run created under ``key`` (or ``None``)."""
        self._ensure()
        return self._query_one("SELECT * FROM runs WHERE idempotency_key = ?", (key,))

    def has_active(self, job: str) -> bool:
        """Whether ``job`` has a non-stale active (``queued``/``running``) run."""
        self._ensure()
        threshold = (
            datetime.now(UTC) - timedelta(seconds=self._settings.stale_after_s)
        ).isoformat()
        with closing(self._connect()) as con:
            row = con.execute(
                "SELECT 1 FROM runs WHERE job = ? AND status IN ('queued','running') "
                "AND created_at >= ? LIMIT 1",
                (job, threshold),
            ).fetchone()
        return row is not None

    def latest_terminal(self, job: str) -> Run | None:
        """Return the most recent finished (``ok``/``failed``) run of ``job``."""
        self._ensure()
        return self._query_one(
            "SELECT * FROM runs WHERE job = ? AND status IN ('ok','failed') "
            "ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (job,),
        )

    def list(
        self,
        job: str,
        *,
        status: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        descending: bool = True,
        after: tuple[str, int] | None = None,
        limit: int = 100,
    ) -> list[tuple[Run, int]]:
        """Keyset page of ``job``'s runs as ``(run, rowid)`` over ``(created_at, rowid)``.

        ``after`` is the ``(created_at, rowid)`` of the last item on the previous
        page; rows strictly after it (in ``descending`` direction) are returned.
        """
        self._ensure()
        clauses = ["job = ?"]
        params: list[Any] = [job]
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if since is not None:
            clauses.append("created_at >= ?")
            params.append(since.isoformat())
        if until is not None:
            clauses.append("created_at <= ?")
            params.append(until.isoformat())
        if after is not None:
            cur_ts, cur_rowid = after
            op = "<" if descending else ">"
            clauses.append(f"(created_at {op} ? OR (created_at = ? AND rowid {op} ?))")
            params.extend([cur_ts, cur_ts, cur_rowid])
        direction = "DESC" if descending else "ASC"
        sql = (
            f"SELECT rowid AS _rowid, * FROM runs WHERE {' AND '.join(clauses)} "
            f"ORDER BY created_at {direction}, rowid {direction} LIMIT ?"
        )
        params.append(limit)
        with closing(self._connect()) as con:
            rows = con.execute(sql, params).fetchall()
        return [(self._row_to_run(row), int(row["_rowid"])) for row in rows]

    # -- helpers ----------------------------------------------------------

    def _query_one(self, sql: str, params: Sequence[Any]) -> Run | None:
        with closing(self._connect()) as con:
            row = con.execute(sql, params).fetchone()
        return self._row_to_run(row) if row is not None else None

    def _row(self, run: Run) -> tuple[Any, ...]:
        data = run.model_dump(mode="json")
        return tuple(data[column] for column in self._columns)

    @staticmethod
    def _row_to_run(row: sqlite3.Row) -> Run:
        data = dict(zip(row.keys(), row, strict=True))
        data.pop("_rowid", None)  # present only on keyset (``list``) rows
        return Run(**data)


#: Process-wide singleton (mirrors ``pulsar.logger.log``); tests reconfigure it.
run_store = RunStore()
