"""Build and validate the movements table: load OINM, then the golden check.

Usage:
    # Initial historical load (chunked by retail year), then validate:
    python -m pulsar.jobs.build_movements HR --backfill
    # Backfill every company up to (excluding) a date, e.g. through yesterday:
    python -m pulsar.jobs.build_movements ALL --backfill --until 2026-06-18
    # Daily incremental sync of every company, then validate:
    python -m pulsar.jobs.build_movements ALL
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from pulsar.config.settings import Company
from pulsar.model.movements.build import backfill_company, sync_company
from pulsar.model.movements.validate import reconcile_company
from pulsar.storage.lake import open_lake

DEFAULT_CATALOG = Path("lake/catalog.sqlite")
DEFAULT_DATA = Path("lake/data")


def run(
    company: Company,
    *,
    catalog_path: Path = DEFAULT_CATALOG,
    data_path: Path = DEFAULT_DATA,
    backfill: bool = False,
    since: date | None = None,
    until: date | None = None,
) -> int:
    """Load one company (incremental or chunked backfill), then validate.

    Args:
        company: Company to process.
        catalog_path: SQLite catalog path for the lakehouse.
        data_path: Parquet data directory for the lakehouse.
        backfill: If true, run the chunked historical backfill; otherwise a
            single incremental sync from the watermark.
        since: For incremental mode, optional inclusive lower bound; for
            backfill mode, the start date.
        until: Exclusive upper bound (end). Defaults to tomorrow, so passing
            today loads through yesterday.

    Returns:
        Process exit code: ``0`` if the reconstruction matches (🟢), ``1`` if
        there are mismatches (🔴).
    """
    if backfill:
        start = since or date(2019, 1, 1)
        rows = backfill_company(
            company,
            catalog_path=catalog_path,
            data_path=data_path,
            start=start,
            end=until,
        )
    else:
        rows = sync_company(
            company, catalog_path=catalog_path, data_path=data_path, since=since, until=until
        )
    print(f"[movements] {company.value}: {rows} rows written")

    con = open_lake(catalog_path, data_path)
    try:
        mismatches = reconcile_company(con, company)
    finally:
        con.close()

    if mismatches.is_empty():
        print(f"[validate] {company.value}: 🟢 reconstruction matches OITW (Diff = 0)")
        return 0

    print(f"[validate] {company.value}: 🔴 {mismatches.height} mismatched (item, warehouse) pairs")
    print(mismatches.head(20))
    return 1


def main() -> int:
    """Parse CLI args and run the foundation pipeline for one or all companies.

    Returns:
        Process exit code: ``0`` only if every processed company validates.
    """
    # Force UTF-8 stdout so the 🟢/🔴 markers and polars tables never crash on a
    # legacy Windows console (cp1252). Harmless on other platforms.
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Load the movements table and validate it.")
    parser.add_argument(
        "company",
        choices=[*(c.value for c in Company), "ALL"],
        help="Company to process, or ALL for every company.",
    )
    parser.add_argument("--backfill", action="store_true", help="Chunked historical load.")
    parser.add_argument(
        "--since", type=date.fromisoformat, default=None, help="YYYY-MM-DD lower bound / start."
    )
    parser.add_argument(
        "--until",
        type=date.fromisoformat,
        default=None,
        help="YYYY-MM-DD exclusive upper bound (end); defaults to tomorrow.",
    )
    parser.add_argument(
        "--catalog", type=Path, default=DEFAULT_CATALOG, help="SQLite catalog path."
    )
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="Parquet data directory.")
    args = parser.parse_args()

    companies = list(Company) if args.company == "ALL" else [Company(args.company)]
    exit_code = 0
    for company in companies:
        exit_code = max(
            exit_code,
            run(
                company,
                catalog_path=args.catalog,
                data_path=args.data,
                backfill=args.backfill,
                since=args.since,
                until=args.until,
            ),
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
