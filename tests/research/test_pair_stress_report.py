import json

import pandas as pd
import pytest

from src.research.pair_stress_report import (
    build_surviving_pair_report,
    pair_stress_report_path,
    write_pair_stress_report,
)
from src.research.pair_stress_simulation import build_pair_zscore


def test_pair_stress_zscore_rejects_invalid_raw_prices():
    df = pd.DataFrame({
        "A_close": [100.0, 101.0, -1.0],
        "B_close": [50.0, 51.0, 52.0],
    })

    with pytest.raises(ValueError, match="positive finite raw prices"):
        build_pair_zscore(df, lookback_bars=2, hedge_ratio=1.0)


def test_stress_report_records_traceable_trades_and_friction(tmp_path):
    net_df = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=5, freq="1min"),
        "position": [0.0, 1.0, 1.0, 0.0, 0.0],
        "z_score": [0.0, -2.1, -1.4, 0.0, 0.0],
        "gross_returns": [0.0, 0.01, 0.02, -0.005, 0.0],
        "fee_drag": [0.0, 0.0012, 0.0, 0.0012, 0.0],
        "funding_drag": [0.0, 0.0001, 0.0001, 0.0, 0.0],
        "net_returns": [0.0, 0.0087, 0.0199, -0.0062, 0.0],
    })
    pair = {
        "Asset_X": "DASH/USDT",
        "Asset_Y": "ZEC/USDT",
        "Hedge_Ratio": 0.8,
    }

    row = build_surviving_pair_report(
        pair=pair,
        source_window={"start": "2026-01-01T00:00:00", "end": "2026-01-01T00:04:00", "bars": 5},
        stress_params={"lookback_bars": 60, "entry_z": 2.0, "exit_z": 0.0},
        net_df=net_df,
    )
    path = write_pair_stress_report([row], timeframe="1m", exchange="bybit", base_dir=tmp_path)

    artifact = json.loads(path.read_text(encoding="utf-8"))

    assert path == pair_stress_report_path("1m", tmp_path)
    assert artifact["metadata"]["artifact_type"] == "pair_stress_report"
    assert artifact["pairs"][0]["pair"] == "DASH/USDT|ZEC/USDT"
    assert artifact["pairs"][0]["status"] == "survived"
    assert artifact["pairs"][0]["summary"]["gross_return"] == pytest.approx(0.025)
    assert artifact["pairs"][0]["summary"]["net_return"] == pytest.approx(0.0224)
    assert artifact["pairs"][0]["summary"]["fee_drag"] == pytest.approx(0.0024)
    assert artifact["pairs"][0]["entries_exits"][0]["side"] == "LONG_SPREAD"
    assert artifact["pairs"][0]["entries_exits"][0]["net_return"] == pytest.approx(0.0224)
