from types import SimpleNamespace
from unittest.mock import AsyncMock

import pandas as pd
import pytest

from src.engine.trader.config import OrderExecutionConfig, load_strategy_config
from src.engine.trader.runtime.pair_queue import PairQueuePolicy
from src.engine.trader.runtime.pair_validity.models import PairValiditySnapshot
from src.engine.trader.runtime.tick import execute_tick
from src.engine.trader.state.manager import TradeStateManager


@pytest.fixture
def state():
    mgr = TradeStateManager(db_path=":memory:")
    yield mgr
    mgr.close()


@pytest.fixture
def notifier():
    return SimpleNamespace(send=AsyncMock())


@pytest.fixture
def state_only_order_execution():
    return OrderExecutionConfig(
        mode="state_only",
        fill_poll_attempts=0,
        fill_poll_interval_seconds=0.0,
        cancel_unfilled_after_poll=False,
        client_order_prefix="test",
    )


def _pair(asset_x: str, asset_y: str, sharpe: float = 2.0):
    return {
        "Asset_X": asset_x,
        "Asset_Y": asset_y,
        "Hedge_Ratio": 1.0,
        "Best_Params": {
            "lookback_bars": 20,
            "entry_z": 2.0,
        },
        "Performance": {
            "sharpe_ratio": sharpe,
            "final_pnl_pct": 10.0,
        },
    }


def _signal(signal: str, z_score: float = 2.5):
    return SimpleNamespace(
        signal=signal,
        price_a=100.0,
        price_b=50.0,
        weight_a=0.6,
        weight_b=0.4,
        z_score=z_score,
    )


def _validity(
    pair_label: str,
    *,
    operator_review_reasons: list[str] | None = None,
) -> PairValiditySnapshot:
    asset_x, asset_y = pair_label.split("|")
    return PairValiditySnapshot(
        pair_label=pair_label,
        asset_x=asset_x,
        asset_y=asset_y,
        artifact_generated_at="2026-01-01T00:00:00+00:00",
        artifact_promoted_at="2026-01-01T01:00:00+00:00",
        latest_data_at="2026-01-01T03:00:00+00:00",
        timeframe="1m",
        exchange="bybit",
        recent_window_bars=240,
        recent_observation_bars=240,
        wall_clock_age_minutes_since_artifact_generation=180.0,
        bars_since_artifact_generation=180,
        bars_since_promotion=120,
        research_window_start=None,
        research_window_end=None,
        wall_clock_age_minutes_since_research_end=None,
        bars_since_research_end=None,
        research_hedge_ratio=1.0,
        recent_hedge_ratio=1.0,
        hedge_ratio_drift_pct=0.0,
        research_correlation=0.8,
        recent_correlation=0.8,
        correlation_delta=0.0,
        research_p_value=0.02,
        recent_p_value=0.02,
        p_value_delta=0.0,
        research_half_life_bars=80.0,
        recent_half_life_bars=80.0,
        half_life_drift_pct=0.0,
        research_spread_mean=None,
        recent_spread_mean=None,
        spread_mean_shift_sigma=None,
        research_spread_std=None,
        recent_spread_std=None,
        spread_std_drift_pct=None,
        open_position_id=None,
        open_position_holding_bars=None,
        open_position_half_life_multiple=None,
        observed_entries=0,
        observed_signal_exits=0,
        observed_forced_exits=0,
        observed_avg_holding_bars=None,
        operator_review_reasons=operator_review_reasons or [],
        open_position_review_reasons=[],
        notes=[],
    )


async def _fake_candles(*args, **kwargs):
    return (
        pd.DataFrame({"timestamp": [1, 2], "close": [100.0, 101.0]}),
        pd.DataFrame({"timestamp": [1, 2], "close": [50.0, 49.5]}),
    )


@pytest.mark.asyncio
async def test_queue_blocked_decision_prevents_new_entry(
    monkeypatch,
    state,
    notifier,
    state_only_order_execution,
):
    pair = _pair("AAA/USDT", "BBB/USDT")
    pair_label = "AAA/USDT|BBB/USDT"
    monkeypatch.setattr("src.engine.trader.runtime.tick._fetch_pair_candles", _fake_candles)
    monkeypatch.setattr(
        "src.engine.trader.runtime.tick.evaluate_signal",
        lambda **kwargs: _signal("LONG_SPREAD"),
    )

    await execute_tick(
        pairs=[pair],
        state=state,
        notifier=notifier,
        timeframe="1m",
        strategy_cfg=load_strategy_config("configs/strategy/dev.yml"),
        exchange_id="bybit",
        api_key="",
        api_secret="",
        order_execution_cfg=state_only_order_execution,
        order_execution_adapter=None,
        pair_queue_policy=PairQueuePolicy(
            block_on_missing_validity=True,
            block_on_operator_review_reasons=True,
            require_entry_signal=True,
        ),
        pair_validity_snapshots=[
            _validity(pair_label, operator_review_reasons=["stale_market_data"])
        ],
        pair_queue_enabled=True,
    )

    assert state.get_open_positions() == []
    assert state.get_leg_fills() == []
    sent_messages = [call.args[0] for call in notifier.send.await_args_list]
    assert any("ENTRY BLOCKED BY PAIR QUEUE" in message for message in sent_messages)


@pytest.mark.asyncio
async def test_queue_block_does_not_prevent_existing_position_natural_exit(
    monkeypatch,
    state,
    notifier,
    state_only_order_execution,
):
    pair = _pair("AAA/USDT", "BBB/USDT")
    pair_label = "AAA/USDT|BBB/USDT"
    state.open_position(
        pair_label,
        "AAA/USDT",
        "BBB/USDT",
        "LONG_SPREAD",
        100.0,
        50.0,
        0.6,
        0.4,
        -2.5,
        20,
    )
    monkeypatch.setattr("src.engine.trader.runtime.tick._fetch_pair_candles", _fake_candles)
    monkeypatch.setattr(
        "src.engine.trader.runtime.tick.evaluate_signal",
        lambda **kwargs: _signal("FLAT", z_score=0.1),
    )

    await execute_tick(
        pairs=[pair],
        state=state,
        notifier=notifier,
        timeframe="1m",
        strategy_cfg=load_strategy_config("configs/strategy/dev.yml"),
        exchange_id="bybit",
        api_key="",
        api_secret="",
        order_execution_cfg=state_only_order_execution,
        order_execution_adapter=None,
        pair_queue_policy=PairQueuePolicy(
            block_on_missing_validity=True,
            block_on_operator_review_reasons=True,
            require_entry_signal=True,
        ),
        pair_validity_snapshots=[
            _validity(pair_label, operator_review_reasons=["stale_market_data"])
        ],
        pair_queue_enabled=True,
    )

    assert state.get_open_positions() == []
    closed = state.get_all_closed()
    assert len(closed) == 1
    assert closed[0]["close_reason"] == "SIGNAL_EXIT"
    assert all(leg["exchange_order_id"] is None for leg in state.get_leg_fills())


@pytest.mark.asyncio
async def test_queue_rank_controls_future_entry_order(
    monkeypatch,
    state,
    notifier,
    state_only_order_execution,
):
    low_rank = _pair("LOW/USDT", "BBB/USDT", sharpe=0.5)
    high_rank = _pair("HIGH/USDT", "DDD/USDT", sharpe=3.0)
    routed = []

    async def fake_route_signal_transition(**kwargs):
        routed.append(kwargs["pair_label"])

    monkeypatch.setattr("src.engine.trader.runtime.tick._fetch_pair_candles", _fake_candles)
    monkeypatch.setattr(
        "src.engine.trader.runtime.tick.evaluate_signal",
        lambda **kwargs: _signal("LONG_SPREAD"),
    )
    monkeypatch.setattr(
        "src.engine.trader.runtime.tick.route_signal_transition",
        fake_route_signal_transition,
    )

    await execute_tick(
        pairs=[low_rank, high_rank],
        state=state,
        notifier=notifier,
        timeframe="1m",
        strategy_cfg=load_strategy_config("configs/strategy/dev.yml"),
        exchange_id="bybit",
        api_key="",
        api_secret="",
        order_execution_cfg=state_only_order_execution,
        order_execution_adapter=None,
        pair_queue_policy=PairQueuePolicy(
            research_weight=1.0,
            validity_weight=0.0,
            opportunity_weight=0.0,
            block_on_missing_validity=False,
            require_entry_signal=True,
        ),
        pair_queue_enabled=True,
    )

    assert routed == ["HIGH/USDT|DDD/USDT", "LOW/USDT|BBB/USDT"]
