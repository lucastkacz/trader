"""Filters for exchange market ticker facts."""

from collections.abc import Iterable

from src.exchange.data.market_data import MarketTicker


def select_symbols_by_quote_volume(
    tickers: Iterable[MarketTicker],
    *,
    min_quote_volume: float,
) -> list[str]:
    """Return symbols whose 24h quote volume is above the configured floor."""
    if min_quote_volume < 0:
        raise ValueError("min_quote_volume must be non-negative")
    return [
        ticker.symbol
        for ticker in tickers
        if ticker.quote_volume > min_quote_volume
    ]
