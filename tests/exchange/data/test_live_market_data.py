"""
Tests for live CCXT market-data adapter connectivity.
These tests hit real exchange APIs and require network access.
Mark with @pytest.mark.live so they can be skipped in CI offline tests.
"""

import pytest
import asyncio

from src.exchange.data.ccxt_adapter import CcxtMarketDataAdapter
from src.exchange.config.venue import load_ccxt_exchange_config


def _exchange_config():
    return load_ccxt_exchange_config("configs/exchange/market_profiles/linear_usdt_swap.yml")


@pytest.mark.live
def test_bybit_connectivity_4h():
    """Verify we can fetch 4H candles from Bybit."""
    async def _run():
        async with CcxtMarketDataAdapter("bybit", "", "", _exchange_config()) as adapter:
            df = await adapter.fetch_ohlcv("BTC/USDT:USDT", "4h", 5)
        assert len(df) == 5
        assert "close" in df.columns
        assert df["close"].iloc[-1] > 0
        return df

    df = asyncio.run(_run())
    print(f"\n  Latest BTC/USDT 4H close: {df['close'].iloc[-1]}")


@pytest.mark.live
def test_bybit_connectivity_1m():
    """Verify 1m candles work (needed for turbo mode)."""
    async def _run():
        async with CcxtMarketDataAdapter("bybit", "", "", _exchange_config()) as adapter:
            df = await adapter.fetch_ohlcv("BTC/USDT:USDT", "1m", 3)
        assert len(df) == 3
        assert df["close"].iloc[-1] > 0

    asyncio.run(_run())


@pytest.mark.live
def test_mega_cap_pair_available():
    """Verify a mega-cap pair (ETH/USDT) exists on Bybit."""
    async def _run():
        async with CcxtMarketDataAdapter("bybit", "", "", _exchange_config()) as adapter:
            df = await adapter.fetch_ohlcv("ETH/USDT:USDT", "4h", 3)
        assert len(df) >= 1
        assert df["close"].iloc[-1] > 0

    asyncio.run(_run())
