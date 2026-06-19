"""DuckLake store: attach a DuckLake lakehouse with a SQLite catalog.

DuckLake (ADR-0002 §9) gives ACID, time-travel and schema evolution over
Parquet. The catalog lives in a local SQLite file (zero extra infrastructure);
data files live under ``data_path``. Migratable to Postgres later.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection

LAKE_ALIAS = "lake"


def open_lake(catalog_path: Path, data_path: Path) -> DuckDBPyConnection:
    """Open a DuckDB connection with a DuckLake lakehouse attached.

    Args:
        catalog_path: Path to the SQLite catalog file (created if missing).
        data_path: Directory for Parquet data files (created if missing).

    Returns:
        A connection with the lakehouse attached and selected as current.
    """
    import duckdb

    data_path.mkdir(parents=True, exist_ok=True)
    catalog_path.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    con.execute("INSTALL ducklake; LOAD ducklake;")
    con.execute("INSTALL sqlite; LOAD sqlite;")
    con.execute(
        f"ATTACH 'ducklake:sqlite:{catalog_path.as_posix()}' AS {LAKE_ALIAS} "
        f"(DATA_PATH '{data_path.as_posix()}/')"
    )
    con.execute(f"USE {LAKE_ALIAS}")
    return con
