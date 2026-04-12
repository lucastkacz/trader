"""
Exchange-Agnostic Live Fetcher
================================
Provides a single async interface for fetching live OHLCV candles
from any CCXT-supported exchange. Used by the Ghost Trader (Epoch 3+)
to decouple live price feeds from the historical data mining layer.

The exchange is selected via the GHOST_EXCHANGE setting in .env.
"""

import ccxt.async_support as ccxt
import pandas as pd

from src.core.logger import logger, LogContext
from src.core.config import settings


def _get_exchange() -> ccxt.Exchange:
    """
    Factory that returns the configured exchange instance.
    Supports: bybit, binance.
    """
    exchange_id = settings.ghost_exchange.lower()

    if exchange_id == "bybit":
        return ccxt.bybit({
            "enableRateLimit": True,
            "options": {"defaultType": "linear"},  # USDT perpetuals
            "apiKey": settings.bybit_api_key,
            "secret": settings.bybit_api_secret,
        })
    elif exchange_id == "binance":
        return ccxt.binance({
            "enableRateLimit": True,
            "options": {"defaultType": "future"},  # USD-M perpetuals
            "apiKey": settings.binance_api_key,
            "secret": settings.binance_api_secret,
        })
    else:
        raise ValueError(f"Unsupported ghost exchange: {exchange_id}")


async def fetch_live_klines(
    symbol: str,
    timeframe: str = "4h",
    limit: int = 200,
) -> pd.DataFrame:
    """
    Fetches recent OHLCV candles from the configured live exchange.

    Symbol format: 'BTC/USDT' (standard CCXT, no colon suffix needed).
    The function handles exchange-specific symbol resolution internally.
    """
    exchange = _get_exchange()
    exchange_id = settings.ghost_exchange.lower()

    # Resolve the CCXT market symbol with the correct settlement suffix
    if ":" not in symbol:
        quote = symbol.split("/")[-1]
        ccxt_symbol = f"{symbol}:{quote}"
    else:
        ccxt_symbol = symbol

    ctx = LogContext(pair=symbol)

    try:
        ohlcv = await exchange.fetch_ohlcv(ccxt_symbol, timeframe, limit=limit)

        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)

        logger.bind(**ctx.model_dump(exclude_none=True)).debug(
            f"[{exchange_id}] Fetched {len(df)} candles for {symbol}"
        )
        return df

    except ccxt.NetworkError as ne:
        logger.bind(**ctx.model_dump(exclude_none=True)).error(
            f"[{exchange_id}] Network error: {ne}"
        )
        raise RuntimeError(f"NetworkError on {exchange_id}: {ne}")
    except Exception as e:
        logger.bind(**ctx.model_dump(exclude_none=True)).critical(
            f"[{exchange_id}] FATAL: {e}"
        )
        raise
    finally:
        await exchange.close()
