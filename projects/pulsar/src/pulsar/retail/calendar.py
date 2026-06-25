"""Retail (4-5-4) calendar, anchored on a single known week.

There is no generic "first Sunday of February" rule: the calendar is defined by
one anchor week and built purely by arithmetic from it, forwards and backwards.

Anchor:
    Retail year 2026, week 1 == Sunday 2026-02-01 .. Saturday 2026-02-07.

Business rules (invariants):
    * Every week runs Sunday -> Saturday.
    * Every retail year has exactly 52 weeks (364 days). There is never a 53rd
      week, so each year start is exactly 364 days after the previous one.
    * Periods ("months") follow the 4-5-4 pattern per quarter: 4, 5, 4 weeks.
    * Quarters are 13 weeks each: Q1 weeks 1-13, Q2 14-26, Q3 27-39, Q4 40-52.
    * A retail year is named after the Gregorian year of its first week (the year
      starting 2026-02-01 is retail year 2026).

Because the year is fixed at 364 days, the start date drifts ~1 day earlier each
Gregorian year. This is the intended consequence of the "always 52 weeks" rule
(we never insert a leap week to re-anchor).
"""

from __future__ import annotations

from datetime import date, timedelta

import polars as pl
from pydantic import BaseModel, ConfigDict

#: Alias for the ``date`` type, so the ``RetailDate.date`` field below can keep
#: its ergonomic name without shadowing the type in its own annotations.
_Date = date

# --- Anchor and structural constants ---------------------------------------

#: Retail year whose week 1 is pinned by :data:`ANCHOR_WEEK1_START`.
ANCHOR_YEAR = 2026
#: Sunday on which week 1 of :data:`ANCHOR_YEAR` starts.
ANCHOR_WEEK1_START = date(2026, 2, 1)

WEEKS_PER_YEAR = 52
DAYS_PER_WEEK = 7
DAYS_PER_YEAR = WEEKS_PER_YEAR * DAYS_PER_WEEK  # 364

#: Weeks per period (retail month), following the 4-5-4 pattern, periods 1..12.
PERIOD_WEEKS: tuple[int, ...] = (4, 5, 4, 4, 5, 4, 4, 5, 4, 4, 5, 4)

#: Conventional Gregorian-aligned names for the 12 retail periods. Period 1 is
#: February (the retail year starts in February); period 12 is January.
PERIOD_NAMES: tuple[str, ...] = (
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
    "January",
)

WEEKS_PER_QUARTER = WEEKS_PER_YEAR // 4  # 13


class RetailDate(BaseModel):
    """A Gregorian date resolved into its retail-calendar coordinates."""

    model_config = ConfigDict(frozen=True)

    date: _Date
    year: int  # retail year
    week: int  # 1..52
    period: int  # 1..12 (retail month)
    period_name: str  # e.g. "April" for period 3
    quarter: int  # 1..4
    day_of_week: int  # 1 = Sunday .. 7 = Saturday (retail week)
    week_start: _Date  # Sunday
    week_end: _Date  # Saturday


# --- Year-level helpers -----------------------------------------------------


def retail_year_start(year: int) -> date:
    """Return the Sunday on which the given retail year's week 1 starts.

    Args:
        year: Retail year.

    Returns:
        The start date (a Sunday).
    """
    return ANCHOR_WEEK1_START + timedelta(days=(year - ANCHOR_YEAR) * DAYS_PER_YEAR)


def retail_year_range(year: int) -> tuple[date, date]:
    """Return the inclusive ``(start, end)`` Gregorian dates of a retail year.

    Args:
        year: Retail year.

    Returns:
        ``(first_sunday, last_saturday)`` spanning all 52 weeks.
    """
    start = retail_year_start(year)
    return start, start + timedelta(days=DAYS_PER_YEAR - 1)


# --- Week-level helpers -----------------------------------------------------


def week_start(year: int, week: int) -> date:
    """Return the Sunday that starts ``week`` of retail ``year``.

    Args:
        year: Retail year.
        week: Week number, 1..52.

    Returns:
        The week's start date (a Sunday).

    Raises:
        ValueError: If ``week`` is outside 1..52.
    """
    _check_week(week)
    return retail_year_start(year) + timedelta(days=(week - 1) * DAYS_PER_WEEK)


def week_range(year: int, week: int) -> tuple[date, date]:
    """Return the inclusive ``(Sunday, Saturday)`` dates of a retail week.

    Args:
        year: Retail year.
        week: Week number, 1..52.

    Returns:
        ``(start, end)`` for the week.
    """
    start = week_start(year, week)
    return start, start + timedelta(days=DAYS_PER_WEEK - 1)


# --- Period (month) and quarter helpers ------------------------------------


def period_weeks(period: int) -> tuple[int, int]:
    """Return the inclusive ``(first_week, last_week)`` of a retail period.

    Args:
        period: Retail period (month), 1..12.

    Returns:
        The first and last week numbers of the period.

    Raises:
        ValueError: If ``period`` is outside 1..12.
    """
    _check_period(period)
    first = 1 + sum(PERIOD_WEEKS[: period - 1])
    return first, first + PERIOD_WEEKS[period - 1] - 1


def period_range(year: int, period: int) -> tuple[date, date]:
    """Return the inclusive Gregorian ``(start, end)`` dates of a retail period.

    Args:
        year: Retail year.
        period: Retail period (month), 1..12.

    Returns:
        ``(start, end)`` spanning the period's weeks.
    """
    first, last = period_weeks(period)
    return week_start(year, first), week_range(year, last)[1]


def quarter_weeks(quarter: int) -> tuple[int, int]:
    """Return the inclusive ``(first_week, last_week)`` of a retail quarter.

    Args:
        quarter: Retail quarter, 1..4.

    Returns:
        The first and last week numbers of the quarter.

    Raises:
        ValueError: If ``quarter`` is outside 1..4.
    """
    _check_quarter(quarter)
    first = (quarter - 1) * WEEKS_PER_QUARTER + 1
    return first, quarter * WEEKS_PER_QUARTER


def quarter_range(year: int, quarter: int) -> tuple[date, date]:
    """Return the inclusive Gregorian ``(start, end)`` dates of a retail quarter.

    Args:
        year: Retail year.
        quarter: Retail quarter, 1..4.

    Returns:
        ``(start, end)`` spanning the quarter's 13 weeks.
    """
    first, last = quarter_weeks(quarter)
    return week_start(year, first), week_range(year, last)[1]


def period_of_week(week: int) -> int:
    """Return the retail period (month, 1..12) that contains ``week``.

    Args:
        week: Week number, 1..52.

    Returns:
        The period number.

    Raises:
        ValueError: If ``week`` is outside 1..52.
    """
    _check_week(week)
    cumulative = 0
    for index, weeks in enumerate(PERIOD_WEEKS, start=1):
        cumulative += weeks
        if week <= cumulative:
            return index
    raise AssertionError("unreachable: week is validated to be <= 52")


def quarter_of_week(week: int) -> int:
    """Return the retail quarter (1..4) that contains ``week``.

    Args:
        week: Week number, 1..52.

    Returns:
        The quarter number.

    Raises:
        ValueError: If ``week`` is outside 1..52.
    """
    _check_week(week)
    return (week - 1) // WEEKS_PER_QUARTER + 1


# --- Resolution from a Gregorian date --------------------------------------


def from_date(value: date) -> RetailDate:
    """Resolve a Gregorian date into its full retail-calendar coordinates.

    Works for any date, before or after the anchor (floor division handles the
    negative offsets used by historical dates such as 2019).

    Args:
        value: The Gregorian date to resolve.

    Returns:
        The :class:`RetailDate` describing ``value``.
    """
    days_since_anchor = (value - ANCHOR_WEEK1_START).days
    global_week = days_since_anchor // DAYS_PER_WEEK
    year_offset = global_week // WEEKS_PER_YEAR

    year = ANCHOR_YEAR + year_offset
    week = global_week - year_offset * WEEKS_PER_YEAR + 1
    period = period_of_week(week)
    start, end = week_range(year, week)

    return RetailDate(
        date=value,
        year=year,
        week=week,
        period=period,
        period_name=PERIOD_NAMES[period - 1],
        quarter=quarter_of_week(week),
        day_of_week=(value - start).days + 1,
        week_start=start,
        week_end=end,
    )


# --- Vectorized helpers (polars) -------------------------------------------


def retail_year_expr(date_col: str | pl.Expr = "doc_date") -> pl.Expr:
    """Polars expression for the retail year of a ``Date`` column.

    Vectorized equivalent of ``from_date(d).year``, reusing this module's anchor
    constants so the calendar stays the single source of truth (the arithmetic is
    never re-implemented in callers or in SQL). Correct for dates before the
    anchor (e.g. 2019): integer ``//`` floors toward minus infinity, matching the
    scalar floor division in :func:`from_date`.

    Args:
        date_col: Name of (or expression for) the source ``Date`` column.

    Returns:
        An ``Int16`` expression aliased ``retail_year``.
    """
    col = pl.col(date_col) if isinstance(date_col, str) else date_col
    days_since_anchor = (col - pl.lit(ANCHOR_WEEK1_START)).dt.total_days()
    year_offset = days_since_anchor // DAYS_PER_YEAR
    return (year_offset + ANCHOR_YEAR).cast(pl.Int16).alias("retail_year")


# --- Validation -------------------------------------------------------------


def _check_week(week: int) -> None:
    if not 1 <= week <= WEEKS_PER_YEAR:
        raise ValueError(f"retail week must be 1..{WEEKS_PER_YEAR}, got {week}")


def _check_period(period: int) -> None:
    if not 1 <= period <= len(PERIOD_WEEKS):
        raise ValueError(f"retail period must be 1..{len(PERIOD_WEEKS)}, got {period}")


def _check_quarter(quarter: int) -> None:
    if not 1 <= quarter <= 4:
        raise ValueError(f"retail quarter must be 1..4, got {quarter}")
