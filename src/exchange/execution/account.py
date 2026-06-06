"""CCXT-backed read-only exchange account snapshots."""

from collections.abc import Callable
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from src.exchange.config.venue import CcxtExchangeConfig
from src.exchange.data.market_data import create_configured_ccxt_exchange

ExchangeFactory = Callable[[str, str, str, CcxtExchangeConfig], Any]


class ExchangePositionSnapshot(BaseModel):
    """One exchange-side position from a read-only account snapshot."""

    model_config = ConfigDict(extra="allow")

    symbol: str
    side: str
    qty: float = Field(gt=0)
    spread_id: int | None = None

    @property
    def normalized_side(self) -> str:
        side = self.side.upper()
        if side in {"BUY", "LONG"}:
            return "BUY"
        if side in {"SELL", "SHORT"}:
            return "SELL"
        return side


class ExchangeSnapshotProvider(Protocol):
    """Read-only provider for exchange/account positions."""

    async def fetch_open_positions(self) -> list[ExchangePositionSnapshot]:
        """Fetch open exchange positions without mutating exchange state."""


class _CCXTPositionRow(BaseModel):
    """Structured subset of one normalized CCXT position row."""

    model_config = ConfigDict(extra="allow")

    symbol: str
    side: str | None = None
    contracts: float | None = None


class CCXTReadOnlySnapshotProvider:
    """Fetch open account positions through CCXT without exchange mutation."""

    def __init__(
        self,
        exchange_id: str,
        api_key: str,
        api_secret: str,
        exchange_config: CcxtExchangeConfig,
        exchange_factory: ExchangeFactory = create_configured_ccxt_exchange,
    ):
        self.exchange_id = exchange_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.exchange_config = exchange_config
        self.exchange_factory = exchange_factory

    async def fetch_open_positions(self) -> list[ExchangePositionSnapshot]:
        """Fetch and normalize non-zero exchange positions."""
        exchange = self.exchange_factory(
            self.exchange_id,
            self.api_key,
            self.api_secret,
            self.exchange_config,
        )
        try:
            positions = await exchange.fetch_positions()
            return [
                snapshot
                for position in positions
                if (snapshot := _snapshot_from_ccxt_position(position)) is not None
            ]
        finally:
            await exchange.close()


def _snapshot_from_ccxt_position(
    position: dict[str, Any],
) -> ExchangePositionSnapshot | None:
    row = _CCXTPositionRow.model_validate(position)
    qty = float(row.contracts or 0.0)
    if qty <= 0:
        return None
    if row.side is None:
        raise ValueError(f"Open exchange position is missing side: {row.symbol}")
    return ExchangePositionSnapshot(
        symbol=row.symbol,
        side=row.side,
        qty=qty,
    )
