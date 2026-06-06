"""CCXT-backed exchange order execution adapter."""

from dataclasses import dataclass
from typing import Any, Protocol

from src.exchange.config.venue import CcxtExchangeConfig
from src.exchange.data.market_data import create_configured_ccxt_exchange


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

    async def cancel_order(
        self,
        symbol: str,
        exchange_order_id: str,
    ) -> OrderStatusSnapshot:
        """Cancel one exchange order and return its terminal status."""


class CCXTOrderExecutionAdapter:
    """CCXT-backed live order adapter.

    This adapter is intentionally only used when order_execution.mode is
    explicitly "live"; unit tests inject fakes and never reach the network.
    """

    def __init__(
        self,
        exchange_id: str,
        api_key: str,
        api_secret: str,
        exchange_config: CcxtExchangeConfig,
    ):
        self.exchange_id = exchange_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.exchange_config = exchange_config

    async def submit_market_order(
        self,
        request: OrderSubmissionRequest,
    ) -> OrderSubmissionResult:
        exchange = create_configured_ccxt_exchange(
            self.exchange_id,
            self.api_key,
            self.api_secret,
            self.exchange_config,
        )
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
        exchange = create_configured_ccxt_exchange(
            self.exchange_id,
            self.api_key,
            self.api_secret,
            self.exchange_config,
        )
        ccxt_symbol = _to_ccxt_derivative_symbol(symbol)
        try:
            await exchange.load_markets()
            order = await exchange.fetch_order(exchange_order_id, ccxt_symbol)
            return _status_snapshot_from_ccxt_order(order)
        finally:
            await exchange.close()

    async def cancel_order(
        self,
        symbol: str,
        exchange_order_id: str,
    ) -> OrderStatusSnapshot:
        exchange = create_configured_ccxt_exchange(
            self.exchange_id,
            self.api_key,
            self.api_secret,
            self.exchange_config,
        )
        ccxt_symbol = _to_ccxt_derivative_symbol(symbol)
        try:
            await exchange.load_markets()
            order = await exchange.cancel_order(exchange_order_id, ccxt_symbol)
            return _status_snapshot_from_ccxt_order(order)
        finally:
            await exchange.close()


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
            float(order["average"]) if order.get("average") is not None else None
        ),
    )


def _to_ccxt_derivative_symbol(symbol: str) -> str:
    return symbol
