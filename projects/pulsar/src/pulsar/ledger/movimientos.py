"""Build and incrementally sync the immutable movement ledger.

Idempotency strategy: **create-date window replace**. Each sync pulls the full
``[since, until)`` window from HANA (the source of truth) and replaces that same
window in the ledger (``DELETE`` + ``INSERT``). This is correct regardless of
OINM's exact primary key and robust to back-dated rows, because HANA — not the
ledger — owns the truth for the window being refreshed.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from pulsar.config.settings import Company
from pulsar.extract.oinm import LEDGER_COLUMNS, fetch_oinm
from pulsar.ledger.store import open_lake

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection

LEDGER_TABLE = "ledger_movimientos"

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


def sync_company(
    company: Company,
    *,
    catalog_path: Path,
    data_path: Path,
    since: date | None = None,
    until: date | None = None,
) -> int:
    """Sync one company's movements into the ledger.

    On an incremental run (``since`` omitted) it resumes from the company's
    watermark, re-pulling the last captured day to absorb same-day additions.

    Args:
        company: Company to sync.
        catalog_path: SQLite catalog path for the lakehouse.
        data_path: Parquet data directory for the lakehouse.
        since: Inclusive lower bound on ``CreateDate``; defaults to the
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
        if frame.is_empty():
            return 0

        # Window replace: delete the refreshed window, then insert the fresh pull.
        con.register("incoming", frame.select(LEDGER_COLUMNS))
        con.execute(
            f"DELETE FROM {LEDGER_TABLE} WHERE company = ? AND create_date >= ?",
            [company.value, effective_since],
        )
        cols = ", ".join(LEDGER_COLUMNS)
        con.execute(f"INSERT INTO {LEDGER_TABLE} ({cols}) SELECT {cols} FROM incoming")
        con.unregister("incoming")
        return frame.height
    finally:
        con.close()
