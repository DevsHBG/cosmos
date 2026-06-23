"""Unified ``/v1/logs`` collection: querying the polymorphic log store.

One collection over the three log tables (``job_logs``/``api_logs``/
``performance_logs``); ``type`` is the discriminator filter (omitted = all). Results
are **keyset-paginated** by the total order ``(ts, type, rowid)``, so a growing time
series paginates with stable, constant-cost cursors and no offset drift (see
``docs/arquitectura-restful.md`` §10-11, §18.2).

The cursor is an opaque base64 token wrapping that order key. Because the kinds live
in separate tables, an "all types" query reads each relevant table past the cursor
and k-way merges the results; a single ``type`` reduces to one table.
"""

from __future__ import annotations

import base64
import binascii
import json
from datetime import datetime
from typing import Any, Literal, cast

from pydantic import BaseModel

from pulsar.api.problem import ProblemException
from pulsar.api.schemas import ApiLogItem, JobLogItem, LogItemModel, PerformanceLogItem
from pulsar.logger import log

#: The discriminator values accepted by ``?type=``.
LogType = Literal["job", "api", "performance"]

#: ``type`` → (table/KIND, item model). Tuple order defines the global tiebreak rank.
_TYPES: tuple[tuple[LogType, str, type[BaseModel]], ...] = (
    ("job", "job_logs", JobLogItem),
    ("api", "api_logs", ApiLogItem),
    ("performance", "performance_logs", PerformanceLogItem),
)
_TABLE: dict[LogType, str] = {t: table for t, table, _ in _TYPES}
_MODEL: dict[LogType, type[BaseModel]] = {t: model for t, _, model in _TYPES}
_RANK: dict[LogType, int] = {t: i for i, (t, _, _) in enumerate(_TYPES)}
_BY_RANK: tuple[LogType, ...] = tuple(t for t, _, _ in _TYPES)
#: Kinds that carry a ``status`` column (``performance`` has none).
_HAS_STATUS: frozenset[LogType] = frozenset({"job", "api"})


def _encode_cursor(ts: str, type_: LogType, rowid: int) -> str:
    """Pack a sort-key position into an opaque cursor token."""
    raw = json.dumps({"ts": ts, "type": type_, "rowid": rowid}, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[str, LogType, int]:
    """Unpack a cursor token; raise a 400 problem if it is malformed."""
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        type_ = data["type"]
        if type_ not in _RANK:
            raise ValueError(type_)
        return str(data["ts"]), type_, int(data["rowid"])
    except (binascii.Error, ValueError, KeyError, TypeError) as exc:
        raise ProblemException(
            400,
            "Invalid cursor",
            detail="The 'cursor' parameter is not a valid pagination token.",
            type_slug="invalid-cursor",
        ) from exc


def _parse_sort(sort: str) -> bool:
    """Return ``descending`` for the ``sort`` value; raise a 400 problem if unsupported."""
    if sort in ("-ts", ""):
        return True
    if sort == "ts":
        return False
    raise ProblemException(
        400,
        "Invalid sort",
        detail="Only 'ts' (ascending) and '-ts' (descending) are supported for 'sort'.",
        type_slug="invalid-sort",
    )


def _keyset(
    rank: int, cur_ts: str, cur_rank: int, cur_rowid: int, descending: bool
) -> tuple[str, list[Any]]:
    """Build the "strictly after the cursor" predicate for one table.

    The global order is ``ts`` (in ``descending`` direction), then ``type`` rank
    ascending, then ``rowid`` (same direction). At an equal ``ts`` a whole table sorts
    after the cursor only when its rank is greater than the cursor's.
    """
    op = "<" if descending else ">"
    if rank == cur_rank:
        return f"(ts {op} ? OR (ts = ? AND rowid {op} ?))", [cur_ts, cur_ts, cur_rowid]
    if rank > cur_rank:
        return f"(ts {op}= ?)", [cur_ts]
    return f"(ts {op} ?)", [cur_ts]


def query_logs(
    *,
    type_: LogType | None = None,
    status: str | None = None,
    level: str | None = None,
    correlation_id: str | None = None,
    job: str | None = None,
    path: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    sort: str = "-ts",
    limit: int = 100,
    cursor: str | None = None,
) -> tuple[list[LogItemModel], str | None]:
    """Query the unified logs collection, returning ``(items, next_cursor)``.

    Filters that only exist on some kinds narrow the queried tables: ``status``
    excludes ``performance``; ``job`` keeps only ``job``; ``path`` keeps only ``api``.
    """
    descending = _parse_sort(sort)
    types: list[LogType] = [type_] if type_ is not None else list(_BY_RANK)
    if status is not None:
        types = [t for t in types if t in _HAS_STATUS]
    if job is not None:
        types = [t for t in types if t == "job"]
    if path is not None:
        types = [t for t in types if t == "api"]

    cur = _decode_cursor(cursor) if cursor else None
    cur_rank = _RANK[cur[1]] if cur else 0

    # (ts, rank, rowid, item) for every candidate row across the queried tables.
    candidates: list[tuple[str, int, int, LogItemModel]] = []
    for t in types:
        where_parts: list[str] = []
        params: list[Any] = []
        if cur is not None:
            clause, values = _keyset(_RANK[t], cur[0], cur_rank, cur[2], descending)
            where_parts.append(clause)
            params.extend(values)
        if level is not None:
            where_parts.append("level = ?")
            params.append(level)
        if correlation_id is not None:
            where_parts.append("correlation_id = ?")
            params.append(correlation_id)
        if status is not None:
            where_parts.append("status = ?")
            params.append(status)
        if job is not None:
            where_parts.append("job = ?")
            params.append(job)
        if path is not None:
            where_parts.append("path = ?")
            params.append(path)

        rows = log.query(
            _TABLE[t],
            since=since,
            until=until,
            where=" AND ".join(where_parts) or None,
            params=tuple(params),
            order_by="ts",
            descending=descending,
            limit=limit + 1,  # one extra row tells us whether a next page exists
            include_rowid=True,
        )
        model = _MODEL[t]
        for row in rows:
            item = cast(LogItemModel, model(**{k: v for k, v in row.items() if k != "_rowid"}))
            candidates.append((str(row["ts"]), _RANK[t], int(row["_rowid"]), item))

    # Merge into the global order via stable sorts applied least-significant first.
    candidates.sort(key=lambda c: c[2], reverse=descending)  # rowid
    candidates.sort(key=lambda c: c[1])  # type rank (always ascending)
    candidates.sort(key=lambda c: c[0], reverse=descending)  # ts

    page = candidates[:limit]
    items = [c[3] for c in page]
    next_cursor: str | None = None
    if len(candidates) > limit and page:
        ts, rank, rowid, _ = page[-1]
        next_cursor = _encode_cursor(ts, _BY_RANK[rank], rowid)
    return items, next_cursor
