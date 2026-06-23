"""Sinks: where records land. Abstract base + a SQLite implementation.

A sink knows how to create its schema and write a batch of records. ``SqliteSink``
derives its columns generically from the record type's Pydantic fields, so adding
a new record type needs no sink changes — just a registration.
"""

from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path
from typing import Any, get_args

from pulsar.logger.records import LogRecord


class Sink(ABC):
    """A destination for log records."""

    @abstractmethod
    def ensure_schema(self) -> None:
        """Create the backing storage if it does not exist (idempotent)."""

    @abstractmethod
    def write(self, records: Sequence[LogRecord]) -> None:
        """Persist a batch of records (all of the sink's record type)."""


class SqliteSink(Sink):
    """Append-only SQLite table for one record type (WAL, batched inserts).

    Columns are derived from the record type's fields; ``dict``/``list`` values are
    stored as JSON text and ``datetime`` as ISO-8601 text (both readable by DuckDB).
    """

    def __init__(self, db_path: Path, table: str, record_type: type[LogRecord]) -> None:
        self._db_path = db_path
        self._table = table
        self._record_type = record_type
        self._columns: tuple[str, ...] = tuple(record_type.model_fields)

    def _connect(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self._db_path)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        return con

    def ensure_schema(self) -> None:
        cols = ", ".join(f'"{c}" {self._affinity(c)}' for c in self._columns)
        with closing(self._connect()) as con, con:
            con.execute(f'CREATE TABLE IF NOT EXISTS "{self._table}" ({cols})')
            con.execute(f'CREATE INDEX IF NOT EXISTS "{self._table}_ts" ON "{self._table}" (ts)')
            if "job" in self._columns:
                con.execute(
                    f'CREATE INDEX IF NOT EXISTS "{self._table}_job_ts" '
                    f'ON "{self._table}" (job, ts)'
                )
            if "correlation_id" in self._columns:
                con.execute(
                    f'CREATE INDEX IF NOT EXISTS "{self._table}_cid" '
                    f'ON "{self._table}" (correlation_id)'
                )

    def write(self, records: Sequence[LogRecord]) -> None:
        if not records:
            return
        cols = ", ".join(f'"{c}"' for c in self._columns)
        placeholders = ", ".join("?" for _ in self._columns)
        sql = f'INSERT INTO "{self._table}" ({cols}) VALUES ({placeholders})'
        rows = [self._row(record) for record in records]
        with closing(self._connect()) as con, con:
            con.executemany(sql, rows)

    def _row(self, record: LogRecord) -> tuple[Any, ...]:
        data = record.model_dump(mode="json")
        return tuple(self._cell(data.get(column)) for column in self._columns)

    @staticmethod
    def _cell(value: Any) -> Any:
        if isinstance(value, dict | list):
            return json.dumps(value, ensure_ascii=False)
        return value

    def _affinity(self, column: str) -> str:
        annotation = self._record_type.model_fields[column].annotation
        args = [a for a in get_args(annotation) if a is not type(None)]
        base = args[0] if args else annotation
        if base in (bool, int):
            return "INTEGER"
        if base is float:
            return "REAL"
        return "TEXT"
