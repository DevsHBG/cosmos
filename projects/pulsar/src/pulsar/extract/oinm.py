"""Incremental extraction of inventory movements from SAP ``OINM``.

``OINM`` (Whse Journal) is the immutable inventory-movement ledger in SAP B1:
one row per posting line, with ``InQty``/``OutQty``, warehouse, dates and the
source-document link. The point-in-time inventory at any date is the running
sum of these movements (validated: reconstruction == ``OITW`` current stock).

The incremental watermark is ``CreateDate`` (capture date), NOT ``DocDate``,
so back-dated documents are not missed (ADR-0002 §4). ``DocDate`` is preserved
as the business-effective date.
"""

from __future__ import annotations

from datetime import date

import polars as pl

from pulsar.config.hana import hana_connection
from pulsar.config.settings import Company, get_hana_settings

# Column order of the ledger frame this module produces.
LEDGER_COLUMNS: tuple[str, ...] = (
    "mov_id",
    "company",
    "item_code",
    "warehouse",
    "doc_date",
    "create_date",
    "trans_type",
    "base_entry",
    "base_num",
    "doc_line",
    "in_qty",
    "out_qty",
    "trans_value",
)


def build_oinm_query(schema: str) -> str:
    """Build the incremental OINM extraction SQL for one schema.

    Args:
        schema: HANA schema (company database) name, e.g. ``"HBG_THR"``.

    Returns:
        SQL with two positional params: ``since`` (inclusive) and ``until``
        (exclusive), both compared against ``CreateDate``.

    Note:
        Column names (``CreatedBy`` as the source ``DocEntry``, ``BASE_REF``,
        ``DocLineNum``, ``TransValue``) follow standard SAP B1; confirm against
        the live schema if any column raises an error.
    """
    return f"""
        SELECT
            M."ItemCode"                 AS "item_code",
            M."Warehouse"                AS "warehouse",
            CAST(M."DocDate"   AS DATE)  AS "doc_date",
            CAST(M."CreateDate" AS DATE) AS "create_date",
            M."TransType"                AS "trans_type",
            M."CreatedBy"                AS "base_entry",
            M."BASE_REF"                 AS "base_num",
            M."DocLineNum"               AS "doc_line",
            M."InQty"                    AS "in_qty",
            M."OutQty"                   AS "out_qty",
            M."TransValue"               AS "trans_value"
        FROM "{schema}"."OINM" M
        WHERE M."CreateDate" >= ?
          AND M."CreateDate" <  ?
    """


def finalize_oinm_frame(df: pl.DataFrame, company: Company) -> pl.DataFrame:
    """Type-cast a raw OINM frame, add ``company`` and a surrogate ``mov_id``.

    ``mov_id`` is a deterministic hash over the natural key. It is an audit
    convenience only; idempotency of loads relies on the create-date window
    replace strategy (see :mod:`pulsar.ledger.movimientos`), not on ``mov_id``.

    Args:
        df: Raw frame as returned by the OINM query (one row per posting line).
        company: The company the rows belong to.

    Returns:
        A frame with the columns of :data:`LEDGER_COLUMNS`.
    """
    typed = df.with_columns(
        pl.col("item_code").cast(pl.Utf8),
        pl.col("warehouse").cast(pl.Utf8),
        pl.col("doc_date").cast(pl.Date),
        pl.col("create_date").cast(pl.Date),
        pl.col("trans_type").cast(pl.Int64, strict=False),
        pl.col("base_entry").cast(pl.Int64, strict=False),
        pl.col("base_num").cast(pl.Int64, strict=False),
        pl.col("doc_line").cast(pl.Int64, strict=False),
        pl.col("in_qty").cast(pl.Float64, strict=False),
        pl.col("out_qty").cast(pl.Float64, strict=False),
        pl.col("trans_value").cast(pl.Float64, strict=False),
    ).with_columns(pl.lit(company.value).alias("company"))

    natural_key = pl.concat_str(
        [
            pl.col("company"),
            pl.col("trans_type").cast(pl.Utf8),
            pl.col("base_entry").cast(pl.Utf8),
            pl.col("doc_line").cast(pl.Utf8),
            pl.col("item_code"),
            pl.col("warehouse"),
        ],
        separator="|",
        ignore_nulls=False,
    )
    return typed.with_columns(natural_key.hash().alias("mov_id")).select(LEDGER_COLUMNS)


def fetch_oinm(company: Company, *, since: date, until: date) -> pl.DataFrame:
    """Fetch OINM movements for a company in the ``[since, until)`` window.

    Args:
        company: Company to extract.
        since: Inclusive lower bound on ``CreateDate``.
        until: Exclusive upper bound on ``CreateDate``.

    Returns:
        A finalized ledger frame (columns of :data:`LEDGER_COLUMNS`); empty if
        no movements were captured in the window.
    """
    schema = get_hana_settings().schema_for(company)
    sql = build_oinm_query(schema)
    with hana_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute(sql, [since.isoformat(), until.isoformat()])
            columns = [d[0] for d in cur.description]
            rows = cur.fetchall()
        finally:
            cur.close()

    if not rows:
        return pl.DataFrame(schema={c: pl.Utf8 for c in LEDGER_COLUMNS}).clear()
    raw = pl.DataFrame(rows, schema=columns, orient="row")
    return finalize_oinm_frame(raw, company)
