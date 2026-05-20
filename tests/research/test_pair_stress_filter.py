import pandas as pd

from src.data.storage.local_parquet import ParquetStorage
from src.engine.trader.config import load_strategy_config
from src.research import pair_stress_filter
from src.research.pair_stress_filter import PairStressFilter


def test_pair_stress_filter_survivor_records_research_baseline_fields(monkeypatch, tmp_path):
    async_unused = object()
    timestamps = pd.date_range("2026-01-01T00:00:00Z", periods=600, freq="1min")
    storage = ParquetStorage(str(tmp_path / "parquet"))
    storage.save_ohlcv(
        "AAA/USDT",
        "1m",
        _ohlcv(timestamps, start=100.0),
        {},
        exchange="bybit",
    )
    storage.save_ohlcv(
        "BBB/USDT",
        "1m",
        _ohlcv(timestamps, start=90.0),
        {},
        exchange="bybit",
    )

    def fake_find_best_parameters(**kwargs):
        net_df = pd.DataFrame({
            "timestamp": timestamps[-5:],
            "position": [0.0, 1.0, 1.0, 0.0, 0.0],
            "z_score": [0.0, -2.0, -1.0, 0.0, 0.0],
            "gross_returns": [0.0, 0.01, 0.0, 0.0, 0.0],
            "net_returns": [0.0, 0.01, 0.0, 0.0, 0.0],
            "fee_drag": [0.0, 0.0, 0.0, 0.0, 0.0],
        })
        return (
            {"lookback_bars": 60, "entry_z": 2.0},
            {"sharpe_ratio": 2.0, "final_pnl_pct": 1.0},
            0.01,
            net_df,
        )

    monkeypatch.setattr(
        pair_stress_filter,
        "find_best_parameters",
        fake_find_best_parameters,
    )

    survivor, _ = PairStressFilter(storage)._stress_filter_one_pair(
        pair={
            "Cohort": "Cohort_0",
            "Asset_X": "AAA/USDT",
            "Asset_Y": "BBB/USDT",
            "Hedge_Ratio": 1.0,
            "Half_Life": 40.0,
            "P_Value": 0.01,
        },
        pair_index=0,
        pair_count=1,
        timeframe="1m",
        exchange="bybit",
        grid=[],
        simulator=async_unused,
        friction=async_unused,
        bars_per_year=525_600,
        strategy_cfg=load_strategy_config("configs/strategy/dev.yml"),
    )

    assert survivor is not None
    assert survivor["Research_Window"] == {
        "start": "2026-01-01T00:00:00+00:00",
        "end": "2026-01-01T09:59:00+00:00",
        "bars": 600,
    }
    assert survivor["Correlation"] is not None
    assert survivor["Spread_Mean"] is not None
    assert survivor["Spread_Std"] is not None
    assert survivor["Z_Score_Distribution"]["lookback_bars"] == 60
    assert survivor["Z_Score_Distribution"]["observations"] == 541


def _ohlcv(timestamps: pd.DatetimeIndex, *, start: float) -> pd.DataFrame:
    close = pd.Series(range(len(timestamps)), dtype=float) * 0.01 + start
    return pd.DataFrame({
        "timestamp": timestamps,
        "open": close,
        "high": close + 0.1,
        "low": close - 0.1,
        "close": close,
        "volume": 1000.0,
    })
