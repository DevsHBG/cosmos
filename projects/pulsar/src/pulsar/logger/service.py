"""The logger service: one emit point backed by a non-blocking flush worker.

``emit`` enqueues and returns immediately; a background thread drains the queue
and writes batches to the registered sinks. Logging is **best-effort** — a sink
failure is swallowed (degraded to stderr) and never propagates to the caller.
``query`` and ``connect_duckdb`` read the SQLite store back for unified analysis.

Lifecycle (``start``/``shutdown``) is wired into the FastAPI ``lifespan`` and the
standalone scheduler/CLI. ``start`` returns whether it actually started the worker,
so a caller only shuts down what it itself started (lets tests own the singleton).
"""

from __future__ import annotations

import queue
import sqlite3
import sys
import threading
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pulsar.logger.config import LoggerSettings, get_logger_settings
from pulsar.logger.records import ApiLog, JobLog, LogRecord, PerformanceLog
from pulsar.logger.sinks import Sink, SqliteSink

if TYPE_CHECKING:
    from collections.abc import Sequence

    from duckdb import DuckDBPyConnection

#: Record types registered against the default SQLite store on ``start``.
_DEFAULT_TYPES: tuple[type[LogRecord], ...] = (JobLog, ApiLog, PerformanceLog)


class LoggerService:
    """Process-wide logger: registry, non-blocking emit, flush worker, query."""

    def __init__(self, config: LoggerSettings | None = None) -> None:
        self._config = config or get_logger_settings()
        self._sinks: dict[type[LogRecord], Sink] = {}
        self._queue: queue.Queue[LogRecord] = queue.Queue(maxsize=self._config.queue_maxsize)
        self._dropped = 0
        self._worker: threading.Thread | None = None
        self._stopping = threading.Event()
        self._drain_lock = threading.Lock()
        self._lifecycle_lock = threading.Lock()
        self._started = False

    # -- configuration ----------------------------------------------------

    def configure(self, config: LoggerSettings) -> None:
        """Replace the settings and reset state (only while stopped).

        Used by tests to point the singleton at a temporary store.
        """
        if self._started:
            raise RuntimeError("cannot reconfigure a running logger")
        self._config = config
        self._sinks = {}
        self._dropped = 0
        self._queue = queue.Queue(maxsize=config.queue_maxsize)

    def register(self, record_type: type[LogRecord], sink: Sink) -> None:
        """Bind a record type to a sink (overrides any previous binding)."""
        self._sinks[record_type] = sink

    def _register_defaults(self) -> None:
        for record_type in _DEFAULT_TYPES:
            if record_type not in self._sinks:
                sink = SqliteSink(self._config.db_path, record_type.KIND, record_type)
                self.register(record_type, sink)

    # -- emit / flush -----------------------------------------------------

    def emit(self, record: LogRecord) -> None:
        """Enqueue a record for background writing; never blocks, never raises."""
        try:
            self._queue.put_nowait(record)
        except queue.Full:
            self._dropped += 1  # backpressure: drop and count, never block the caller

    def flush(self) -> None:
        """Drain everything queued so far and write it now (in the caller thread)."""
        with self._drain_lock:
            batch: list[LogRecord] = []
            while True:
                try:
                    batch.append(self._queue.get_nowait())
                except queue.Empty:
                    break
            self._write(batch)

    def _write(self, records: list[LogRecord]) -> None:
        if not records:
            return
        by_type: dict[type[LogRecord], list[LogRecord]] = {}
        for record in records:
            by_type.setdefault(type(record), []).append(record)
        for record_type, items in by_type.items():
            sink = self._sinks.get(record_type)
            if sink is None:
                continue  # unregistered type: drop (best-effort)
            try:
                for start in range(0, len(items), self._config.batch_size):
                    sink.write(items[start : start + self._config.batch_size])
            except Exception as exc:  # best-effort: logging must never break the caller
                print(f"[logger] sink write failed: {exc!r}", file=sys.stderr)

    # -- lifecycle --------------------------------------------------------

    def start(self) -> bool:
        """Register defaults, create schemas, and start the flush worker.

        Returns:
            ``True`` if this call started the worker, ``False`` if already running.
        """
        with self._lifecycle_lock:
            if self._started:
                return False
            self._register_defaults()
            for sink in self._sinks.values():
                try:
                    sink.ensure_schema()
                except Exception as exc:  # best-effort: never break startup on logging
                    print(f"[logger] ensure_schema failed: {exc!r}", file=sys.stderr)
            self._stopping.clear()
            self._worker = threading.Thread(target=self._run, name="logger-flush", daemon=True)
            self._worker.start()
            self._started = True
            return True

    def shutdown(self) -> None:
        """Stop the worker and flush anything left in the queue (idempotent)."""
        with self._lifecycle_lock:
            worker = self._worker
            if self._started:
                self._stopping.set()
                if worker is not None:
                    worker.join(timeout=10.0)
                self._worker = None
                self._started = False
        self.flush()  # final drain, also covers emits made while never started

    def _run(self) -> None:
        while not self._stopping.wait(self._config.flush_interval_s):
            self.flush()
        self.flush()  # final pass after stop is signalled

    # -- query ------------------------------------------------------------

    def query(
        self,
        kind: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        where: str | None = None,
        params: Sequence[Any] = (),
        order_by: str = "ts",
        descending: bool = False,
        limit: int | None = None,
        include_rowid: bool = False,
    ) -> list[dict[str, Any]]:
        """Read records of one ``kind`` back from the SQLite store.

        Args:
            kind: A registered record ``KIND`` (its table name).
            since: Inclusive lower bound on ``ts``.
            until: Inclusive upper bound on ``ts``.
            where: Extra SQL predicate with ``?`` placeholders (internal callers only).
            params: Values bound to the ``where`` placeholders.
            order_by: Column to sort by (must be a valid identifier).
            descending: Sort descending when ``True``.
            limit: Maximum number of rows.
            include_rowid: When ``True``, expose each row's SQLite ``rowid`` as a
                ``_rowid`` field and add it as an ``ORDER BY`` tiebreak, giving a
                total, stable order for keyset (cursor) pagination.

        Returns:
            The matching rows as dicts (empty if the store/table does not exist yet).
        """
        registered = {rt.KIND for rt in self._sinks}
        if kind not in registered:
            raise KeyError(f"unknown log kind: {kind!r}; registered: {sorted(registered)}")
        if not order_by.isidentifier():
            raise ValueError(f"invalid order_by column: {order_by!r}")
        if not self._config.db_path.exists():
            return []

        clauses: list[str] = []
        values: list[Any] = []
        if since is not None:
            clauses.append("ts >= ?")
            values.append(since.isoformat())
        if until is not None:
            clauses.append("ts <= ?")
            values.append(until.isoformat())
        if where:
            clauses.append(f"({where})")
            values.extend(params)

        direction = "DESC" if descending else "ASC"
        select = "rowid AS _rowid, *" if include_rowid else "*"
        sql = f'SELECT {select} FROM "{kind}"'
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += f' ORDER BY "{order_by}" {direction}'
        if include_rowid:
            sql += f", rowid {direction}"
        if limit is not None:
            sql += " LIMIT ?"
            values.append(limit)

        con = sqlite3.connect(self._config.db_path)
        con.row_factory = sqlite3.Row
        try:
            exists = con.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (kind,)
            ).fetchone()
            if exists is None:
                return []
            rows = con.execute(sql, values).fetchall()
        finally:
            con.close()
        return [dict(zip(row.keys(), row, strict=True)) for row in rows]

    def connect_duckdb(self) -> DuckDBPyConnection:
        """Return a DuckDB connection with the SQLite store attached (read-only).

        Enables unified SQL across every log table at once (e.g. join ``api_logs``
        with ``performance_logs`` by timestamp). Caller owns closing the connection.
        """
        import duckdb

        con = duckdb.connect()
        con.execute("INSTALL sqlite; LOAD sqlite;")
        con.execute(
            f"ATTACH '{self._config.db_path.as_posix()}' AS logs_db (TYPE sqlite, READ_ONLY)"
        )
        con.execute("USE logs_db")
        return con

    @property
    def dropped(self) -> int:
        """Number of records dropped because the queue was full (backpressure)."""
        return self._dropped
