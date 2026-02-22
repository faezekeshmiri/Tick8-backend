"""Tick 8 interval configuration (injectable for Story 4 admin-configurable intervals).

Returns the number of days from the previous review to the next, for each tick 1..8.
Tick 1 = same day (0); Tick 2 = +1 day; ... Tick 8 = +90 days.
"""

from __future__ import annotations

# Default Tick 8 intervals (days from previous review). Story 4 will replace via set_tick8_intervals.
_DEFAULT_TICK8_INTERVALS_DAYS: tuple[int, ...] = (0, 1, 3, 7, 14, 30, 60, 90)

_tick8_intervals: tuple[int, ...] = _DEFAULT_TICK8_INTERVALS_DAYS


def get_tick8_interval_days(tick_number: int) -> int:
    """Return interval in days for tick 1..8 (1-indexed). Tick 1 = 0 (same day)."""
    if not 1 <= tick_number <= 8:
        raise ValueError("tick_number must be 1..8")
    return _tick8_intervals[tick_number - 1]


def get_tick8_intervals() -> tuple[int, ...]:
    """Return all 8 intervals (for schedule recalculation)."""
    return _tick8_intervals


def set_tick8_intervals(intervals: tuple[int, ...]) -> None:
    """Replace intervals (Story 4: admin-configured). Must be 8 non-negative integers."""
    if len(intervals) != 8 or any(i < 0 for i in intervals):
        raise ValueError("intervals must be 8 non-negative integers")
    global _tick8_intervals
    _tick8_intervals = tuple(intervals)


def get_regression_intervals_days() -> tuple[int, int, int]:
    """Phase 2 regression mini Phase 1: R1=0, R2=+1, R3=+3 days."""
    return (0, 1, 3)
