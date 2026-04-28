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
