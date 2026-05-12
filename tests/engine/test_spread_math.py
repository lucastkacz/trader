import numpy as np
import pandas as pd
import pytest

from src.engine.analysis.spread_math import build_hedged_log_spread


def test_build_hedged_log_spread_logs_raw_prices_once():
    raw_x = pd.Series([100.0, 110.0, 121.0])
    raw_y = pd.Series([50.0, 55.0, 60.5])

    spread = build_hedged_log_spread(raw_x, raw_y, hedge_ratio=0.5)

    expected = np.log(raw_x) - 0.5 * np.log(raw_y)
    pd.testing.assert_series_equal(spread, expected)


def test_build_hedged_log_spread_rejects_non_positive_or_non_finite_prices():
    with pytest.raises(ValueError, match="positive finite raw prices"):
        build_hedged_log_spread(
            pd.Series([100.0, 0.0, 101.0]),
            pd.Series([50.0, 51.0, 52.0]),
            hedge_ratio=1.0,
        )

    with pytest.raises(ValueError, match="positive finite raw prices"):
        build_hedged_log_spread(
            pd.Series([100.0, np.nan, 101.0]),
            pd.Series([50.0, 51.0, 52.0]),
            hedge_ratio=1.0,
        )
