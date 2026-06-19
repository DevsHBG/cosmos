"""Schema (DDL) for the movements ledger table (``ledger_movements``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection

LEDGER_TABLE = "ledger_movements"

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
