"""Schema (DDL) for the inventory movements table (``inventory.movements``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection

#: DuckLake schema (domain) and table for the movements journal. Each table gets
#: its own folder under the lake's data path: ``<data>/inventory/movements/``.
SCHEMA = "inventory"
TABLE = "movements"
#: Fully-qualified name used in all SQL against the lakehouse.
MOVEMENTS_TABLE = f"{SCHEMA}.{TABLE}"
#: Column the table is partitioned by: the retail year of ``doc_date``. DuckLake
#: writes one Hive folder per value: ``movements/retail_year=2025/``.
PARTITION_KEY = "retail_year"

_CREATE_TABLE = f"""
    CREATE TABLE IF NOT EXISTS {MOVEMENTS_TABLE} (
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
        trans_value  DOUBLE,
        retail_year  SMALLINT
    )
"""


def ensure_schema(con: DuckDBPyConnection) -> None:
    """Create the ``inventory`` schema and the partitioned ``movements`` table.

    Idempotent: the table is created only if missing, and partitioning is set
    only on first creation. DuckLake records a new partition spec on every
    ``SET PARTITIONED BY``, so re-issuing it on each run is avoided.

    Args:
        con: An open lakehouse connection.
    """
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    table_exists = con.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = ? AND table_name = ?",
        [SCHEMA, TABLE],
    ).fetchone()
    con.execute(_CREATE_TABLE)
    if table_exists is None:
        con.execute(f"ALTER TABLE {MOVEMENTS_TABLE} SET PARTITIONED BY ({PARTITION_KEY})")
