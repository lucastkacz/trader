"""Unified CCXT adapter for fetching market data from configured markets."""

from typing import Optional

import ccxt.async_support as ccxt
import pandas as pd

from src.core.logger import LogContext, logger
from src.exchange.config.venue import CcxtExchangeConfig
from src.data.ohlcv import normalize_ohlcv_frame


def create_configured_ccxt_exchange(
    exchange_id: str,
    api_key: str,
    api_secret: str,
    exchange_config: CcxtExchangeConfig,
) -> ccxt.Exchange:
    """
    Factory for a rate-limited async CCXT exchange using typed market config.

    Parameters
    ----------
    exchange_id : str — raw CCXT exchange ID (e.g., "bybit", "binanceusdm", "kucoin")
    api_key : str — API key credential
    api_secret : str — API secret credential
    exchange_config : CcxtExchangeConfig — market contract and CCXT options

    Returns
    -------
    ccxt.Exchange instance configured from operator-supplied YAML.
    """
    exchange_class = getattr(ccxt, exchange_id, None)
    if exchange_class is None:
        raise ValueError(f"Unknown CCXT exchange ID: '{exchange_id}'. Check https://docs.ccxt.com/")

    return exchange_class(
        exchange_config.to_ccxt_kwargs(api_key=api_key, api_secret=api_secret)
    )


async def fetch_universe(
    exchange: ccxt.Exchange,
    min_volume: float,
    exchange_config: CcxtExchangeConfig,
) -> list[str]:
    """
    Fetch configured-market tickers and filter by 24h quote volume.
    Returns native CCXT market symbols unchanged.

    Parameters
    ----------
    exchange : ccxt.Exchange — an initialized exchange instance
    min_volume : float — minimum 24h quote volume threshold (no default!)
    exchange_config : CcxtExchangeConfig — market contract profile from YAML
    """
    try:
        markets = await exchange.load_markets()
        tickers = await exchange.fetch_tickers()
        valid_pairs = []

        for symbol, data in tickers.items():
            market = markets.get(symbol)
            if market is None or not exchange_config.market_contract.matches_market(market):
                continue

            quote_volume = float(data.get("quoteVolume", 0) or 0)
            if quote_volume > min_volume:
                valid_pairs.append(symbol)

        ctx = LogContext(trade_id="UNIVERSE_SCAN")
        logger.bind(**ctx.model_dump(exclude_none=True)).info(
            f"Filtered Universe: {len(valid_pairs)} assets above ${min_volume:,.0f} volume "
            f"on {exchange.id} [{exchange_config.market_contract.name}]."
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
    exchange : ccxt.Exchange - an initialized exchange instance
    symbol : str - native CCXT market symbol (e.g., "BTC/USDT:USDT")
    timeframe : str - candle interval (e.g., "1m", "4h")
    limit : int - max candles per request
    since : int, optional - start timestamp in milliseconds
    end_ts : int, optional - freeze-frame cutoff timestamp in milliseconds
    """
    ctx = LogContext(pair=symbol)
    logger.bind(**ctx.model_dump(exclude_none=True)).debug(
        f"[{exchange.id}] Fetching {limit} candles for {timeframe}"
    )

    try:
        ohlcv = await exchange.fetch_ohlcv(
            symbol, timeframe, limit=limit, since=since
        )

        df = pd.DataFrame(
            ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df = normalize_ohlcv_frame(df)

        if since is not None:
            df = df[df["timestamp"] >= since]
        if end_ts is not None:
            df = df[df["timestamp"] <= end_ts]

        return df.reset_index(drop=True)

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
