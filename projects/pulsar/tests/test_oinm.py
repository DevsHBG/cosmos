"""Pure tests for OINM extraction logic (no HANA connection required)."""

from __future__ import annotations

from datetime import datetime

import polars as pl

from pulsar.config.settings import Company
from pulsar.extract.oinm import LEDGER_COLUMNS, build_oinm_query, finalize_oinm_frame


def test_build_oinm_query_targets_schema_and_has_two_params() -> None:
    sql = build_oinm_query("HBG_THR")
    assert '"HBG_THR"."OINM"' in sql
    assert sql.count("?") == 2  # since (inclusive), until (exclusive)


def _raw_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "item_code": ["0010324", "0010324"],
            "warehouse": ["A01", "A01"],
            "doc_date": ["2024-03-15", "2024-03-16"],
            "doc_time": [1430, 905],  # HHMM: 14:30 and 09:05
            "create_date": ["2024-03-15", "2024-03-16"],
            "trans_type": [15, 20],
            "base_entry": [1001, 1002],
            "base_num": [5001, 5002],
            "doc_line": [0, 0],
            "in_qty": [0.0, 10.0],
            "out_qty": [3.0, 0.0],
            "trans_value": [0.0, 100.0],
        }
    )


def test_finalize_adds_company_and_mov_id_with_expected_columns() -> None:
    out = finalize_oinm_frame(_raw_frame(), Company.HR)
    assert tuple(out.columns) == LEDGER_COLUMNS
    assert out["company"].to_list() == ["HR", "HR"]
    assert out["doc_date"].dtype == pl.Date
    assert out["mov_id"].null_count() == 0


def test_finalize_combines_doc_date_and_doc_time_into_doc_ts() -> None:
    out = finalize_oinm_frame(_raw_frame(), Company.HR)
    assert out["doc_time"].dtype == pl.Int16
    assert out["doc_time"].to_list() == [1430, 905]
    assert out["doc_ts"].dtype == pl.Datetime
    assert out["doc_ts"].to_list() == [
        datetime(2024, 3, 15, 14, 30),
        datetime(2024, 3, 16, 9, 5),
    ]


def test_finalize_mov_id_is_deterministic() -> None:
    a = finalize_oinm_frame(_raw_frame(), Company.HR)
    b = finalize_oinm_frame(_raw_frame(), Company.HR)
    assert a["mov_id"].to_list() == b["mov_id"].to_list()
