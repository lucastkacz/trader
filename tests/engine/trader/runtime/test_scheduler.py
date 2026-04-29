import pytest

from src.engine.trader.runtime.scheduler import seconds_until_next_candle


def test_seconds_until_next_candle_accepts_minute_timeframe():
    wait_seconds = seconds_until_next_candle("1m")

    assert wait_seconds > 0.0


def test_seconds_until_next_candle_accepts_hour_timeframe():
    wait_seconds = seconds_until_next_candle("4h")

    assert wait_seconds > 0.0


@pytest.mark.parametrize("timeframe", ["", "bad", "4x"])
def test_seconds_until_next_candle_rejects_invalid_timeframe(timeframe):
    with pytest.raises(ValueError):
        seconds_until_next_candle(timeframe)
