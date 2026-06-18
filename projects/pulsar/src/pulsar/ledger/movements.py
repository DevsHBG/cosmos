"""Build and incrementally sync the immutable movement ledger.

Idempotency strategy: **bounded create-date window replace**. Each load pulls a
``[since, until)`` window from HANA (the source of truth) and replaces exactly
that window in the ledger (``DELETE`` + ``INSERT``). Correct regardless of OINM's
exact primary key and robust to back-dated rows, because HANA — not the ledger —
owns the truth for the window being refreshed.

Backfill is **chunked by month** so every query is small and bounded (no single
massive transaction); the daily incremental load is a single small window. The
underlying OINM query is a plain indexed range scan (no joins, no correlated
subqueries), so per-query load on HANA is light.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING

from pulsar.config.settings import Company
from pulsar.extract.oinm import LEDGER_COLUMNS, fetch_oinm
from pulsar.ledger.store import open_lake

if TYPE_CHECKING:
    import polars as pl
    from duckdb import DuckDBPyConnection

LEDGER_TABLE = "ledger_movements"

# Earliest movement to consider on a first (empty) load. SAP data starts ~2019;
# starting from inception yields a correct opening balance (ADR-0002).
FLOOR_DATE = date(2019, 1, 1)

_CREATE_TABLE = f"""
    CREATE TABLE IF NOT EXISTS {LEDGER_TABLE} (
        mov_id       UBIGINT,
        company      VARCHAR,
        item_code    VARCHAR,
        warehouse    VARCHAR,
        doc_date     DATE,
        doc_time     SMALLINT,
        doc_ts       TIMESTAMP,
        create_date  DATE,
        trans_type   BIGINT,
        base_entry   BIGINT,
        base_num     BIGINT,
        doc_line     BIGINT,
        in_qty       DOUBLE,
        out_qty      DOUBLE,
        trans_value  DOUBLE
    )
"""


def ensure_schema(con: DuckDBPyConnection) -> None:
    """Create the ledger table if it does not exist.

    Args:
        con: An open lakehouse connection.
    """
    con.execute(_CREATE_TABLE)


def current_watermark(con: DuckDBPyConnection, company: Company) -> date | None:
    """Return the latest ``create_date`` loaded for a company.

    Args:
        con: An open lakehouse connection.
        company: Company to look up.

    Returns:
        The max ``create_date`` for the company, or ``None`` if it has no rows.
    """
    row = con.execute(
        f"SELECT MAX(create_date) FROM {LEDGER_TABLE} WHERE company = ?",
        [company.value],
    ).fetchone()
    return row[0] if row is not None else None


def _iter_month_windows(
    start: date, end: date, step_months: int = 1
) -> Iterator[tuple[date, date]]:
    """Yield ``[from, to)`` windows of ``step_months`` from ``start`` to ``end``.

    Args:
        start: Inclusive start date.
        end: Exclusive end date.
        step_months: Window size in months (default 1).

    Yields:
        Half-open ``(from, to)`` date windows; the last is clipped to ``end``.
    """
    if start >= end:
        return
    cur = start
    while cur < end:
        months = cur.month - 1 + step_months
        nxt = date(cur.year + months // 12, months % 12 + 1, 1)
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

    Only touches the ledger when ``frame`` has rows, so an empty pull never
    deletes existing data.

    Args:
        con: An open lakehouse connection.
        company: Company being loaded.
        frame: Finalized ledger frame for the window.
        since: Inclusive lower bound on ``create_date``.
        until: Exclusive upper bound on ``create_date``.

    Returns:
        Number of rows written.
    """
    if frame.is_empty():
        return 0
    cols = ", ".join(LEDGER_COLUMNS)
    con.register("incoming", frame.select(LEDGER_COLUMNS))
    try:
        con.execute(
            f"DELETE FROM {LEDGER_TABLE} "
            f"WHERE company = ? AND create_date >= ? AND create_date < ?",
            [company.value, since, until],
        )
        con.execute(f"INSERT INTO {LEDGER_TABLE} ({cols}) SELECT {cols} FROM incoming")
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
    """Incrementally sync one company's movements into the ledger.

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
    step_months: int = 1,
) -> int:
    """Historical backfill in bounded monthly windows (one small query each).

    Each window is an indexed range scan over OINM and is replaced atomically,
    making the backfill resumable: re-running re-loads windows idempotently.

    Args:
        company: Company to backfill.
        catalog_path: SQLite catalog path for the lakehouse.
        data_path: Parquet data directory for the lakehouse.
        start: Inclusive start date (default :data:`FLOOR_DATE`).
        end: Exclusive end date (default tomorrow).
        step_months: Window size in months (lower it if a month is too heavy).

    Returns:
        Total number of rows written across all windows.
    """
    end = end or (date.today() + timedelta(days=1))
    con = open_lake(catalog_path, data_path)
    try:
        ensure_schema(con)
        total = 0
        for win_start, win_end in _iter_month_windows(start, end, step_months):
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
