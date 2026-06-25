"""The job runs collection: reading the authoritative runs store as a resource.

A run is a first-class resource (``docs/arquitectura-restful.md`` §12/§18.3): its
lifecycle state lives in the runs store (:mod:`pulsar.jobs.runs`), which this module
reads back as a **keyset-paginated** collection ordered by ``(created_at, rowid)`` —
the same cursor scheme as the logs collection, so a growing series pages with
stable, constant-cost cursors and no offset drift.

The cursor is an opaque base64 token wrapping that order key.
"""

from __future__ import annotations

import base64
import binascii
import json
from datetime import datetime

from pulsar.api.problem import ProblemException
from pulsar.api.schemas import RunItem
from pulsar.jobs.runs import Run, run_store


def run_to_item(run: Run) -> RunItem:
    """Map a stored :class:`Run` to its API representation."""
    return RunItem(
        id=run.id,
        job=run.job,
        status=run.status,
        trigger=run.trigger,
        rows=run.rows,
        detail=run.detail,
        correlation_id=run.correlation_id,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        duration_s=run.duration_s,
    )


def _encode_cursor(created_at: str, rowid: int) -> str:
    """Pack a sort-key position into an opaque cursor token."""
    raw = json.dumps({"created_at": created_at, "rowid": rowid}, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[str, int]:
    """Unpack a cursor token; raise a 400 problem if it is malformed."""
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return str(data["created_at"]), int(data["rowid"])
    except (binascii.Error, ValueError, KeyError, TypeError) as exc:
        raise ProblemException(
            400,
            "Invalid cursor",
            detail="The 'cursor' parameter is not a valid pagination token.",
            type_slug="invalid-cursor",
        ) from exc


def _parse_sort(sort: str) -> bool:
    """Return ``descending`` for the ``sort`` value; raise a 400 problem if unsupported."""
    if sort in ("-created_at", ""):
        return True
    if sort == "created_at":
        return False
    raise ProblemException(
        400,
        "Invalid sort",
        detail="Only 'created_at' (ascending) and '-created_at' (descending) are supported.",
        type_slug="invalid-sort",
    )


def query_runs(
    job: str,
    *,
    status: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    sort: str = "-created_at",
    limit: int = 100,
    cursor: str | None = None,
) -> tuple[list[RunItem], str | None]:
    """Query a job's runs collection, returning ``(items, next_cursor)``."""
    descending = _parse_sort(sort)
    after = _decode_cursor(cursor) if cursor else None
    rows = run_store.list(
        job,
        status=status,
        since=since,
        until=until,
        descending=descending,
        after=after,
        limit=limit + 1,  # one extra row tells us whether a next page exists
    )
    page = rows[:limit]
    items = [run_to_item(run) for run, _ in page]
    next_cursor: str | None = None
    if len(rows) > limit and page:
        last_run, last_rowid = page[-1]
        next_cursor = _encode_cursor(last_run.created_at.isoformat(), last_rowid)
    return items, next_cursor
