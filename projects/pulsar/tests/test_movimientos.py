"""Pure tests for ledger windowing logic (no HANA / no lakehouse required)."""

from __future__ import annotations

from datetime import date

from pulsar.ledger.movimientos import _iter_month_windows


def test_month_windows_are_half_open_and_contiguous() -> None:
    windows = list(_iter_month_windows(date(2024, 1, 1), date(2024, 4, 1)))
    assert windows == [
        (date(2024, 1, 1), date(2024, 2, 1)),
        (date(2024, 2, 1), date(2024, 3, 1)),
        (date(2024, 3, 1), date(2024, 4, 1)),
    ]


def test_month_windows_clip_last_window_to_end() -> None:
    windows = list(_iter_month_windows(date(2024, 1, 15), date(2024, 2, 10)))
    assert windows == [
        (date(2024, 1, 15), date(2024, 2, 1)),
        (date(2024, 2, 1), date(2024, 2, 10)),
    ]


def test_month_windows_cross_year_boundary() -> None:
    windows = list(_iter_month_windows(date(2024, 11, 1), date(2025, 2, 1)))
    assert windows == [
        (date(2024, 11, 1), date(2024, 12, 1)),
        (date(2024, 12, 1), date(2025, 1, 1)),
        (date(2025, 1, 1), date(2025, 2, 1)),
    ]


def test_month_windows_step_of_two() -> None:
    windows = list(_iter_month_windows(date(2024, 1, 1), date(2024, 5, 1), step_months=2))
    assert windows == [
        (date(2024, 1, 1), date(2024, 3, 1)),
        (date(2024, 3, 1), date(2024, 5, 1)),
    ]


def test_month_windows_empty_when_start_not_before_end() -> None:
    assert list(_iter_month_windows(date(2024, 1, 1), date(2024, 1, 1))) == []
