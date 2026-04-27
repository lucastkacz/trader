"""Market-data adapter helpers for trader execution."""

import pandas as pd

from src.data.fetcher.live_client import fetch_live_klines


async def fetch_recent_candles(
    symbol: str,
    bars_needed: int,
    timeframe: str,
    exchange_id: str,
    api_key: str,
    api_secret: str,
) -> pd.DataFrame:
    """Fetch recent candles and annotate them with their source symbol."""
    df = await fetch_live_klines(
        exchange_id=exchange_id,
        api_key=api_key,
        api_secret=api_secret,
        symbol=symbol,
        timeframe=timeframe,
        limit=bars_needed,
    )
    df.attrs["symbol"] = symbol
    return df
