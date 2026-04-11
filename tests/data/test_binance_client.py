import pytest
import ccxt.async_support as ccxt
from unittest.mock import AsyncMock, patch

try:
    from src.data.fetcher.binance_client import fetch_usd_m_universe, fetch_klines
except ImportError:
    pass  # Will naturally crash on first test per TDD

@pytest.mark.asyncio
async def test_fetch_usd_m_universe_success():
    """
    Tests that we fetch the active Universe cleanly, mapping CCXT data correctly.
    """
    mock_exchange = AsyncMock()
    # Mock return data simulating a mini universe
    mock_exchange.fetch_tickers.return_value = {
        "BTC/USDT:USDT": {"symbol": "BTC/USDT:USDT", "quoteVolume": 500000000},
        "ETH/USDT:USDT": {"symbol": "ETH/USDT:USDT", "quoteVolume": 250000000},
        "OBSCURE_DEAD_COIN/USDT:USDT": {"symbol": "OBSCURE/USDT:USDT", "quoteVolume": 500}
    }
    mock_exchange.has = {"fetchTickers": True}
    
    with patch("src.data.fetcher.binance_client._get_exchange", return_value=mock_exchange):
        universe = await fetch_usd_m_universe(min_volume=1000)
        
        # Should only return the two high-volume tickers
        assert len(universe) == 2
        assert "BTC/USDT" in universe  # Notice the clean up of the base symbol without :USDT
        assert "OBSCURE_DEAD_COIN/USDT" not in universe

@pytest.mark.asyncio
async def test_fetch_klines_network_failure():
    """
    Tests the exception fallback logic. If Binance sends a 502/Timeout,
    the fetcher must logically bubble up an empty array or raise a handled error
    without collapsing the active event loop.
    """
    mock_exchange = AsyncMock()
    mock_exchange.fetch_ohlcv.side_effect = ccxt.NetworkError("502 Bad Gateway")
    
    with patch("src.data.fetcher.binance_client._get_exchange", return_value=mock_exchange):
        with pytest.raises(RuntimeError, match="NetworkError"):
            await fetch_klines("BTC/USDT", timeframe="1d", limit=180)
