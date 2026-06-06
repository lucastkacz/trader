"""Guarded live order execution for recorded spread leg targets."""

import asyncio
from dataclasses import dataclass
from typing import Any

from src.engine.trader.config import OrderExecutionConfig
from src.engine.trader.state.order_lifecycle import LegOrderStatus
from src.engine.trader.state.manager import TradeStateManager
from src.exchange.execution.orders import (
    OrderExecutionAdapter,
    OrderRejected,
    OrderStatusSnapshot,
    OrderSubmissionRequest,
)


@dataclass(frozen=True)
class LegOrderExecutionOutcome:
    """Final local outcome for one attempted leg execution."""

    leg_fill_id: int
    status: str
    submitted: bool
    exchange_order_id: str | None
    message: str


async def execute_spread_leg_orders(
    state: TradeStateManager,
    spread_id: int,
    leg_role: str,
    config: OrderExecutionConfig,
    adapter: OrderExecutionAdapter | None,
) -> list[LegOrderExecutionOutcome]:
    """Execute recorded leg targets when explicitly configured for live orders."""
    if config.mode == "state_only":
        return []

    if adapter is None:
        raise RuntimeError("Live order execution requires an OrderExecutionAdapter")

    outcomes = []
    legs = [
        leg for leg in state.get_leg_fills(spread_id=spread_id)
        if leg["leg_role"] == leg_role and leg["status"] == LegOrderStatus.TARGET_RECORDED.value
    ]

    for leg in legs:
        outcomes.append(await _execute_one_leg(state=state, leg=leg, config=config, adapter=adapter))

    return outcomes


async def _execute_one_leg(
    state: TradeStateManager,
    leg: dict[str, Any],
    config: OrderExecutionConfig,
    adapter: OrderExecutionAdapter,
) -> LegOrderExecutionOutcome:
    request = OrderSubmissionRequest(
        leg_fill_id=leg["id"],
        spread_id=leg["spread_id"],
        symbol=leg["symbol"],
        side=leg["side"],
        quantity=float(leg["target_qty"]),
        client_order_id=_client_order_id(config=config, leg=leg),
    )

    state.record_leg_submit_requested(request.leg_fill_id, client_order_id=request.client_order_id)
    try:
        submitted = await adapter.submit_market_order(request)
    except OrderRejected as exc:
        state.record_leg_rejected(request.leg_fill_id, reason=str(exc))
        return _outcome(leg_fill_id=request.leg_fill_id, status="REJECTED", message=str(exc))
    except Exception as exc:
        state.record_leg_failed(request.leg_fill_id, reason=str(exc))
        return _outcome(leg_fill_id=request.leg_fill_id, status="FAILED", message=str(exc))

    state.record_leg_acknowledged(
        request.leg_fill_id,
        exchange_order_id=submitted.exchange_order_id,
        client_order_id=request.client_order_id,
    )
    _apply_order_status_snapshot(
        state=state,
        leg_fill_id=request.leg_fill_id,
        snapshot=OrderStatusSnapshot(
            status=submitted.status,
            filled_qty=submitted.filled_qty,
            avg_fill_price=submitted.avg_fill_price,
        ),
    )

    if _current_leg_status(state, request.leg_fill_id) in _TERMINAL_STATUSES:
        return _outcome_from_state(state, request.leg_fill_id, submitted.exchange_order_id)

    for _ in range(config.fill_poll_attempts):
        if config.fill_poll_interval_seconds > 0:
            await asyncio.sleep(config.fill_poll_interval_seconds)
        snapshot = await adapter.fetch_order_status(
            symbol=request.symbol,
            exchange_order_id=submitted.exchange_order_id,
        )
        _apply_order_status_snapshot(state=state, leg_fill_id=request.leg_fill_id, snapshot=snapshot)
        if _current_leg_status(state, request.leg_fill_id) in _TERMINAL_STATUSES:
            return _outcome_from_state(state, request.leg_fill_id, submitted.exchange_order_id)

    if config.cancel_unfilled_after_poll:
        state.record_leg_cancel_requested(request.leg_fill_id)
        try:
            snapshot = await adapter.cancel_order(
                symbol=request.symbol,
                exchange_order_id=submitted.exchange_order_id,
            )
        except Exception as exc:
            state.record_leg_failed(request.leg_fill_id, reason=str(exc))
            return _outcome_from_state(state, request.leg_fill_id, submitted.exchange_order_id)
        _apply_order_status_snapshot(state=state, leg_fill_id=request.leg_fill_id, snapshot=snapshot)

    return _outcome_from_state(state, request.leg_fill_id, submitted.exchange_order_id)


def _apply_order_status_snapshot(
    state: TradeStateManager,
    leg_fill_id: int,
    snapshot: OrderStatusSnapshot,
) -> None:
    normalized = _normalize_exchange_status(snapshot.status)
    if normalized == "OPEN":
        return
    if normalized == "PARTIALLY_FILLED":
        state.record_leg_partially_filled(
            leg_fill_id,
            filled_qty=snapshot.filled_qty,
            avg_fill_price=_required_price(snapshot),
        )
    elif normalized == "FILLED":
        state.record_leg_filled(
            leg_fill_id,
            filled_qty=snapshot.filled_qty,
            avg_fill_price=snapshot.avg_fill_price,
        )
    elif normalized == "CANCELLED":
        if _current_leg_status(state, leg_fill_id) != LegOrderStatus.CANCEL_REQUESTED.value:
            state.record_leg_cancel_requested(leg_fill_id)
        state.record_leg_cancelled(leg_fill_id)
    elif normalized == "REJECTED":
        state.record_leg_failed(leg_fill_id, reason="exchange reported rejected after acknowledgement")
    elif normalized == "FAILED":
        state.record_leg_failed(leg_fill_id, reason="exchange reported failed")


def _normalize_exchange_status(status: str) -> str:
    normalized = status.upper().replace("-", "_")
    aliases = {
        "OPEN": "OPEN",
        "NEW": "OPEN",
        "PARTIAL": "PARTIALLY_FILLED",
        "PARTIALLY_FILLED": "PARTIALLY_FILLED",
        "CLOSED": "FILLED",
        "FILLED": "FILLED",
        "CANCELED": "CANCELLED",
        "CANCELLED": "CANCELLED",
        "REJECTED": "REJECTED",
        "FAILED": "FAILED",
    }
    if normalized not in aliases:
        raise RuntimeError(f"Unsupported exchange order status: {status}")
    return aliases[normalized]


def _required_price(snapshot: OrderStatusSnapshot) -> float:
    if snapshot.avg_fill_price is None:
        raise ValueError("Fill snapshot requires avg_fill_price")
    return snapshot.avg_fill_price


def _client_order_id(config: OrderExecutionConfig, leg: dict[str, Any]) -> str:
    return f"{config.client_order_prefix}-{leg['spread_id']}-{leg['leg_role'].lower()}-{leg['id']}"


def _current_leg_status(state: TradeStateManager, leg_fill_id: int) -> str:
    leg = next(row for row in state.get_leg_fills() if row["id"] == leg_fill_id)
    return leg["status"]


def _outcome_from_state(
    state: TradeStateManager,
    leg_fill_id: int,
    exchange_order_id: str,
) -> LegOrderExecutionOutcome:
    leg = next(row for row in state.get_leg_fills() if row["id"] == leg_fill_id)
    return LegOrderExecutionOutcome(
        leg_fill_id=leg_fill_id,
        status=leg["status"],
        submitted=True,
        exchange_order_id=exchange_order_id,
        message="live order lifecycle recorded",
    )


def _outcome(
    leg_fill_id: int,
    status: str,
    message: str,
) -> LegOrderExecutionOutcome:
    return LegOrderExecutionOutcome(
        leg_fill_id=leg_fill_id,
        status=status,
        submitted=False,
        exchange_order_id=None,
        message=message,
    )


_TERMINAL_STATUSES = {
    LegOrderStatus.FILLED.value,
    LegOrderStatus.CANCELLED.value,
    LegOrderStatus.FAILED.value,
    LegOrderStatus.REJECTED.value,
}
