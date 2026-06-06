"""
Tests for the unified Exchange Client.
Mocks CCXT to verify data flow without network access.
"""

import pytest
import ccxt.async_support as ccxt
from unittest.mock import AsyncMock

from src.exchange.data.ccxt_adapter import CcxtMarketDataAdapter
from src.exchange.config.venue import load_ccxt_exchange_config
from src.exchange.data.market_data import (
    create_configured_ccxt_exchange,
    fetch_klines,
    fetch_universe,
)


def _exchange_config(path: str = "configs/exchange/market_profiles/linear_usdt_swap.yml"):
    return load_ccxt_exchange_config(path)


def test_create_configured_ccxt_exchange_valid():
    """Valid CCXT exchange ID should return an exchange instance."""
    exchange = create_configured_ccxt_exchange(
        "bybit",
        "test_key",
        "test_secret",
        _exchange_config(),
    )
    assert exchange is not None
    assert exchange.apiKey == "test_key"
    assert exchange.options["defaultType"] == "swap"
    assert exchange.options["defaultSubType"] == "linear"
    assert exchange.options["defaultSettle"] == "USDT"
    assert exchange.options["adjustForTimeDifference"] is True
    assert exchange.options["recvWindow"] == 10_000
    assert exchange.options["fetchMarkets"]["types"] == ["linear"]


def test_create_configured_ccxt_exchange_invalid():
    """Invalid exchange ID should raise ValueError."""
    with pytest.raises(ValueError, match="Unknown CCXT exchange ID"):
        create_configured_ccxt_exchange(
            "nonexistent_exchange_xyz",
            "key",
            "secret",
            _exchange_config(),
        )


@pytest.mark.asyncio
async def test_fetch_universe_filters_by_volume():
    """Should only return tickers above the volume threshold."""
    mock_exchange = AsyncMock()
    mock_exchange.id = "bybit"
    mock_exchange.load_markets.return_value = {
        "BTC/USDT:USDT": {
            "type": "swap",
            "linear": True,
            "settle": "USDT",
        },
        "ETH/USDT:USDT": {
            "type": "swap",
            "linear": True,
            "settle": "USDT",
        },
        "DEAD/USDT:USDT": {
            "type": "swap",
            "linear": True,
            "settle": "USDT",
        },
        "BTC/USDC:USDC": {
            "type": "swap",
            "linear": True,
            "settle": "USDC",
        },
        "BTC/USDT": {"type": "spot", "spot": True},
    }
    mock_exchange.fetch_tickers.return_value = {
        "BTC/USDT:USDT": {"symbol": "BTC/USDT:USDT", "quoteVolume": 500_000_000},
        "ETH/USDT:USDT": {"symbol": "ETH/USDT:USDT", "quoteVolume": 250_000_000},
        "DEAD/USDT:USDT": {"symbol": "DEAD/USDT:USDT", "quoteVolume": 500},
        "BTC/USDC:USDC": {"symbol": "BTC/USDC:USDC", "quoteVolume": 500_000_000},
        "BTC/USDT": {"symbol": "BTC/USDT", "quoteVolume": 500_000_000},
    }

    universe = await fetch_universe(
        mock_exchange,
        min_volume=1_000_000,
        exchange_config=_exchange_config(),
    )

    assert len(universe) == 2
    assert "BTC/USDT:USDT" in universe
    assert "ETH/USDT:USDT" in universe
    assert "DEAD/USDT:USDT" not in universe
    assert "BTC/USDC:USDC" not in universe
    assert "BTC/USDT" not in universe


@pytest.mark.asyncio
async def test_fetch_universe_uses_configured_spot_contract():
    mock_exchange = AsyncMock()
    mock_exchange.id = "bybit"
    mock_exchange.load_markets.return_value = {
        "BTC/USDT:USDT": {
            "type": "swap",
            "linear": True,
            "settle": "USDT",
        },
        "BTC/USDT": {"type": "spot", "spot": True},
    }
    mock_exchange.fetch_tickers.return_value = {
        "BTC/USDT:USDT": {"symbol": "BTC/USDT:USDT", "quoteVolume": 500_000_000},
        "BTC/USDT": {"symbol": "BTC/USDT", "quoteVolume": 500_000_000},
    }

    universe = await fetch_universe(
        mock_exchange,
        min_volume=1_000_000,
        exchange_config=_exchange_config("configs/exchange/market_profiles/spot.yml"),
    )

    assert universe == ["BTC/USDT"]


@pytest.mark.asyncio
async def test_fetch_klines_network_failure():
    """Network error should be caught and re-raised as RuntimeError."""
    mock_exchange = AsyncMock()
    mock_exchange.id = "bybit"
    mock_exchange.fetch_ohlcv.side_effect = ccxt.NetworkError("502 Bad Gateway")

    with pytest.raises(RuntimeError, match="NetworkError"):
        await fetch_klines(
            exchange=mock_exchange,
            symbol="BTC/USDT:USDT",
            timeframe="4h",
            limit=100,
        )


@pytest.mark.asyncio
async def test_fetch_klines_preserves_ccxt_symbol():
    mock_exchange = AsyncMock()
    mock_exchange.id = "bybit"
    mock_exchange.fetch_ohlcv.return_value = [
        [1600000000000, 100.0, 101.0, 99.0, 100.5, 1000.0],
    ]

    df = await fetch_klines(
        exchange=mock_exchange,
        symbol="BTC/USDT:USDT",
        timeframe="4h",
        limit=100,
    )

    mock_exchange.fetch_ohlcv.assert_awaited_once_with(
        "BTC/USDT:USDT",
        "4h",
        limit=100,
        since=None,
    )
    assert df["close"].iloc[0] == 100.5
    assert df["timestamp"].iloc[0] == 1600000000000


@pytest.mark.asyncio
async def test_fetch_klines_applies_requested_window_after_exchange_fetch():
    mock_exchange = AsyncMock()
    mock_exchange.id = "bybit"
    mock_exchange.fetch_ohlcv.return_value = [
        [1600000000000, 100.0, 101.0, 99.0, 100.5, 1000.0],
        [1600000060000, 101.0, 102.0, 100.0, 101.5, 1000.0],
        [1600000120000, 102.0, 103.0, 101.0, 102.5, 1000.0],
    ]

    df = await fetch_klines(
        exchange=mock_exchange,
        symbol="BTC/USDT:USDT",
        timeframe="1m",
        limit=100,
        since=1600000060000,
        end_ts=1600000060000,
    )

    mock_exchange.fetch_ohlcv.assert_awaited_once_with(
        "BTC/USDT:USDT",
        "1m",
        limit=100,
        since=1600000060000,
    )
    assert df["timestamp"].tolist() == [1600000060000]


@pytest.mark.asyncio
async def test_ccxt_market_data_adapter_uses_injected_exchange_without_owning_close():
    mock_exchange = AsyncMock()
    mock_exchange.id = "bybit"
    mock_exchange.fetch_ohlcv.return_value = [
        [1600000000000, 100.0, 101.0, 99.0, 100.5, 1000.0],
    ]
    adapter = CcxtMarketDataAdapter(
        "bybit",
        "key",
        "secret",
        _exchange_config(),
        exchange=mock_exchange,
    )

    df = await adapter.fetch_ohlcv("BTC/USDT:USDT", "1m", 5)
    await adapter.close()

    assert df["timestamp"].tolist() == [1600000000000]
    mock_exchange.fetch_ohlcv.assert_awaited_once()
    mock_exchange.close.assert_not_awaited()
