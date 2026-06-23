"""Movement jobs: incremental sync and historical backfill (each self-validates)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import ClassVar

from pulsar.config.settings import Company
from pulsar.jobs.core import Job, JobContext, register
from pulsar.model.movements.build import FLOOR_DATE, backfill_company, sync_company
from pulsar.model.movements.validate import reconcile_company
from pulsar.storage.lake import open_lake

#: Default target: every company.
ALL_COMPANIES: tuple[Company, ...] = tuple(Company)


def _validate(ctx: JobContext, companies: tuple[Company, ...]) -> None:
    """Run the golden check for each company; raise on the first mismatch."""
    con = open_lake(ctx.catalog_path, ctx.data_path)
    try:
        for company in companies:
            mismatches = reconcile_company(con, company)
            if not mismatches.is_empty():
                raise RuntimeError(
                    f"{company.value}: {mismatches.height} (item, warehouse) pairs differ from OITW"
                )
    finally:
        con.close()


@dataclass(frozen=True)
class SyncMovements(Job):
    """Incremental sync of movements from each company's watermark, then validate."""

    companies: tuple[Company, ...] = ALL_COMPANIES
    name: ClassVar[str] = "sync-movements"
    description: ClassVar[str] = "Incremental sync from each company's watermark, then validate."
    writes_lake: ClassVar[bool] = True

    def run(self, ctx: JobContext) -> int:
        total = 0
        for company in self.companies:
            total += sync_company(company, catalog_path=ctx.catalog_path, data_path=ctx.data_path)
        _validate(ctx, self.companies)
        return total


@dataclass(frozen=True)
class BackfillMovements(Job):
    """Chunked historical backfill (retail-year windows), then validate."""

    companies: tuple[Company, ...] = ALL_COMPANIES
    since: date | None = None
    until: date | None = None
    name: ClassVar[str] = "backfill-movements"
    description: ClassVar[str] = "Historical backfill in retail-year windows, then validate."
    writes_lake: ClassVar[bool] = True

    def run(self, ctx: JobContext) -> int:
        total = 0
        for company in self.companies:
            total += backfill_company(
                company,
                catalog_path=ctx.catalog_path,
                data_path=ctx.data_path,
                start=self.since or FLOOR_DATE,
                end=self.until,
            )
        _validate(ctx, self.companies)
        return total


# Register schedulable defaults (the scheduler/API run these by name; the CLI can
# build instances with custom params).
register(SyncMovements())
register(BackfillMovements())
