"""Phase-1 foundation runner: sync the ledger and run the golden validation.

Usage:
    python -m pulsar.pipeline.foundation HR
    python -m pulsar.pipeline.foundation HR --since 2019-01-01
    python -m pulsar.pipeline.foundation HR --catalog ./lake/catalog.sqlite --data ./lake/data
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from pulsar.config.settings import Company
from pulsar.ledger.movimientos import sync_company
from pulsar.ledger.reconcile import reconcile_company
from pulsar.ledger.store import open_lake

DEFAULT_CATALOG = Path("lake/catalog.sqlite")
DEFAULT_DATA = Path("lake/data")


def run(
    company: Company,
    *,
    catalog_path: Path = DEFAULT_CATALOG,
    data_path: Path = DEFAULT_DATA,
    since: date | None = None,
) -> int:
    """Sync one company then validate the reconstruction against ``OITW``.

    Args:
        company: Company to process.
        catalog_path: SQLite catalog path for the lakehouse.
        data_path: Parquet data directory for the lakehouse.
        since: Optional inclusive lower bound on ``CreateDate``.

    Returns:
        Process exit code: ``0`` if the reconstruction matches (🟢), ``1`` if
        there are mismatches (🔴).
    """
    rows = sync_company(company, catalog_path=catalog_path, data_path=data_path, since=since)
    print(f"[ledger] {company.value}: {rows} rows written")

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
    """Parse CLI args and run the foundation pipeline.

    Returns:
        Process exit code from :func:`run`.
    """
    parser = argparse.ArgumentParser(description="Sync the movement ledger and validate it.")
    parser.add_argument("company", choices=[c.value for c in Company], help="Company to process.")
    parser.add_argument(
        "--since", type=date.fromisoformat, default=None, help="YYYY-MM-DD lower bound."
    )
    parser.add_argument(
        "--catalog", type=Path, default=DEFAULT_CATALOG, help="SQLite catalog path."
    )
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="Parquet data directory.")
    args = parser.parse_args()

    return run(
        Company(args.company),
        catalog_path=args.catalog,
        data_path=args.data,
        since=args.since,
    )


if __name__ == "__main__":
    raise SystemExit(main())
