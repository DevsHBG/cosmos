"""Extraction of current stock from SAP ``OITW`` (per warehouse, per item).

Used as the source of truth for the golden validation: the ledger
reconstruction (running sum of OINM) must equal ``OITW.OnHand`` today.
"""

from __future__ import annotations

import polars as pl

from pulsar.config.hana import hana_connection
from pulsar.config.settings import Company, get_hana_settings

_OITW_COLUMNS: tuple[str, ...] = ("item_code", "warehouse", "qty_sap")


def build_oitw_query(schema: str) -> str:
    """Build the current-stock query for one schema.

    Args:
        schema: HANA schema (company database) name.

    Returns:
        SQL selecting current on-hand per (item, warehouse).
    """
    return f"""
        SELECT
            W."ItemCode" AS "item_code",
            W."WhsCode"  AS "warehouse",
            W."OnHand"   AS "qty_sap"
        FROM "{schema}"."OITW" W
    """


def fetch_oitw(company: Company) -> pl.DataFrame:
    """Fetch current on-hand per (item, warehouse) for a company.

    Args:
        company: Company to extract.

    Returns:
        Frame with columns ``item_code``, ``warehouse``, ``qty_sap``.
    """
    schema = get_hana_settings().schema_for(company)
    with hana_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute(build_oitw_query(schema))
            columns = [d[0] for d in cur.description]
            rows = cur.fetchall()
        finally:
            cur.close()

    if not rows:
        return pl.DataFrame(schema={c: pl.Utf8 for c in _OITW_COLUMNS}).clear()
    return pl.DataFrame(rows, schema=columns, orient="row").with_columns(
        pl.col("item_code").cast(pl.Utf8),
        pl.col("warehouse").cast(pl.Utf8),
        pl.col("qty_sap").cast(pl.Float64, strict=False),
    )
