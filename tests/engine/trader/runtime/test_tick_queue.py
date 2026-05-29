from types import SimpleNamespace
from unittest.mock import AsyncMock

import pandas as pd
import pytest

from src.engine.trader.config import OrderExecutionConfig, load_strategy_config
from src.engine.trader.runtime.pair_queue import PairQueuePolicy
from src.engine.trader.runtime.pair_validity.models import PairValiditySnapshot
from src.engine.trader.runtime.risk import PreTradeRiskPolicy
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


def _signal(
    signal: str,
    z_score: float = 2.5,
    *,
    weight_a: float = 0.6,
    weight_b: float = 0.4,
    price_a: float = 100.0,
    price_b: float = 50.0,
):
    return SimpleNamespace(
        signal=signal,
        price_a=price_a,
        price_b=price_b,
        weight_a=weight_a,
        weight_b=weight_b,
        z_score=z_score,
    )


def _pre_trade_policy(
    *,
    max_cluster_exposure: float = 0.10,
    max_portfolio_exposure: float = 0.30,
    max_leverage: float = 10.0,
    min_order_quantity: float = 0.000001,
    min_order_notional: float = 0.000001,
    order_quantity_step: float = 0.000001,
    liquidity_lookback_bars: int = 2,
    min_recent_quote_volume: float = 1.0,
) -> PreTradeRiskPolicy:
    return PreTradeRiskPolicy(
        max_cluster_exposure=max_cluster_exposure,
        max_portfolio_exposure=max_portfolio_exposure,
        max_leverage=max_leverage,
        min_order_quantity=min_order_quantity,
        min_order_notional=min_order_notional,
        order_quantity_step=order_quantity_step,
        liquidity_lookback_bars=liquidity_lookback_bars,
        min_recent_quote_volume=min_recent_quote_volume,
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
        pd.DataFrame(
            {"timestamp": [1, 2], "close": [100.0, 101.0], "volume": [1000.0, 1000.0]}
        ),
        pd.DataFrame(
            {"timestamp": [1, 2], "close": [50.0, 49.5], "volume": [1000.0, 1000.0]}
        ),
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
async def test_pre_trade_risk_sizes_entry_to_cluster_exposure(
    monkeypatch,
    state,
    notifier,
    state_only_order_execution,
):
    pair = _pair("AAA/USDT", "BBB/USDT")
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
            block_on_missing_validity=False,
            require_entry_signal=True,
        ),
        pair_queue_enabled=True,
        pre_trade_risk_policy=_pre_trade_policy(),
    )

    position = state.get_open_positions()[0]
    assert position["weight_a"] == pytest.approx(0.06)
    assert position["weight_b"] == pytest.approx(0.04)
    legs = state.get_leg_fills(spread_id=position["id"])
    assert [leg["target_qty"] for leg in legs] == pytest.approx([0.06, 0.04])
    assert all(leg["exchange_order_id"] is None for leg in legs)


@pytest.mark.asyncio
async def test_pre_trade_risk_blocks_portfolio_exposure_without_opening_position(
    monkeypatch,
    state,
    notifier,
    state_only_order_execution,
):
    state.open_position(
        "OLD/USDT|BBB/USDT",
        "OLD/USDT",
        "BBB/USDT",
        "LONG_SPREAD",
        100.0,
        50.0,
        0.12,
        0.08,
        -2.5,
        20,
    )
    monkeypatch.setattr("src.engine.trader.runtime.tick._fetch_pair_candles", _fake_candles)
    monkeypatch.setattr(
        "src.engine.trader.runtime.tick.evaluate_signal",
        lambda **kwargs: _signal("LONG_SPREAD"),
    )

    await execute_tick(
        pairs=[_pair("AAA/USDT", "CCC/USDT")],
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
            block_on_missing_validity=False,
            max_positions_per_pair=2,
            require_entry_signal=True,
        ),
        pair_queue_enabled=True,
        pre_trade_risk_policy=_pre_trade_policy(max_portfolio_exposure=0.25),
    )

    assert [position["pair_label"] for position in state.get_open_positions()] == [
        "OLD/USDT|BBB/USDT"
    ]
    sent_messages = [call.args[0] for call in notifier.send.await_args_list]
    assert any("ENTRY BLOCKED BY PRE-TRADE RISK" in message for message in sent_messages)
    assert any("portfolio_exposure_above_max" in message for message in sent_messages)


@pytest.mark.asyncio
async def test_pre_trade_risk_blocks_leverage_without_recording_leg_targets(
    monkeypatch,
    state,
    notifier,
    state_only_order_execution,
):
    monkeypatch.setattr("src.engine.trader.runtime.tick._fetch_pair_candles", _fake_candles)
    monkeypatch.setattr(
        "src.engine.trader.runtime.tick.evaluate_signal",
        lambda **kwargs: _signal("LONG_SPREAD"),
    )

    await execute_tick(
        pairs=[_pair("AAA/USDT", "BBB/USDT")],
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
            block_on_missing_validity=False,
            require_entry_signal=True,
        ),
        pair_queue_enabled=True,
        pre_trade_risk_policy=_pre_trade_policy(max_leverage=0.05),
    )

    assert state.get_open_positions() == []
    assert state.get_leg_fills() == []
    sent_messages = [call.args[0] for call in notifier.send.await_args_list]
    assert any("max_leverage_exceeded" in message for message in sent_messages)


@pytest.mark.asyncio
async def test_pre_trade_risk_blocks_order_quantity_below_min_without_opening_position(
    monkeypatch,
    state,
    notifier,
    state_only_order_execution,
):
    monkeypatch.setattr("src.engine.trader.runtime.tick._fetch_pair_candles", _fake_candles)
    monkeypatch.setattr(
        "src.engine.trader.runtime.tick.evaluate_signal",
        lambda **kwargs: _signal(
            "LONG_SPREAD",
            weight_a=0.99999,
            weight_b=0.00001,
        ),
    )

    await execute_tick(
        pairs=[_pair("AAA/USDT", "BBB/USDT")],
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
            block_on_missing_validity=False,
            require_entry_signal=True,
        ),
        pair_queue_enabled=True,
        pre_trade_risk_policy=_pre_trade_policy(
            min_order_quantity=0.01,
            min_order_notional=0.000001,
            order_quantity_step=0.000001,
        ),
    )

    assert state.get_all_orders() == []
    assert state.get_leg_fills() == []
    sent_messages = [call.args[0] for call in notifier.send.await_args_list]
    assert any("order_quantity_below_min" in message for message in sent_messages)


@pytest.mark.asyncio
async def test_pre_trade_risk_blocks_order_notional_below_min_without_leg_targets(
    monkeypatch,
    state,
    notifier,
    state_only_order_execution,
):
    monkeypatch.setattr("src.engine.trader.runtime.tick._fetch_pair_candles", _fake_candles)
    monkeypatch.setattr(
        "src.engine.trader.runtime.tick.evaluate_signal",
        lambda **kwargs: _signal("LONG_SPREAD", price_b=1.0),
    )

    await execute_tick(
        pairs=[_pair("AAA/USDT", "BBB/USDT")],
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
            block_on_missing_validity=False,
            require_entry_signal=True,
        ),
        pair_queue_enabled=True,
        pre_trade_risk_policy=_pre_trade_policy(
            min_order_quantity=0.000001,
            min_order_notional=0.05,
            order_quantity_step=0.000001,
        ),
    )

    assert state.get_all_orders() == []
    assert state.get_leg_fills() == []
    sent_messages = [call.args[0] for call in notifier.send.await_args_list]
    assert any("order_notional_below_min" in message for message in sent_messages)


@pytest.mark.asyncio
async def test_pre_trade_risk_blocks_invalid_order_precision_without_order_ids(
    monkeypatch,
    state,
    notifier,
    state_only_order_execution,
):
    monkeypatch.setattr("src.engine.trader.runtime.tick._fetch_pair_candles", _fake_candles)
    monkeypatch.setattr(
        "src.engine.trader.runtime.tick.evaluate_signal",
        lambda **kwargs: _signal(
            "LONG_SPREAD",
            weight_a=0.75,
            weight_b=0.25,
        ),
    )

    await execute_tick(
        pairs=[_pair("AAA/USDT", "BBB/USDT")],
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
            block_on_missing_validity=False,
            require_entry_signal=True,
        ),
        pair_queue_enabled=True,
        pre_trade_risk_policy=_pre_trade_policy(
            min_order_quantity=0.000001,
            min_order_notional=0.000001,
            order_quantity_step=0.02,
        ),
    )

    assert state.get_all_orders() == []
    assert state.get_leg_fills() == []
    sent_messages = [call.args[0] for call in notifier.send.await_args_list]
    assert any("order_precision_invalid" in message for message in sent_messages)


@pytest.mark.asyncio
async def test_pre_trade_precision_blocked_flip_closes_without_replacement_open(
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
        lambda **kwargs: _signal(
            "SHORT_SPREAD",
            weight_a=0.75,
            weight_b=0.25,
        ),
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
            block_on_missing_validity=False,
            max_positions_per_pair=2,
            require_entry_signal=True,
        ),
        pair_queue_enabled=True,
        pre_trade_risk_policy=_pre_trade_policy(
            min_order_quantity=0.000001,
            min_order_notional=0.000001,
            order_quantity_step=0.02,
        ),
    )

    assert state.get_open_positions() == []
    assert len(state.get_all_closed()) == 1
    legs = state.get_leg_fills()
    assert sum(leg["leg_role"] == "OPEN" for leg in legs) == 2
    assert sum(leg["leg_role"] == "CLOSE" for leg in legs) == 2
    assert all(leg["exchange_order_id"] is None for leg in legs)
    assert all(leg["client_order_id"] is None for leg in legs)
    sent_messages = [call.args[0] for call in notifier.send.await_args_list]
    assert any("EXIT SIGNAL: AAA/USDT|BBB/USDT" in message for message in sent_messages)
    assert any("order_precision_invalid" in message for message in sent_messages)


@pytest.mark.asyncio
async def test_pre_trade_risk_blocks_low_liquidity_entry_without_opening_position(
    monkeypatch,
    state,
    notifier,
    state_only_order_execution,
):
    async def low_liquidity_candles(*args, **kwargs):
        return (
            pd.DataFrame(
                {"timestamp": [1, 2], "close": [100.0, 101.0], "volume": [1.0, 1.0]}
            ),
            pd.DataFrame(
                {"timestamp": [1, 2], "close": [50.0, 49.5], "volume": [1.0, 1.0]}
            ),
        )

    monkeypatch.setattr("src.engine.trader.runtime.tick._fetch_pair_candles", low_liquidity_candles)
    monkeypatch.setattr(
        "src.engine.trader.runtime.tick.evaluate_signal",
        lambda **kwargs: _signal("LONG_SPREAD"),
    )

    await execute_tick(
        pairs=[_pair("AAA/USDT", "BBB/USDT")],
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
            block_on_missing_validity=False,
            require_entry_signal=True,
        ),
        pair_queue_enabled=True,
        pre_trade_risk_policy=_pre_trade_policy(min_recent_quote_volume=10_000.0),
    )

    assert state.get_all_orders() == []
    assert state.get_leg_fills() == []
    sent_messages = [call.args[0] for call in notifier.send.await_args_list]
    assert any("liquidity_below_min" in message for message in sent_messages)


@pytest.mark.asyncio
async def test_pre_trade_liquidity_blocked_flip_closes_without_replacement_open(
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

    async def low_liquidity_candles(*args, **kwargs):
        return (
            pd.DataFrame(
                {"timestamp": [1, 2], "close": [100.0, 101.0], "volume": [1.0, 1.0]}
            ),
            pd.DataFrame(
                {"timestamp": [1, 2], "close": [50.0, 49.5], "volume": [1.0, 1.0]}
            ),
        )

    monkeypatch.setattr("src.engine.trader.runtime.tick._fetch_pair_candles", low_liquidity_candles)
    monkeypatch.setattr(
        "src.engine.trader.runtime.tick.evaluate_signal",
        lambda **kwargs: _signal("SHORT_SPREAD"),
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
            block_on_missing_validity=False,
            max_positions_per_pair=2,
            require_entry_signal=True,
        ),
        pair_queue_enabled=True,
        pre_trade_risk_policy=_pre_trade_policy(min_recent_quote_volume=10_000.0),
    )

    assert state.get_open_positions() == []
    assert len(state.get_all_closed()) == 1
    legs = state.get_leg_fills()
    assert sum(leg["leg_role"] == "OPEN" for leg in legs) == 2
    assert sum(leg["leg_role"] == "CLOSE" for leg in legs) == 2
    assert all(leg["exchange_order_id"] is None for leg in legs)
    assert all(leg["client_order_id"] is None for leg in legs)
    sent_messages = [call.args[0] for call in notifier.send.await_args_list]
    assert any("EXIT SIGNAL: AAA/USDT|BBB/USDT" in message for message in sent_messages)
    assert any("liquidity_below_min" in message for message in sent_messages)


@pytest.mark.asyncio
async def test_global_capital_slot_blocks_second_entry_in_same_tick(
    monkeypatch,
    state,
    notifier,
    state_only_order_execution,
):
    high_rank = _pair("HIGH/USDT", "BBB/USDT", sharpe=3.0)
    low_rank = _pair("LOW/USDT", "DDD/USDT", sharpe=0.5)
    monkeypatch.setattr("src.engine.trader.runtime.tick._fetch_pair_candles", _fake_candles)
    monkeypatch.setattr(
        "src.engine.trader.runtime.tick.evaluate_signal",
        lambda **kwargs: _signal("LONG_SPREAD"),
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
            max_open_positions=1,
            require_entry_signal=True,
        ),
        pair_queue_enabled=True,
    )

    open_positions = state.get_open_positions()
    assert len(open_positions) == 1
    assert open_positions[0]["pair_label"] == "HIGH/USDT|BBB/USDT"
    sent_messages = [call.args[0] for call in notifier.send.await_args_list]
    assert any("ENTRY SIGNAL: HIGH/USDT|BBB/USDT" in message for message in sent_messages)
    assert any("capital_slots_full" in message for message in sent_messages)


@pytest.mark.asyncio
async def test_asset_capital_slot_blocks_new_entry_without_closing_existing_position(
    monkeypatch,
    state,
    notifier,
    state_only_order_execution,
):
    state.open_position(
        "AAA/USDT|BBB/USDT",
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
        lambda **kwargs: _signal("LONG_SPREAD"),
    )

    await execute_tick(
        pairs=[_pair("CCC/USDT", "AAA/USDT")],
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
            block_on_missing_validity=False,
            max_positions_per_pair=2,
            max_positions_per_asset=1,
            require_entry_signal=True,
        ),
        pair_queue_enabled=True,
    )

    open_positions = state.get_open_positions()
    assert len(open_positions) == 1
    assert open_positions[0]["pair_label"] == "AAA/USDT|BBB/USDT"
    sent_messages = [call.args[0] for call in notifier.send.await_args_list]
    assert any("asset_position_limit_reached" in message for message in sent_messages)


@pytest.mark.asyncio
async def test_pair_capital_slot_blocks_flip_replacement_entry(
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
        lambda **kwargs: _signal("SHORT_SPREAD"),
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
            block_on_missing_validity=False,
            max_positions_per_pair=1,
            require_entry_signal=True,
        ),
        pair_queue_enabled=True,
    )

    assert state.get_open_positions() == []
    assert len(state.get_all_closed()) == 1
    sent_messages = [call.args[0] for call in notifier.send.await_args_list]
    assert any("EXIT SIGNAL: AAA/USDT|BBB/USDT" in message for message in sent_messages)
    assert any("pair_position_limit_reached" in message for message in sent_messages)


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
