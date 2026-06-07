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
    print(
        "\nTEST: Live smoke test that fetches five 4h BTC/USDT candles from Bybit "
        "through the CCXT market-data adapter."
    )

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
    print(
        "\nTEST: Live smoke test that fetches three 1m BTC/USDT candles from Bybit "
        "to confirm short-timeframe data works."
    )

    async def _run():
        async with CcxtMarketDataAdapter("bybit", "", "", _exchange_config()) as adapter:
            df = await adapter.fetch_ohlcv("BTC/USDT:USDT", "1m", 3)
        assert len(df) == 3
        assert df["close"].iloc[-1] > 0

    asyncio.run(_run())


@pytest.mark.live
def test_mega_cap_pair_available():
    """Verify a mega-cap pair (ETH/USDT) exists on Bybit."""
    print(
        "\nTEST: Live smoke test that confirms ETH/USDT is available and returns "
        "positive OHLCV close prices."
    )

    async def _run():
        async with CcxtMarketDataAdapter("bybit", "", "", _exchange_config()) as adapter:
            df = await adapter.fetch_ohlcv("ETH/USDT:USDT", "4h", 3)
        assert len(df) >= 1
        assert df["close"].iloc[-1] > 0

    asyncio.run(_run())


@pytest.mark.live
def test_bybit_funding_rate_history():
    """Verify we can fetch funding rate history from Bybit."""
    print(
        "\nTEST: Live smoke test that fetches historical funding rates for "
        "BTC/USDT:USDT from Bybit through the CCXT market-data adapter."
    )

    async def _run():
        async with CcxtMarketDataAdapter("bybit", "", "", _exchange_config()) as adapter:
            df = await adapter.fetch_funding_rate_history("BTC/USDT:USDT", limit=5)
        
        assert len(df) > 0
        assert "timestamp" in df.columns
        assert "funding_rate" in df.columns
        assert df["funding_rate"].dtype == "float64"
        return df

    df = asyncio.run(_run())
    print(f"\n  Latest BTC/USDT funding rate: {df['funding_rate'].iloc[-1]} at {df['timestamp'].iloc[-1]}")

