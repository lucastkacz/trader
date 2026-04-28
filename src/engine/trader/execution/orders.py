"""Guarded live order execution for recorded spread leg targets."""

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol

from src.data.fetcher.exchange_client import create_exchange
from src.engine.trader.config import OrderExecutionConfig
from src.engine.trader.state.order_lifecycle import LegOrderStatus
from src.engine.trader.state_manager import TradeStateManager


@dataclass(frozen=True)
class OrderSubmissionRequest:
    """One exchange order request derived from a recorded leg target."""

    leg_fill_id: int
    spread_id: int
    symbol: str
    side: str
    quantity: float
    client_order_id: str


@dataclass(frozen=True)
class OrderStatusSnapshot:
    """Exchange-side order status normalized for local lifecycle transitions."""

    status: str
    filled_qty: float
    avg_fill_price: float | None


@dataclass(frozen=True)
class OrderSubmissionResult:
    """Exchange response after order submission."""

    exchange_order_id: str
    status: str
    filled_qty: float
    avg_fill_price: float | None


@dataclass(frozen=True)
class LegOrderExecutionOutcome:
    """Final local outcome for one attempted leg execution."""

    leg_fill_id: int
    status: str
    submitted: bool
    exchange_order_id: str | None
    message: str


class OrderRejected(RuntimeError):
    """Raised when an exchange rejects an order request before acknowledgement."""


class OrderExecutionAdapter(Protocol):
    """Async boundary for live exchange order operations."""

    async def submit_market_order(
        self,
        request: OrderSubmissionRequest,
    ) -> OrderSubmissionResult:
        """Submit one market order."""

    async def fetch_order_status(
        self,
        symbol: str,
        exchange_order_id: str,
    ) -> OrderStatusSnapshot:
        """Fetch current status for one exchange order."""

    async def cancel_order(self, symbol: str, exchange_order_id: str) -> OrderStatusSnapshot:
        """Cancel one exchange order and return its terminal status."""


class CCXTOrderExecutionAdapter:
    """CCXT-backed live order adapter.

    This adapter is intentionally only used when order_execution.mode is
    explicitly "live"; unit tests inject fakes and never reach the network.
    """

    def __init__(self, exchange_id: str, api_key: str, api_secret: str):
        self.exchange_id = exchange_id
        self.api_key = api_key
        self.api_secret = api_secret

    async def submit_market_order(
        self,
        request: OrderSubmissionRequest,
    ) -> OrderSubmissionResult:
        exchange = create_exchange(self.exchange_id, self.api_key, self.api_secret)
        symbol = _to_ccxt_derivative_symbol(request.symbol)
        try:
            await exchange.load_markets()
            amount = float(exchange.amount_to_precision(symbol, request.quantity))
            order = await exchange.create_order(
                symbol=symbol,
                type="market",
                side=request.side.lower(),
                amount=amount,
                price=None,
                params={"clientOrderId": request.client_order_id},
            )
            return _submission_result_from_ccxt_order(order)
        finally:
            await exchange.close()

    async def fetch_order_status(
        self,
        symbol: str,
        exchange_order_id: str,
    ) -> OrderStatusSnapshot:
        exchange = create_exchange(self.exchange_id, self.api_key, self.api_secret)
        ccxt_symbol = _to_ccxt_derivative_symbol(symbol)
        try:
            await exchange.load_markets()
            order = await exchange.fetch_order(exchange_order_id, ccxt_symbol)
            return _status_snapshot_from_ccxt_order(order)
        finally:
            await exchange.close()

    async def cancel_order(self, symbol: str, exchange_order_id: str) -> OrderStatusSnapshot:
        exchange = create_exchange(self.exchange_id, self.api_key, self.api_secret)
        ccxt_symbol = _to_ccxt_derivative_symbol(symbol)
        try:
            await exchange.load_markets()
            order = await exchange.cancel_order(exchange_order_id, ccxt_symbol)
            return _status_snapshot_from_ccxt_order(order)
        finally:
            await exchange.close()


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


def _submission_result_from_ccxt_order(order: dict[str, Any]) -> OrderSubmissionResult:
    exchange_order_id = str(order.get("id") or order.get("clientOrderId") or "")
    if not exchange_order_id:
        raise RuntimeError("Exchange order response did not include an order id")
    snapshot = _status_snapshot_from_ccxt_order(order)
    return OrderSubmissionResult(
        exchange_order_id=exchange_order_id,
        status=snapshot.status,
        filled_qty=snapshot.filled_qty,
        avg_fill_price=snapshot.avg_fill_price,
    )


def _status_snapshot_from_ccxt_order(order: dict[str, Any]) -> OrderStatusSnapshot:
    return OrderStatusSnapshot(
        status=str(order.get("status") or "open"),
        filled_qty=float(order.get("filled") or 0.0),
        avg_fill_price=(
            float(order["average"])
            if order.get("average") is not None else None
        ),
    )


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


def _to_ccxt_derivative_symbol(symbol: str) -> str:
    if ":" in symbol:
        return symbol
    quote_currency = symbol.split("/")[-1]
    return f"{symbol}:{quote_currency}"


_TERMINAL_STATUSES = {
    LegOrderStatus.FILLED.value,
    LegOrderStatus.CANCELLED.value,
    LegOrderStatus.FAILED.value,
    LegOrderStatus.REJECTED.value,
}
