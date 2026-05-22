"""Time helpers for pair-validity diagnostics."""

from datetime import datetime, timezone
from typing import Any

from src.utils.timeframe_math import get_timeframe_minutes


def age_minutes(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return (as_utc(end) - as_utc(start)).total_seconds() / 60.0


def bars_between(
    start: datetime | None,
    end: datetime | None,
    timeframe: str,
) -> int | None:
    if start is None or end is None:
        return None
    minutes = get_timeframe_minutes(timeframe)
    return max(0, int((as_utc(end) - as_utc(start)).total_seconds() // 60 // minutes))


def parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return as_utc(parsed)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

