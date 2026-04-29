"""Candle scheduling helpers for the trader runtime."""

from datetime import datetime, timedelta, timezone

from src.utils.timeframe_math import get_timeframe_minutes


CANDLE_BUFFER_SECONDS = 30
SECONDS_PER_DAY = 24 * 60 * 60


def seconds_until_next_candle(timeframe: str) -> float:
    """Return seconds until the next candle boundary plus safety buffer."""
    now = datetime.now(timezone.utc)
    timeframe_minutes = get_timeframe_minutes(timeframe)
    bar_seconds = int(timeframe_minutes * 60)

    if bar_seconds <= 0:
        raise ValueError(f"Timeframe must be positive: {timeframe}")
    if SECONDS_PER_DAY % bar_seconds != 0:
        raise ValueError(f"Timeframe must divide a UTC day: {timeframe}")

    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elapsed_seconds = int((now - day_start).total_seconds())
    next_bar_elapsed = ((elapsed_seconds // bar_seconds) + 1) * bar_seconds
    if next_bar_elapsed >= SECONDS_PER_DAY:
        next_candle = day_start + timedelta(days=1)
    else:
        next_candle = day_start + timedelta(seconds=next_bar_elapsed)

    delta = (next_candle - now).total_seconds() + CANDLE_BUFFER_SECONDS
    return max(delta, 0)
