"""Unified CCXT adapter for fetching market data from configured markets."""

from dataclasses import dataclass
from typing import Optional

import ccxt.async_support as ccxt
import pandas as pd

from src.core.logger import LogContext, logger
from src.exchange.config.venue import CcxtExchangeConfig
from src.data.ohlcv import normalize_ohlcv_frame


@dataclass(frozen=True)
class MarketTicker:
    """Ticker facts for one configured exchange market."""

    symbol: str
    quote_volume: float
    market_type: str | None = None
    market_sub_type: str | None = None
    settle: str | None = None


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


async def fetch_market_tickers(
    exchange: ccxt.Exchange,
    exchange_config: CcxtExchangeConfig,
) -> list[MarketTicker]:
    """
    Fetch ticker facts for markets matching the configured contract profile.

    Parameters
    ----------
    exchange : ccxt.Exchange — an initialized exchange instance
    exchange_config : CcxtExchangeConfig — market contract profile from YAML
    """
    try:
        markets = await exchange.load_markets()
        tickers = await exchange.fetch_tickers()
        market_tickers = []

        for symbol, data in tickers.items():
            market = markets.get(symbol)
            if market is None or not exchange_config.market_contract.matches_market(market):
                continue

            market_tickers.append(
                MarketTicker(
                    symbol=symbol,
                    quote_volume=float(data.get("quoteVolume", 0) or 0),
                    market_type=_str_or_none(market.get("type")),
                    market_sub_type=_market_sub_type(market),
                    settle=_str_or_none(market.get("settle")),
                )
            )

        ctx = LogContext(trade_id="UNIVERSE_SCAN")
        logger.bind(**ctx.model_dump(exclude_none=True)).info(
            f"Fetched {len(market_tickers)} configured-market tickers "
            f"from {exchange.id} [{exchange_config.market_contract.name}]."
        )
        return market_tickers

    except Exception as e:
        logger.error(f"Failed pulling market tickers from {exchange.id}: {e}")
        raise RuntimeError(f"Market Ticker Error ({exchange.id}): {e}")


def _market_sub_type(market: dict) -> str | None:
    if market.get("linear") is True:
        return "linear"
    if market.get("inverse") is True:
        return "inverse"
    return _str_or_none(market.get("subType"))


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


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
    end_ts : int, optional - inclusive freeze-frame candle-open cutoff in milliseconds.
        Live callers should pass the last fully closed candle open.
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


async def fetch_funding_rate_history(
    exchange: ccxt.Exchange,
    symbol: str,
    since: Optional[int] = None,
    limit: Optional[int] = None,
) -> pd.DataFrame:
    """
    Downloads historical funding rates from any CCXT-supported exchange.

    Parameters
    ----------
    exchange : ccxt.Exchange - an initialized exchange instance
    symbol : str - native CCXT market symbol (e.g., "BTC/USDT:USDT")
    since : int, optional - start timestamp in milliseconds
    limit : int, optional - max historical records to fetch
    """
    ctx = LogContext(pair=symbol)
    logger.bind(**ctx.model_dump(exclude_none=True)).debug(
        f"[{exchange.id}] Fetching funding rate history for {symbol}"
    )

    try:
        # Check if the exchange supports fetchFundingRateHistory
        if not exchange.has.get("fetchFundingRateHistory", False):
            raise NotImplementedError(
                f"Exchange {exchange.id} does not support fetching funding rate history."
            )

        raw = await exchange.fetch_funding_rate_history(
            symbol, since=since, limit=limit
        )

        return _normalize_funding_rate_history(raw, since=since)

    except ccxt.NetworkError as ne:
        logger.bind(**ctx.model_dump(exclude_none=True)).error(
            f"[{exchange.id}] Network error while fetching funding: {ne}"
        )
        raise RuntimeError(f"NetworkError ({exchange.id}): {ne}")
    except Exception as e:
        logger.bind(**ctx.model_dump(exclude_none=True)).critical(
            f"[{exchange.id}] FATAL while fetching funding: {e}"
        )
        raise


def _normalize_funding_rate_history(
    raw: list[dict],
    *,
    since: Optional[int],
) -> pd.DataFrame:
    """Return canonical funding-rate rows from raw CCXT payloads."""
    if not raw:
        return _empty_funding_rate_frame()

    frame = pd.DataFrame(
        [
            {
                "timestamp": item.get("timestamp"),
                "funding_rate": item.get("fundingRate"),
            }
            for item in raw
        ],
        columns=["timestamp", "funding_rate"],
    )
    frame["timestamp"] = pd.to_numeric(frame["timestamp"], errors="coerce")
    frame["funding_rate"] = pd.to_numeric(frame["funding_rate"], errors="coerce")
    frame = frame.dropna(subset=["timestamp", "funding_rate"])
    if since is not None:
        frame = frame[frame["timestamp"] >= since]
    if frame.empty:
        return _empty_funding_rate_frame()

    frame = frame.astype({"timestamp": "int64", "funding_rate": "float64"})
    frame = frame.drop_duplicates(subset=["timestamp"], keep="last")
    return frame.sort_values("timestamp").reset_index(drop=True)


def _empty_funding_rate_frame() -> pd.DataFrame:
    frame = pd.DataFrame(columns=["timestamp", "funding_rate"])
    return frame.astype({"timestamp": "int64", "funding_rate": "float64"})
