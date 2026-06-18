"""Tests for the retail (4-5-4) calendar.

The expected values are the business-authoritative facts provided for the
anchor year 2026 (and its boundary with 2025).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from pulsar.retail import calendar as rc


def test_anchor_week_one_is_feb_1_to_feb_7_2026() -> None:
    assert rc.week_range(2026, 1) == (date(2026, 2, 1), date(2026, 2, 7))


def test_following_weeks_are_contiguous_sunday_to_saturday() -> None:
    assert rc.week_range(2026, 2) == (date(2026, 2, 8), date(2026, 2, 14))
    assert rc.week_range(2026, 3) == (date(2026, 2, 15), date(2026, 2, 21))


def test_year_start_is_always_a_sunday_and_364_days_apart() -> None:
    for year in (2019, 2024, 2025, 2026, 2027):
        start = rc.retail_year_start(year)
        assert start.weekday() == 6, f"{year} start {start} is not a Sunday"
    delta = rc.retail_year_start(2027) - rc.retail_year_start(2026)
    assert delta == timedelta(days=364)


def test_week_before_2026_belongs_to_week_52_of_2025() -> None:
    # Jan 25 (Sun) .. Jan 31 (Sat) 2026 is week 52 of retail 2025.
    sun = rc.from_date(date(2026, 1, 25))
    sat = rc.from_date(date(2026, 1, 31))
    assert (sun.year, sun.week, sun.day_of_week) == (2025, 52, 1)
    assert (sat.year, sat.week, sat.day_of_week) == (2025, 52, 7)
    assert rc.week_range(2025, 52) == (date(2026, 1, 25), date(2026, 1, 31))


def test_period_april_2026_is_weeks_10_to_13() -> None:
    assert rc.period_weeks(3) == (10, 13)
    # April 2026: starts Apr 5 (week 10), ends May 2 (week 13).
    assert rc.period_range(2026, 3) == (date(2026, 4, 5), date(2026, 5, 2))


def test_quarters_are_thirteen_weeks_each() -> None:
    assert rc.quarter_weeks(1) == (1, 13)
    assert rc.quarter_weeks(2) == (14, 26)
    assert rc.quarter_weeks(3) == (27, 39)
    assert rc.quarter_weeks(4) == (40, 52)


def test_454_pattern_periods_cover_all_52_weeks_without_gaps() -> None:
    covered: list[int] = []
    for period in range(1, 13):
        first, last = rc.period_weeks(period)
        covered.extend(range(first, last + 1))
    assert covered == list(range(1, 53))


def test_period_and_quarter_of_week_boundaries() -> None:
    assert rc.period_of_week(1) == 1
    assert rc.period_of_week(9) == 2
    assert rc.period_of_week(10) == 3
    assert rc.period_of_week(13) == 3
    assert rc.quarter_of_week(13) == 1
    assert rc.quarter_of_week(14) == 2


def test_from_date_full_resolution_at_anchor() -> None:
    rd = rc.from_date(date(2026, 2, 1))
    assert (rd.year, rd.week, rd.period, rd.quarter, rd.day_of_week) == (2026, 1, 1, 1, 1)
    assert rd.period_name == "February"


def test_historical_date_resolves_with_negative_offset() -> None:
    # Data starts in 2019; backward arithmetic must still land in the right year.
    rd = rc.from_date(date(2019, 9, 9))
    assert rd.year == 2019
    # Round-trip invariant: the resolved week actually contains the date.
    start, end = rc.week_range(rd.year, rd.week)
    assert start <= date(2019, 9, 9) <= end


@pytest.mark.parametrize("offset", range(0, 364, 7))
def test_round_trip_every_week_of_2026(offset: int) -> None:
    d = rc.ANCHOR_WEEK1_START + timedelta(days=offset)
    rd = rc.from_date(d)
    start, end = rc.week_range(rd.year, rd.week)
    assert start <= d <= end
    assert start.weekday() == 6  # Sunday
    assert rd.day_of_week == (d - start).days + 1


def test_invalid_inputs_raise() -> None:
    with pytest.raises(ValueError):
        rc.week_start(2026, 0)
    with pytest.raises(ValueError):
        rc.week_start(2026, 53)
    with pytest.raises(ValueError):
        rc.period_weeks(13)
    with pytest.raises(ValueError):
        rc.quarter_weeks(5)
