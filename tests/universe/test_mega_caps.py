import pandas as pd
import pytest

from src.universe.filters.mega_caps import (
    exclude_top_by_dollar_volume,
    exclude_top_by_quote_volume_metric,
)


def test_exclude_top_by_dollar_volume_removes_largest_symbols():
    pool = {
        "BTC": _frame(),
        "ETH": _frame(),
        "SOL": _frame(),
    }
    dollar_volumes = {
        "BTC": 1_000,
        "ETH": 800,
        "SOL": 100,
    }

    filtered = exclude_top_by_dollar_volume(
        pool,
        dollar_volumes,
        exclude_top_n=2,
    )

    assert list(filtered) == ["SOL"]


def test_exclude_top_by_dollar_volume_preserves_pool_when_disabled():
    pool = {"BTC": _frame()}

    filtered = exclude_top_by_dollar_volume(
        pool,
        {"BTC": 1_000},
        exclude_top_n=0,
    )

    assert filtered == pool
    assert filtered is not pool


def test_exclude_top_by_dollar_volume_rejects_negative_count():
    with pytest.raises(ValueError, match="exclude_top_n must be non-negative"):
        exclude_top_by_dollar_volume({}, {}, exclude_top_n=-1)


def test_exclude_top_by_quote_volume_metric_uses_explicit_metric():
    pool = {
        "BTC": _volume_frame([100, 100, 100]),
        "ETH": _volume_frame([10, 10, 10_000]),
        "SOL": _volume_frame([50, 50, 50]),
    }

    mean_filtered = exclude_top_by_quote_volume_metric(
        pool,
        lookback_bars=3,
        metric="mean_quote_volume",
        exclude_top_n=1,
    )
    median_filtered = exclude_top_by_quote_volume_metric(
        pool,
        lookback_bars=3,
        metric="median_quote_volume",
        exclude_top_n=1,
    )

    assert list(mean_filtered) == ["BTC", "SOL"]
    assert list(median_filtered) == ["ETH", "SOL"]


def _frame() -> pd.DataFrame:
    return pd.DataFrame({"close": [1.0]})


def _volume_frame(quote_volumes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "close": [1.0] * len(quote_volumes),
            "volume": quote_volumes,
        }
    )
