"""
Live Data Client
==================
Async interface for fetching live OHLCV candles from any CCXT-supported exchange.
Used by the Trader Engine to get real-time price feeds.

Delegates all exchange logic to the unified exchange_client module.

ARCHITECTURAL RULE: No default values for config-driven parameters.
"""

import pandas as pd

from src.data.fetcher.exchange_client import create_exchange, fetch_klines


async def fetch_live_klines(
    exchange_id: str,
    api_key: str,
    api_secret: str,
    symbol: str,
    timeframe: str,
    limit: int,
) -> pd.DataFrame:
    """
    Fetches recent OHLCV candles from the configured live exchange.

    Parameters
    ----------
    exchange_id : str — raw CCXT exchange ID (e.g., "bybit", "binanceusdm")
    api_key : str — API key credential
    api_secret : str — API secret credential
    symbol : str — standardized pair (e.g., "BTC/USDT")
    timeframe : str — candle interval (e.g., "1m", "4h")
    limit : int — number of candles to fetch

    Returns
    -------
    pd.DataFrame with columns: timestamp, open, high, low, close, volume
    """
    exchange = create_exchange(exchange_id, api_key, api_secret)
    try:
        return await fetch_klines(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )
    finally:
        await exchange.close()
