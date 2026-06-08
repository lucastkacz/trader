import pandas as pd
import pytest

from src.universe.filters.ohlcv_liquidity import select_by_average_dollar_volume


def test_select_by_average_dollar_volume_uses_recent_lookback_and_bounds():
    frames = {
        "IN_RANGE": _frame(closes=[10, 20, 30], volumes=[10, 10, 10]),
        "TOO_SMALL": _frame(closes=[1, 1, 1], volumes=[1, 1, 1]),
        "TOO_LARGE": _frame(closes=[1_000, 1_000, 1_000], volumes=[10, 10, 10]),
        "MISSING_VOLUME": pd.DataFrame({"close": [10, 10]}),
    }

    selection = select_by_average_dollar_volume(
        frames,
        lookback_bars=2,
        min_dollar_volume=100,
        max_dollar_volume=1_000,
    )

    assert list(selection.pool) == ["IN_RANGE"]
    assert selection.dollar_volumes == {"IN_RANGE": 250.0}


def test_select_by_average_dollar_volume_rejects_invalid_bounds():
    with pytest.raises(ValueError, match="lookback_bars must be positive"):
        select_by_average_dollar_volume(
            {},
            lookback_bars=0,
            min_dollar_volume=0,
            max_dollar_volume=1,
        )

    with pytest.raises(ValueError, match="max_dollar_volume"):
        select_by_average_dollar_volume(
            {},
            lookback_bars=1,
            min_dollar_volume=2,
            max_dollar_volume=1,
        )


def _frame(*, closes: list[float], volumes: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"close": closes, "volume": volumes})
