def get_bars_per_day(timeframe: str) -> int:
    """
    Parses a timeframe string (e.g. '1m', '4h', '1d') and returns the exact number of bars per day.
    Raises ValueError if the timeframe is unparseable or unsupported.
    """
    timeframe = timeframe.lower()
    try:
        if timeframe.endswith('m'):
            minutes = int(timeframe[:-1])
            return (60 // minutes) * 24
        elif timeframe.endswith('h'):
            hours = int(timeframe[:-1])
            return 24 // hours
        elif timeframe.endswith('d'):
            days = int(timeframe[:-1])
            return max(1 // days, 1)
        else:
            raise ValueError(f"Unsupported timeframe format: {timeframe}")
    except Exception as e:
        raise ValueError(f"Could not parse timeframe '{timeframe}': {e}")

def get_bars_per_year(timeframe: str) -> int:
    """
    Returns the exact number of bars per year based on the timeframe.
    """
    return get_bars_per_day(timeframe) * 365


def get_timeframe_minutes(timeframe: str) -> float:
    """Parse a timeframe string into minutes per bar."""
    timeframe = timeframe.lower()
    try:
        if timeframe.endswith("m"):
            return float(int(timeframe[:-1]))
        if timeframe.endswith("h"):
            return float(int(timeframe[:-1]) * 60)
        if timeframe.endswith("d"):
            return float(int(timeframe[:-1]) * 24 * 60)
        raise ValueError(f"Unsupported timeframe format: {timeframe}")
    except Exception as exc:
        raise ValueError(f"Could not parse timeframe '{timeframe}': {exc}")


def get_timeframe_ms(timeframe: str) -> int:
    """Parse a timeframe string into milliseconds per bar."""
    return int(get_timeframe_minutes(timeframe) * 60_000)


def floor_timestamp_to_timeframe(timestamp_ms: int, timeframe: str) -> int:
    """Return the candle-open timestamp containing the given millisecond."""
    bar_ms = get_timeframe_ms(timeframe)
    return (timestamp_ms // bar_ms) * bar_ms


def last_closed_candle_open_ms(timeframe: str, *, now_ms: int) -> int:
    """Return the most recent fully closed candle-open timestamp."""
    return max(
        0,
        floor_timestamp_to_timeframe(now_ms, timeframe) - get_timeframe_ms(timeframe),
    )


def is_timeframe_aligned(timestamp_ms: int, timeframe: str) -> bool:
    """Return whether a timestamp falls exactly on a candle-open boundary."""
    return timestamp_ms % get_timeframe_ms(timeframe) == 0
