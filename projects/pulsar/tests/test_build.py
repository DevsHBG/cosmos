"""Pure tests for movements windowing logic (no HANA / no lakehouse required)."""

from __future__ import annotations

from datetime import date
from itertools import pairwise

from pulsar.model.movements.build import _iter_retail_year_windows
from pulsar.retail.calendar import from_date, retail_year_start


def test_windows_on_boundaries_are_full_contiguous_retail_years() -> None:
    windows = list(_iter_retail_year_windows(retail_year_start(2020), retail_year_start(2023)))
    assert windows == [
        (retail_year_start(2020), retail_year_start(2021)),
        (retail_year_start(2021), retail_year_start(2022)),
        (retail_year_start(2022), retail_year_start(2023)),
    ]


def test_first_window_starts_at_start_then_snaps_to_year_boundary() -> None:
    start = date(2019, 1, 1)  # mid retail year 2018
    windows = list(_iter_retail_year_windows(start, retail_year_start(2021)))
    assert windows[0] == (start, retail_year_start(from_date(start).year + 1))
    # Half-open and contiguous: each window's end is the next window's start.
    for (_, a_end), (b_start, _) in pairwise(windows):
        assert a_end == b_start


def test_last_window_is_clipped_to_end() -> None:
    end = date(2022, 6, 15)  # mid retail year
    windows = list(_iter_retail_year_windows(retail_year_start(2021), end))
    assert windows[0][0] == retail_year_start(2021)
    assert windows[-1][1] == end


def test_single_partial_year_yields_one_window() -> None:
    start, end = date(2024, 3, 1), date(2024, 9, 1)  # same retail year
    assert list(_iter_retail_year_windows(start, end)) == [(start, end)]


def test_empty_when_start_not_before_end() -> None:
    d = retail_year_start(2021)
    assert list(_iter_retail_year_windows(d, d)) == []
