"""Post-graduation SRS scheduling (SM-2 adapted). All thresholds/constants isolated for Story 4."""

from __future__ import annotations

from app.models.tick_result import TickResultKind

# Performance score thresholds and initial SRS parameters (Story 4: admin-configurable)
_PERF_THRESHOLDS: list[tuple[float, int, float]] = [
    (0.875, 14, 2.5),   # ≥14 strong recalls -> 14 days, EF 2.5
    (0.625, 7, 2.2),    # ≥10 strong -> 7 days, EF 2.2
    (0.375, 3, 1.7),    # ≥6 strong -> 3 days, EF 1.7
    (-0.1, 1, 1.3),     # else -> 1 day, EF 1.3 (min)
]
MIN_EASE_FACTOR = 1.3
DIFFICULT_MULTIPLIER = 1.2
FORGOT_EASE_DECREMENT = 0.20
MASTERY_INTERVAL_DAYS = 90

# Quality mapping for SM-2 (Story 4 can override)
QUALITY_REMEMBERED = 5
QUALITY_DIFFICULT = 3
QUALITY_FORGOT = 1


def tick_value(kind: TickResultKind) -> float:
    if kind == TickResultKind.REMEMBERED:
        return 1.0
    if kind == TickResultKind.DIFFICULT:
        return 0.5
    return 0.0  # FORGOT


def performance_score_from_tick_values(tick_values: list[float]) -> float:
    """Sum of tick values / 16. Expects exactly 16 values (main 16 ticks, not regression)."""
    if len(tick_values) != 16:
        raise ValueError("expected 16 tick values")
    return sum(tick_values) / 16.0


def get_initial_srs_interval_and_ease(performance_score: float) -> tuple[int, float]:
    """Return (initial_interval_days, initial_ease_factor) for a newly graduated card."""
    for threshold, interval_days, ease in _PERF_THRESHOLDS:
        if performance_score >= threshold:
            return (interval_days, ease)
    return (1, MIN_EASE_FACTOR)


def process_srs_review(
    result: TickResultKind,
    last_interval_days: int,
    ease_factor: float,
    repetitions: int,
) -> tuple[int, float, int]:
    """Apply one SRS review. Returns (next_interval_days, new_ease_factor, new_repetitions)."""
    if result == TickResultKind.REMEMBERED:
        next_interval = max(1, round(last_interval_days * ease_factor))
        # SM-2: EF' = EF + (0.1 - (5-q)(0.08+(5-q)*0.02)); q=5 -> small increase
        new_ease = ease_factor + 0.1 - (5 - QUALITY_REMEMBERED) * (
            0.08 + (5 - QUALITY_REMEMBERED) * 0.02
        )
        new_ease = max(MIN_EASE_FACTOR, round(new_ease * 100) / 100)
        return (next_interval, new_ease, repetitions + 1)
    if result == TickResultKind.DIFFICULT:
        next_interval = max(1, round(last_interval_days * DIFFICULT_MULTIPLIER))
        return (next_interval, ease_factor, repetitions + 1)
    # Forgot
    new_ease = max(MIN_EASE_FACTOR, ease_factor - FORGOT_EASE_DECREMENT)
    return (1, new_ease, 0)
