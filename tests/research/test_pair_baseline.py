import numpy as np
import pandas as pd

from src.research.pair_baseline import build_research_baseline_fields


def test_build_research_baseline_fields_records_window_spread_and_z_distribution():
    timestamps = pd.date_range("2026-01-01T00:00:00Z", periods=80, freq="1min")
    base = np.linspace(100.0, 120.0, len(timestamps))
    prices = pd.DataFrame(
        {
            "asset_x_close": base * 1.02,
            "asset_y_close": base,
        },
        index=timestamps,
    )

    fields = build_research_baseline_fields(
        prices,
        hedge_ratio=1.0,
        lookback_bars=20,
    )

    assert fields["Research_Window"] == {
        "start": "2026-01-01T00:00:00+00:00",
        "end": "2026-01-01T01:19:00+00:00",
        "bars": 80,
    }
    assert fields["Correlation"] is not None
    assert fields["Spread_Mean"] is not None
    assert fields["Spread_Std"] is not None
    assert fields["Z_Score_Distribution"]["lookback_bars"] == 20
    assert fields["Z_Score_Distribution"]["observations"] == 61
    assert set(fields["Z_Score_Distribution"]) == {
        "lookback_bars",
        "observations",
        "mean",
        "std",
        "min",
        "max",
        "p05",
        "p95",
    }


def test_build_research_baseline_fields_serializes_numeric_millisecond_index_as_iso():
    timestamps_ms = [1_767_225_600_000, 1_767_225_660_000, 1_767_225_720_000]
    prices = pd.DataFrame(
        {
            "asset_x_close": [101.0, 102.0, 103.0],
            "asset_y_close": [100.0, 101.0, 102.0],
        },
        index=timestamps_ms,
    )

    fields = build_research_baseline_fields(
        prices,
        hedge_ratio=1.0,
        lookback_bars=2,
    )

    assert fields["Research_Window"]["start"] == "2026-01-01T00:00:00+00:00"
    assert fields["Research_Window"]["end"] == "2026-01-01T00:02:00+00:00"
