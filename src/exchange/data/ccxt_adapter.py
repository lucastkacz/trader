"""CCXT read-only market-data adapter."""

from __future__ import annotations

import pandas as pd
import ccxt.async_support as ccxt

from src.exchange.config.venue import CcxtExchangeConfig
from src.exchange.data.market_data import (
    create_configured_ccxt_exchange,
    fetch_funding_rate_history,
    fetch_klines,
    fetch_universe,
)


class CcxtMarketDataAdapter:
    """Read-only market-data adapter over a CCXT exchange client."""

    def __init__(
        self,
        exchange_id: str,
        api_key: str,
        api_secret: str,
        exchange_config: CcxtExchangeConfig,
        *,
        exchange: ccxt.Exchange | None = None,
    ) -> None:
        self.exchange_id = exchange_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.exchange_config = exchange_config
        self._exchange = exchange
        self._owns_exchange = exchange is None

    async def __aenter__(self) -> "CcxtMarketDataAdapter":
        self._ensure_exchange()
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        await self.close()

    @property
    def exchange(self) -> ccxt.Exchange:
        return self._ensure_exchange()

    async def close(self) -> None:
        """Close the owned exchange client, if this adapter created it."""
        if self._exchange is not None and self._owns_exchange:
            await self._exchange.close()
            self._exchange = None

    async def fetch_universe(self, min_volume: float) -> list[str]:
        """Fetch configured-market symbols above a quote-volume floor."""
        return await fetch_universe(self.exchange, min_volume, self.exchange_config)

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        *,
        since: int | None = None,
        end_ts: int | None = None,
    ) -> pd.DataFrame:
        """Fetch normalized OHLCV candles for one symbol."""
        return await fetch_klines(
            exchange=self.exchange,
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            since=since,
            end_ts=end_ts,
        )

    async def fetch_funding_rate_history(
        self,
        symbol: str,
        *,
        since: int | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """Fetch historical funding rates for one symbol."""
        return await fetch_funding_rate_history(
            exchange=self.exchange,
            symbol=symbol,
            since=since,
            limit=limit,
        )

    def _ensure_exchange(self) -> ccxt.Exchange:
        if self._exchange is None:
            self._exchange = create_configured_ccxt_exchange(
                self.exchange_id,
                self.api_key,
                self.api_secret,
                self.exchange_config,
            )
            self._owns_exchange = True
        return self._exchange
