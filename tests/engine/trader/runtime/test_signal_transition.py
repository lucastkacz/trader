from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.engine.trader.config import OrderExecutionConfig
from src.engine.trader.runtime.signal_transition import route_signal_transition


class FakeState:
    def __init__(self, pnl):
        self.pnl = pnl
        self.opened = []
        self.closed = []

    def get_position_for_pair(self, pair_label):
        return {"id": 42, "pair_label": pair_label}

    def close_position(self, **kwargs):
        self.closed.append(kwargs)
        return self.pnl

    def open_position(self, **kwargs):
        self.opened.append(kwargs)
        return 43


@pytest.fixture
def state_only_order_execution():
    return OrderExecutionConfig(
        mode="state_only",
        fill_poll_attempts=0,
        fill_poll_interval_seconds=0.0,
        cancel_unfilled_after_poll=False,
        client_order_prefix="test",
    )


def _result(signal):
    return SimpleNamespace(
        signal=signal,
        price_a=100.0,
        price_b=50.0,
        weight_a=0.6,
        weight_b=0.4,
        z_score=0.5,
    )


@pytest.mark.asyncio
async def test_exit_notification_formats_missing_pnl_as_na(monkeypatch, state_only_order_execution):
    notifier = SimpleNamespace(send=AsyncMock())
    state = FakeState(pnl=None)
    monkeypatch.setattr(
        "src.engine.trader.runtime.signal_transition._execute_leg_orders",
        AsyncMock(),
    )

    await route_signal_transition(
        pair={"Asset_X": "BTC/USDT", "Asset_Y": "ETH/USDT"},
        pair_label="BTC/USDT|ETH/USDT",
        current_side="LONG_SPREAD",
        result=_result("FLAT"),
        lookback_bars=21,
        timeframe="1m",
        state=state,
        notifier=notifier,
        order_execution_cfg=state_only_order_execution,
        order_execution_adapter=None,
    )

    message = notifier.send.await_args.args[0]
    assert "PNL: <b>N/A</b>" in message
    assert "if pnl else" not in message


@pytest.mark.asyncio
async def test_exit_notification_formats_zero_pnl_as_zero(monkeypatch, state_only_order_execution):
    notifier = SimpleNamespace(send=AsyncMock())
    state = FakeState(pnl=0.0)
    monkeypatch.setattr(
        "src.engine.trader.runtime.signal_transition._execute_leg_orders",
        AsyncMock(),
    )

    await route_signal_transition(
        pair={"Asset_X": "BTC/USDT", "Asset_Y": "ETH/USDT"},
        pair_label="BTC/USDT|ETH/USDT",
        current_side="LONG_SPREAD",
        result=_result("FLAT"),
        lookback_bars=21,
        timeframe="1m",
        state=state,
        notifier=notifier,
        order_execution_cfg=state_only_order_execution,
        order_execution_adapter=None,
    )

    message = notifier.send.await_args.args[0]
    assert "PNL: <b>0.00%</b>" in message


@pytest.mark.asyncio
async def test_flip_notification_formats_pnl(monkeypatch, state_only_order_execution):
    notifier = SimpleNamespace(send=AsyncMock())
    state = FakeState(pnl=0.0123)
    monkeypatch.setattr(
        "src.engine.trader.runtime.signal_transition._execute_leg_orders",
        AsyncMock(),
    )

    await route_signal_transition(
        pair={"Asset_X": "BTC/USDT", "Asset_Y": "ETH/USDT"},
        pair_label="BTC/USDT|ETH/USDT",
        current_side="LONG_SPREAD",
        result=_result("SHORT_SPREAD"),
        lookback_bars=21,
        timeframe="1m",
        state=state,
        notifier=notifier,
        order_execution_cfg=state_only_order_execution,
        order_execution_adapter=None,
    )

    message = notifier.send.await_args.args[0]
    assert "Old Side Closed | PNL: <b>1.23%</b>" in message
    assert "if pnl else" not in message
