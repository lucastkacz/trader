import pytest

from src.engine.trader.config import load_universe_config
from src.exchange.data.market_data import MarketTicker
from src.universe.filters.market_tickers import select_symbols_by_quote_volume


def test_select_symbols_by_quote_volume_uses_configured_floor():
    universe_cfg = load_universe_config("configs/universe/dev.yml")
    min_volume = universe_cfg.filters.min_volume_liquidity
    tickers = [
        MarketTicker(symbol="BTC/USDT:USDT", quote_volume=min_volume * 2),
        MarketTicker(symbol="ETH/USDT:USDT", quote_volume=min_volume + 1),
        MarketTicker(symbol="THIN/USDT:USDT", quote_volume=min_volume),
    ]

    symbols = select_symbols_by_quote_volume(
        tickers,
        min_quote_volume=min_volume,
    )

    assert symbols == ["BTC/USDT:USDT", "ETH/USDT:USDT"]


def test_select_symbols_by_quote_volume_rejects_negative_floor():
    with pytest.raises(ValueError, match="min_quote_volume must be non-negative"):
        select_symbols_by_quote_volume([], min_quote_volume=-1)
