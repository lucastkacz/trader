"""
Tests for Exchange Connectivity (Live Client).
These tests hit real exchange APIs and require network access.
Mark with @pytest.mark.live so they can be skipped in CI.
"""

import pytest
import asyncio

from src.data.fetcher.live_client import fetch_live_klines
from src.core.config import settings


@pytest.mark.live
def test_bybit_connectivity_4h():
    """Verify we can fetch 4H candles from the configured exchange."""
    async def _run():
        df = await fetch_live_klines("BTC/USDT", timeframe="4h", limit=5)
        assert len(df) == 5
        assert "close" in df.columns
        assert df["close"].iloc[-1] > 0
        return df

    df = asyncio.get_event_loop().run_until_complete(_run())
    print(f"\n  Exchange: {settings.ghost_exchange}")
    print(f"  Latest BTC/USDT 4H close: {df['close'].iloc[-1]}")


@pytest.mark.live
def test_bybit_connectivity_1m():
    """Verify 1m candles work (needed for turbo mode)."""
    async def _run():
        df = await fetch_live_klines("BTC/USDT", timeframe="1m", limit=3)
        assert len(df) == 3
        assert df["close"].iloc[-1] > 0
        return df

    asyncio.get_event_loop().run_until_complete(_run())


@pytest.mark.live
def test_tier1_pair_available():
    """Verify a Tier 1 pair (AVNT/USDT) exists on the configured exchange."""
    async def _run():
        df = await fetch_live_klines("AVNT/USDT", timeframe="4h", limit=3)
        assert len(df) >= 1
        assert df["close"].iloc[-1] > 0

    asyncio.get_event_loop().run_until_complete(_run())
