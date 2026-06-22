"""Build and incrementally sync the immutable movements journal.

Idempotency strategy: **bounded create-date window replace**. Each load pulls a
``[since, until)`` window from HANA (the source of truth) and replaces exactly
that window in the table (``DELETE`` + ``INSERT``). Correct regardless of OINM's
exact primary key and robust to back-dated rows, because HANA — not the table —
owns the truth for the window being refreshed.

Backfill is **chunked by retail year** (see :mod:`pulsar.retail.calendar`) so
every query is bounded and each window mirrors the table's ``retail_year``
partition; the daily incremental load is a single small window. The underlying
OINM query is a plain indexed range scan (no joins, no correlated subqueries),
so per-query load on HANA is light.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING

from pulsar.config.settings import Company
from pulsar.model.movements.schema import MOVEMENTS_TABLE, ensure_schema
from pulsar.retail.calendar import from_date, retail_year_start
from pulsar.sources.oinm import MOVEMENT_COLUMNS, fetch_oinm
from pulsar.storage.lake import open_lake

if TYPE_CHECKING:
    import polars as pl
    from duckdb import DuckDBPyConnection

# Earliest movement to consider on a first (empty) load. SAP data starts ~2019;
# starting from inception yields a correct opening balance (ADR-0002).
FLOOR_DATE = date(2019, 1, 1)


def current_watermark(con: DuckDBPyConnection, company: Company) -> date | None:
    """Return the latest ``create_date`` loaded for a company.

    Args:
        con: An open lakehouse connection.
        company: Company to look up.

    Returns:
        The max ``create_date`` for the company, or ``None`` if it has no rows.
    """
    row = con.execute(
        f"SELECT MAX(create_date) FROM {MOVEMENTS_TABLE} WHERE company = ?",
        [company.value],
    ).fetchone()
    return row[0] if row is not None else None


def _iter_retail_year_windows(start: date, end: date) -> Iterator[tuple[date, date]]:
    """Yield ``[from, to)`` windows aligned to retail-year boundaries.

    Each interior window spans exactly one retail year (see
    :mod:`pulsar.retail.calendar`); the first starts at ``start`` and the last is
    clipped to ``end``. Chunking the backfill this way keeps every HANA query
    bounded and mirrors the table's ``retail_year`` partition layout.

    Args:
        start: Inclusive start date.
        end: Exclusive end date.

    Yields:
        Half-open ``(from, to)`` windows; interior boundaries are retail-year
        starts (Sundays).
    """
    if start >= end:
        return
    cur = start
    while cur < end:
        nxt = retail_year_start(from_date(cur).year + 1)
        yield cur, min(nxt, end)
        cur = nxt


def _replace_window(
    con: DuckDBPyConnection,
    company: Company,
    frame: pl.DataFrame,
    *,
    since: date,
    until: date,
) -> int:
    """Replace exactly the ``[since, until)`` window for a company.

    Only touches the table when ``frame`` has rows, so an empty pull never
    deletes existing data.

    Args:
        con: An open lakehouse connection.
        company: Company being loaded.
        frame: Finalized movements frame for the window.
        since: Inclusive lower bound on ``create_date``.
        until: Exclusive upper bound on ``create_date``.

    Returns:
        Number of rows written.
    """
    if frame.is_empty():
        return 0
    cols = ", ".join(MOVEMENT_COLUMNS)
    con.register("incoming", frame.select(MOVEMENT_COLUMNS))
    try:
        con.execute(
            f"DELETE FROM {MOVEMENTS_TABLE} "
            f"WHERE company = ? AND create_date >= ? AND create_date < ?",
            [company.value, since, until],
        )
        con.execute(f"INSERT INTO {MOVEMENTS_TABLE} ({cols}) SELECT {cols} FROM incoming")
    finally:
        con.unregister("incoming")
    return frame.height


def sync_company(
    company: Company,
    *,
    catalog_path: Path,
    data_path: Path,
    since: date | None = None,
    until: date | None = None,
) -> int:
    """Incrementally sync one company's movements into the table.

    Resumes from the company's watermark (re-pulling the last captured day to
    absorb same-day additions). For the initial historical load use
    :func:`backfill_company`, which chunks the pull by month.

    Args:
        company: Company to sync.
        catalog_path: SQLite catalog path for the lakehouse.
        data_path: Parquet data directory for the lakehouse.
        since: Inclusive lower bound on ``create_date``; defaults to the
            watermark (or :data:`FLOOR_DATE` on first load).
        until: Exclusive upper bound; defaults to tomorrow.

    Returns:
        Number of rows written for the window.
    """
    until = until or (date.today() + timedelta(days=1))
    con = open_lake(catalog_path, data_path)
    try:
        ensure_schema(con)
        effective_since = (
            since if since is not None else (current_watermark(con, company) or FLOOR_DATE)
        )
        frame = fetch_oinm(company, since=effective_since, until=until)
        return _replace_window(con, company, frame, since=effective_since, until=until)
    finally:
        con.close()


def backfill_company(
    company: Company,
    *,
    catalog_path: Path,
    data_path: Path,
    start: date = FLOOR_DATE,
    end: date | None = None,
) -> int:
    """Historical backfill in bounded retail-year windows (one query each).

    Each window is an indexed range scan over OINM and is replaced atomically,
    making the backfill resumable: re-running re-loads windows idempotently.
    Windows align to retail-year boundaries (see :mod:`pulsar.retail.calendar`),
    mirroring the table's ``retail_year`` partition.

    Args:
        company: Company to backfill.
        catalog_path: SQLite catalog path for the lakehouse.
        data_path: Parquet data directory for the lakehouse.
        start: Inclusive start date (default :data:`FLOOR_DATE`).
        end: Exclusive end date (default tomorrow).

    Returns:
        Total number of rows written across all windows.
    """
    end = end or (date.today() + timedelta(days=1))
    con = open_lake(catalog_path, data_path)
    try:
        ensure_schema(con)
        total = 0
        for win_start, win_end in _iter_retail_year_windows(start, end):
            t0 = perf_counter()
            frame = fetch_oinm(company, since=win_start, until=win_end)
            rows = _replace_window(con, company, frame, since=win_start, until=win_end)
            elapsed = perf_counter() - t0
            print(
                f"[backfill] {company.value} {win_start.isoformat()}..{win_end.isoformat()}: "
                f"{rows} rows in {elapsed:.1f}s"
            )
            total += rows
        return total
    finally:
        con.close()
