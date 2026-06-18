"""Golden validation: ledger reconstruction vs SAP ``OITW`` current stock.

If the running sum of OINM movements equals current on-hand for every
(item, warehouse), the reconstruction is trustworthy (ADR-0002). This is the
permanent regression test of the foundation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import polars as pl

from pulsar.config.settings import Company
from pulsar.extract.oitw import fetch_oitw
from pulsar.ledger.movimientos import LEDGER_TABLE

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection


def reconcile_company(
    con: DuckDBPyConnection,
    company: Company,
    *,
    tolerance: float = 1e-3,
) -> pl.DataFrame:
    """Compare ledger-reconstructed stock against ``OITW`` for a company.

    Args:
        con: An open lakehouse connection holding the ledger.
        company: Company to validate.
        tolerance: Absolute difference treated as a match (handles fractional
            rounding).

    Returns:
        Frame of mismatches with columns ``item_code``, ``warehouse``,
        ``qty_recon``, ``qty_sap``, ``diff`` (empty frame == 🟢 camino libre).
    """
    recon = con.execute(
        f"""
        SELECT item_code, warehouse, SUM(in_qty - out_qty) AS qty_recon
        FROM {LEDGER_TABLE}
        WHERE company = ?
        GROUP BY item_code, warehouse
        """,
        [company.value],
    ).pl()

    sap = fetch_oitw(company)

    joined = recon.join(sap, on=["item_code", "warehouse"], how="full", coalesce=True)
    diffed = joined.with_columns(
        (pl.col("qty_recon").fill_null(0.0) - pl.col("qty_sap").fill_null(0.0)).alias("diff")
    )
    return diffed.filter(pl.col("diff").abs() > tolerance).sort("diff", descending=True)
