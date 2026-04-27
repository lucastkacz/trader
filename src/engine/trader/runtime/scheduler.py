"""Candle scheduling helpers for the trader runtime."""

from datetime import datetime, timedelta, timezone


CANDLE_BUFFER_SECONDS = 30


def seconds_until_next_candle(timeframe: str) -> float:
    """Return seconds until the next candle boundary plus safety buffer."""
    now = datetime.now(timezone.utc)

    if timeframe.endswith("h"):
        hours = int(timeframe[:-1])
        next_hour = ((now.hour // hours) + 1) * hours
        if next_hour >= 24:
            next_candle = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        else:
            next_candle = now.replace(hour=next_hour, minute=0, second=0, microsecond=0)
    elif timeframe.endswith("m"):
        minutes = int(timeframe[:-1])
        next_minute = ((now.minute // minutes) + 1) * minutes
        if next_minute >= 60:
            next_candle = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        else:
            next_candle = now.replace(minute=next_minute, second=0, microsecond=0)
    else:
        return 60.0

    delta = (next_candle - now).total_seconds() + CANDLE_BUFFER_SECONDS
    return max(delta, 0)
