import pytest

from src.engine.trader.config import OrderExecutionConfig
from src.engine.trader.execution.orders import (
    OrderRejected,
    OrderStatusSnapshot,
    OrderSubmissionResult,
    execute_spread_leg_orders,
)
from src.engine.trader.state_manager import TradeStateManager


class FakeOrderAdapter:
    def __init__(self, submit_result=None, polls=None, cancel_result=None, submit_exc=None):
        self.submit_result = submit_result
        self.polls = list(polls or [])
        self.cancel_result = cancel_result
        self.submit_exc = submit_exc
        self.submitted_requests = []
        self.cancelled_orders = []

    async def submit_market_order(self, request):
        self.submitted_requests.append(request)
        if self.submit_exc is not None:
            raise self.submit_exc
        return self.submit_result

    async def fetch_order_status(self, symbol, exchange_order_id):
        return self.polls.pop(0)

    async def cancel_order(self, symbol, exchange_order_id):
        self.cancelled_orders.append((symbol, exchange_order_id))
        return self.cancel_result


@pytest.fixture
def state():
    mgr = TradeStateManager(db_path=":memory:")
    yield mgr
    mgr.close()


def _live_config(cancel_unfilled_after_poll=False):
    return OrderExecutionConfig(
        mode="live",
        fill_poll_attempts=1,
        fill_poll_interval_seconds=0.0,
        cancel_unfilled_after_poll=cancel_unfilled_after_poll,
        client_order_prefix="test",
    )


def _state_only_config():
    return OrderExecutionConfig(
        mode="state_only",
        fill_poll_attempts=0,
        fill_poll_interval_seconds=0.0,
        cancel_unfilled_after_poll=False,
        client_order_prefix="test",
    )


def _open_spread(state):
    return state.open_position(
        pair_label="BTC/USDT|ETH/USDT",
        asset_x="BTC/USDT",
        asset_y="ETH/USDT",
        side="LONG_SPREAD",
        entry_price_a=100.0,
        entry_price_b=50.0,
        weight_a=0.6,
        weight_b=0.4,
        entry_z=-2.0,
        lookback_bars=21,
    )


@pytest.mark.asyncio
async def test_state_only_order_execution_does_not_submit_or_change_leg_status(state):
    spread_id = _open_spread(state)
    adapter = FakeOrderAdapter()

    outcomes = await execute_spread_leg_orders(
        state=state,
        spread_id=spread_id,
        leg_role="OPEN",
        config=_state_only_config(),
        adapter=adapter,
    )

    assert outcomes == []
    assert adapter.submitted_requests == []
    assert [leg["status"] for leg in state.get_leg_fills(spread_id=spread_id)] == [
        "TARGET_RECORDED",
        "TARGET_RECORDED",
    ]


@pytest.mark.asyncio
async def test_live_order_executor_records_submit_ack_and_filled(state):
    spread_id = _open_spread(state)
    adapter = FakeOrderAdapter(
        submit_result=OrderSubmissionResult(
            exchange_order_id="ex-1",
            status="open",
            filled_qty=0.0,
            avg_fill_price=None,
        ),
        polls=[
            OrderStatusSnapshot(status="filled", filled_qty=0.6, avg_fill_price=101.0),
            OrderStatusSnapshot(status="filled", filled_qty=0.4, avg_fill_price=50.5),
        ],
    )

    outcomes = await execute_spread_leg_orders(
        state=state,
        spread_id=spread_id,
        leg_role="OPEN",
        config=_live_config(),
        adapter=adapter,
    )

    legs = state.get_leg_fills(spread_id=spread_id)
    assert [leg["status"] for leg in legs] == ["FILLED", "FILLED"]
    assert [leg["filled_qty"] for leg in legs] == [0.6, 0.4]
    assert [request.client_order_id for request in adapter.submitted_requests] == [
        "test-1-open-1",
        "test-1-open-2",
    ]
    assert [outcome.status for outcome in outcomes] == ["FILLED", "FILLED"]


@pytest.mark.asyncio
async def test_live_order_executor_can_cancel_unfilled_order_after_poll_window(state):
    spread_id = _open_spread(state)
    adapter = FakeOrderAdapter(
        submit_result=OrderSubmissionResult(
            exchange_order_id="ex-1",
            status="open",
            filled_qty=0.0,
            avg_fill_price=None,
        ),
        polls=[
            OrderStatusSnapshot(status="partially_filled", filled_qty=0.25, avg_fill_price=101.0),
            OrderStatusSnapshot(status="partially_filled", filled_qty=0.1, avg_fill_price=50.0),
        ],
        cancel_result=OrderStatusSnapshot(status="cancelled", filled_qty=0.25, avg_fill_price=101.0),
    )

    outcomes = await execute_spread_leg_orders(
        state=state,
        spread_id=spread_id,
        leg_role="OPEN",
        config=_live_config(cancel_unfilled_after_poll=True),
        adapter=adapter,
    )

    assert [outcome.status for outcome in outcomes] == ["CANCELLED", "CANCELLED"]
    assert len(adapter.cancelled_orders) == 2
    assert [leg["status"] for leg in state.get_leg_fills(spread_id=spread_id)] == [
        "CANCELLED",
        "CANCELLED",
    ]


@pytest.mark.asyncio
async def test_live_order_executor_records_rejection_without_exchange_mutation_retry(state):
    spread_id = _open_spread(state)
    adapter = FakeOrderAdapter(submit_exc=OrderRejected("minimum quantity rejected"))

    outcomes = await execute_spread_leg_orders(
        state=state,
        spread_id=spread_id,
        leg_role="OPEN",
        config=_live_config(),
        adapter=adapter,
    )

    assert [outcome.status for outcome in outcomes] == ["REJECTED", "REJECTED"]
    assert [leg["status"] for leg in state.get_leg_fills(spread_id=spread_id)] == [
        "REJECTED",
        "REJECTED",
    ]
