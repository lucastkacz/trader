"""
Exchange Client
================
Unified CCXT adapter for fetching market data from any supported exchange.
The exchange ID is passed as a raw CCXT identifier (e.g., "bybit", "binanceusdm")
directly from the pipeline YAML — zero internal mapping or inference.

ARCHITECTURAL RULE: No default values for config-driven parameters.
"""

import ccxt.async_support as ccxt
import pandas as pd
from typing import List, Optional

from src.core.logger import logger, LogContext


def create_exchange(exchange_id: str, api_key: str, api_secret: str) -> ccxt.Exchange:
    """
    Factory that returns a rate-limited async CCXT exchange instance.

    Parameters
    ----------
    exchange_id : str — raw CCXT exchange ID (e.g., "bybit", "binanceusdm", "kucoin")
    api_key : str — API key credential
    api_secret : str — API secret credential

    Returns
    -------
    ccxt.Exchange instance ready for async operations.
    """
    exchange_class = getattr(ccxt, exchange_id, None)
    if exchange_class is None:
        raise ValueError(f"Unknown CCXT exchange ID: '{exchange_id}'. Check https://docs.ccxt.com/")

    return exchange_class({
        "enableRateLimit": True,
        "apiKey": api_key,
        "secret": api_secret,
    })


async def fetch_universe(exchange: ccxt.Exchange, min_volume: float) -> List[str]:
    """
    Fetches all active USDT perpetual tickers and filters by 24h quote volume.
    Returns standardized pair symbols (e.g., "BTC/USDT") with the CCXT
    settlement suffix stripped.

    Parameters
    ----------
    exchange : ccxt.Exchange — an initialized exchange instance
    min_volume : float — minimum 24h quote volume threshold (no default!)
    """
    try:
        tickers = await exchange.fetch_tickers()
        valid_pairs = []

        for symbol, data in tickers.items():
            if not symbol.endswith(":USDT"):
                continue

            quote_volume = float(data.get("quoteVolume", 0) or 0)
            if quote_volume > min_volume:
                clean_symbol = symbol.split(":")[0]
                valid_pairs.append(clean_symbol)

        ctx = LogContext(trade_id="UNIVERSE_SCAN")
        logger.bind(**ctx.model_dump(exclude_none=True)).info(
            f"Filtered Universe: {len(valid_pairs)} assets above ${min_volume:,.0f} volume "
            f"on {exchange.id}."
        )
        return valid_pairs

    except Exception as e:
        logger.error(f"Failed pulling universe from {exchange.id}: {e}")
        raise RuntimeError(f"Universe Error ({exchange.id}): {e}")


async def fetch_klines(
    exchange: ccxt.Exchange,
    symbol: str,
    timeframe: str,
    limit: int,
    since: Optional[int] = None,
    end_ts: Optional[int] = None,
) -> pd.DataFrame:
    """
    Downloads OHLCV candles from any CCXT-supported exchange.
    Applies the Mathematical Freeze-Frame (end_ts) to align datasets.

    Parameters
    ----------
    exchange : ccxt.Exchange — an initialized exchange instance
    symbol : str — standardized pair (e.g., "BTC/USDT")
    timeframe : str — candle interval (e.g., "1m", "4h")
    limit : int — max candles per request
    since : int, optional — start timestamp in milliseconds
    end_ts : int, optional — freeze-frame cutoff timestamp in milliseconds
    """
    # CCXT requires the settlement suffix for perpetual queries
    if ":" not in symbol:
        quote_currency = symbol.split("/")[-1]
        ccxt_symbol = f"{symbol}:{quote_currency}"
    else:
        ccxt_symbol = symbol

    ctx = LogContext(pair=symbol)
    logger.bind(**ctx.model_dump(exclude_none=True)).debug(
        f"[{exchange.id}] Fetching {limit} candles for {timeframe}"
    )

    try:
        ohlcv = await exchange.fetch_ohlcv(
            ccxt_symbol, timeframe, limit=limit, since=since
        )

        df = pd.DataFrame(
            ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)

        # ─── FREEZE-FRAME LOGIC ───
        if end_ts is not None:
            df = df[df["timestamp"] <= end_ts]

        return df

    except ccxt.NetworkError as ne:
        logger.bind(**ctx.model_dump(exclude_none=True)).error(
            f"[{exchange.id}] Network error: {ne}"
        )
        raise RuntimeError(f"NetworkError ({exchange.id}): {ne}")
    except Exception as e:
        logger.bind(**ctx.model_dump(exclude_none=True)).critical(
            f"[{exchange.id}] FATAL: {e}"
        )
        raise
