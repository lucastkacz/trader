"""
Tests for the unified Exchange Client.
Mocks CCXT to verify data flow without network access.
"""

import pytest
import ccxt.async_support as ccxt
from unittest.mock import AsyncMock

from src.data.fetcher.exchange_client import create_exchange, fetch_universe, fetch_klines


def test_create_exchange_valid():
    """Valid CCXT exchange ID should return an exchange instance."""
    exchange = create_exchange("bybit", "test_key", "test_secret")
    assert exchange is not None
    assert exchange.apiKey == "test_key"


def test_create_exchange_invalid():
    """Invalid exchange ID should raise ValueError."""
    with pytest.raises(ValueError, match="Unknown CCXT exchange ID"):
        create_exchange("nonexistent_exchange_xyz", "key", "secret")


@pytest.mark.asyncio
async def test_fetch_universe_filters_by_volume():
    """Should only return tickers above the volume threshold."""
    mock_exchange = AsyncMock()
    mock_exchange.id = "bybit"
    mock_exchange.fetch_tickers.return_value = {
        "BTC/USDT:USDT": {"symbol": "BTC/USDT:USDT", "quoteVolume": 500_000_000},
        "ETH/USDT:USDT": {"symbol": "ETH/USDT:USDT", "quoteVolume": 250_000_000},
        "DEAD/USDT:USDT": {"symbol": "DEAD/USDT:USDT", "quoteVolume": 500},
    }

    universe = await fetch_universe(mock_exchange, min_volume=1_000_000)

    assert len(universe) == 2
    assert "BTC/USDT" in universe
    assert "ETH/USDT" in universe
    assert "DEAD/USDT" not in universe


@pytest.mark.asyncio
async def test_fetch_klines_network_failure():
    """Network error should be caught and re-raised as RuntimeError."""
    mock_exchange = AsyncMock()
    mock_exchange.id = "bybit"
    mock_exchange.fetch_ohlcv.side_effect = ccxt.NetworkError("502 Bad Gateway")

    with pytest.raises(RuntimeError, match="NetworkError"):
        await fetch_klines(
            exchange=mock_exchange,
            symbol="BTC/USDT",
            timeframe="4h",
            limit=100,
        )
