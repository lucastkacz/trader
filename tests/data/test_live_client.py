"""
Tests for Exchange Connectivity (Live Client).
These tests hit real exchange APIs and require network access.
Mark with @pytest.mark.live so they can be skipped in CI offline tests.
"""

import pytest
import asyncio

from src.data.fetcher.live_client import fetch_live_klines


@pytest.mark.live
def test_bybit_connectivity_4h():
    """Verify we can fetch 4H candles from Bybit."""
    async def _run():
        df = await fetch_live_klines(
            exchange_id="bybit",
            api_key="",
            api_secret="",
            symbol="BTC/USDT",
            timeframe="4h",
            limit=5,
        )
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
        df = await fetch_live_klines(
            exchange_id="bybit",
            api_key="",
            api_secret="",
            symbol="BTC/USDT",
            timeframe="1m",
            limit=3,
        )
        assert len(df) == 3
        assert df["close"].iloc[-1] > 0

    asyncio.run(_run())


@pytest.mark.live
def test_mega_cap_pair_available():
    """Verify a mega-cap pair (ETH/USDT) exists on Bybit."""
    async def _run():
        df = await fetch_live_klines(
            exchange_id="bybit",
            api_key="",
            api_secret="",
            symbol="ETH/USDT",
            timeframe="4h",
            limit=3,
        )
        assert len(df) >= 1
        assert df["close"].iloc[-1] > 0

    asyncio.run(_run())
