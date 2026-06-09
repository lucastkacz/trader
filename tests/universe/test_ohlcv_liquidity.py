import pandas as pd
import pytest

from src.universe.filters.ohlcv_liquidity import (
    quote_volume_metric,
    select_by_average_dollar_volume,
    select_by_quote_volume_metric,
)


def test_select_by_average_dollar_volume_uses_recent_lookback_and_floor():
    frames = {
        "IN_RANGE": _frame(closes=[10, 20, 30], volumes=[10, 10, 10]),
        "TOO_SMALL": _frame(closes=[1, 1, 1], volumes=[1, 1, 1]),
        "VERY_LIQUID": _frame(closes=[1_000, 1_000, 1_000], volumes=[10, 10, 10]),
        "MISSING_VOLUME": pd.DataFrame({"close": [10, 10]}),
    }

    selection = select_by_average_dollar_volume(
        frames,
        lookback_bars=2,
        min_dollar_volume=100,
    )

    assert list(selection.pool) == ["IN_RANGE", "VERY_LIQUID"]
    assert selection.dollar_volumes == {
        "IN_RANGE": 250.0,
        "VERY_LIQUID": 10_000.0,
    }


def test_select_by_average_dollar_volume_rejects_invalid_floor():
    with pytest.raises(ValueError, match="lookback_bars must be positive"):
        select_by_average_dollar_volume(
            {},
            lookback_bars=0,
            min_dollar_volume=0,
        )


def test_select_by_quote_volume_metric_supports_median_and_percentile():
    frames = {
        "MEDIAN_OK": _frame(closes=[10, 10, 10], volumes=[10, 100, 10]),
        "MEDIAN_LOW": _frame(closes=[10, 10, 10], volumes=[1, 1, 1]),
    }

    median_selection = select_by_quote_volume_metric(
        frames,
        lookback_bars=3,
        metric="median_quote_volume",
        min_value=50,
    )
    p25 = quote_volume_metric(
        frames["MEDIAN_OK"],
        lookback_bars=3,
        metric="percentile_quote_volume",
        percentile=25,
    )

    assert list(median_selection.pool) == ["MEDIAN_OK"]
    assert median_selection.dollar_volumes == {"MEDIAN_OK": 100.0}
    assert p25 == 100.0


def test_percentile_metric_requires_percentile():
    with pytest.raises(ValueError, match="percentile is required"):
        select_by_quote_volume_metric(
            {"BTC": _frame(closes=[10], volumes=[1])},
            lookback_bars=1,
            metric="percentile_quote_volume",
            min_value=0,
        )


def _frame(*, closes: list[float], volumes: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"close": closes, "volume": volumes})
