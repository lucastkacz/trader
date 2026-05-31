"""CCXT-backed read-only exchange position snapshots."""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict

from src.data.fetcher.exchange_client import create_exchange
from src.data.fetcher.symbols import to_display_symbol
from src.engine.trader.reconciliation.service import ExchangePositionSnapshot

ExchangeFactory = Callable[[str, str, str], Any]


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
        exchange_factory: ExchangeFactory = create_exchange,
    ):
        self.exchange_id = exchange_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.exchange_factory = exchange_factory

    async def fetch_open_positions(self) -> list[ExchangePositionSnapshot]:
        """Fetch and normalize non-zero exchange positions."""
        exchange = self.exchange_factory(
            self.exchange_id,
            self.api_key,
            self.api_secret,
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
        symbol=to_display_symbol(row.symbol),
        side=row.side,
        qty=qty,
    )
