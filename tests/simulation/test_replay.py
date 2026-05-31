from datetime import datetime, timezone

import pandas as pd
import pytest

from src.engine.trader.config import StrategyConfig
from src.simulation.replay import (
    InMemoryHistoricalCandleProvider,
    ReplayClock,
    ReplayPair,
    ReplayWindow,
    SignalReplayConfig,
    run_signal_replay,
)


def test_replay_clock_yields_inclusive_deterministic_ticks():
    window = ReplayWindow(
        start=_utc(2026, 5, 31, 8),
        end=_utc(2026, 5, 31, 11),
        timeframe="1h",
    )

    assert list(ReplayClock(window)) == [
        _utc(2026, 5, 31, 8),
        _utc(2026, 5, 31, 9),
        _utc(2026, 5, 31, 10),
        _utc(2026, 5, 31, 11),
    ]


def test_replay_window_rejects_non_positive_timeframe():
    with pytest.raises(ValueError, match="timeframe must be positive"):
        ReplayWindow(
            start=_utc(2026, 5, 31, 8),
            end=_utc(2026, 5, 31, 11),
            timeframe="0h",
        )


def test_in_memory_provider_returns_only_candles_available_as_of_tick():
    provider = InMemoryHistoricalCandleProvider(
        {"A/USDT": _candles([100.0, 101.0, 102.0, 103.0])}
    )

    result = provider.candles_through(
        "A/USDT",
        timeframe="1h",
        through=_utc(2026, 5, 31, 10),
        limit=2,
    )

    assert result["close"].tolist() == [101.0, 102.0]
    assert result["timestamp"].max() == pd.Timestamp(_utc(2026, 5, 31, 10))
    assert result.attrs["symbol"] == "A/USDT"


def test_signal_replay_reuses_shared_signal_policy_and_tracks_natural_exit():
    provider = InMemoryHistoricalCandleProvider(
        {
            "A/USDT": _candles([100.0, 100.0, 100.0, 70.0, 70.0, 100.0, 100.0]),
            "B/USDT": _candles([100.0] * 7),
        }
    )
    config = SignalReplayConfig(
        window=ReplayWindow(
            start=_utc(2026, 5, 31, 10),
            end=_utc(2026, 5, 31, 14),
            timeframe="1h",
        ),
        pairs=(
            ReplayPair(
                asset_x="A/USDT",
                asset_y="B/USDT",
                hedge_ratio=1.0,
                entry_z=1.0,
                lookback_bars=3,
            ),
        ),
    )

    result = run_signal_replay(
        config=config,
        strategy_cfg=_strategy_config(),
        candle_provider=provider,
    )

    assert result.scope == "signal_evaluation_only"
    assert result.completed_ticks == 5
    assert result.pair_labels == ("A/USDT|B/USDT",)
    assert [observation.action for observation in result.observations] == [
        "SKIP",
        "ENTRY",
        "HOLD",
        "EXIT",
        "SKIP",
    ]
    assert result.action_counts == {"SKIP": 2, "ENTRY": 1, "HOLD": 1, "EXIT": 1}
    assert result.final_signal_sides == {"A/USDT|B/USDT": None}


def test_signal_replay_rejects_provider_future_data():
    class FutureDataProvider:
        def candles_through(self, symbol, *, timeframe, through, limit):
            del symbol, timeframe, through, limit
            return _candles([100.0], start_hour=15)

    config = SignalReplayConfig(
        window=ReplayWindow(
            start=_utc(2026, 5, 31, 14),
            end=_utc(2026, 5, 31, 14),
            timeframe="1h",
        ),
        pairs=(
            ReplayPair(
                asset_x="A/USDT",
                asset_y="B/USDT",
                hedge_ratio=1.0,
                entry_z=1.0,
                lookback_bars=3,
            ),
        ),
    )

    with pytest.raises(ValueError, match="future data for A/USDT"):
        run_signal_replay(
            config=config,
            strategy_cfg=_strategy_config(),
            candle_provider=FutureDataProvider(),
        )


def _strategy_config() -> StrategyConfig:
    return StrategyConfig.model_validate(
        {
            "name": "Synthetic replay",
            "execution": {
                "entry_z_score": 1.0,
                "exit_z_score": 0.0,
                "stop_loss_z_score": 4.0,
                "ew_ols_lookback_bars": 3,
                "volatility_lookback_bars": 2,
            },
        }
    )


def _candles(prices: list[float], *, start_hour: int = 8) -> pd.DataFrame:
    timestamps = pd.date_range(
        _utc(2026, 5, 31, start_hour),
        periods=len(prices),
        freq="h",
    )
    return pd.DataFrame({"timestamp": timestamps, "close": prices})


def _utc(year: int, month: int, day: int, hour: int) -> datetime:
    return datetime(year, month, day, hour, tzinfo=timezone.utc)
