"""Market-data adapter helpers for trader execution."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import pandas as pd

from src.core.logger import logger
from src.exchange.data.ccxt_adapter import CcxtMarketDataAdapter
from src.exchange.config.venue import CcxtExchangeConfig

FetchRecentOHLCV = Callable[..., Awaitable[pd.DataFrame]]
Sleep = Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class ReadonlyMarketDataFetchPolicy:
    """Bounded retry policy for readonly runtime OHLCV requests."""

    request_timeout_seconds: float
    max_attempts: int
    retry_backoff_seconds: float

    def __post_init__(self) -> None:
        if self.request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be positive")
        if self.max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        if self.retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds must be non-negative")

    def backoff_seconds_after(self, failed_attempt: int) -> float:
        """Return exponential retry delay after a one-based failed attempt."""
        return self.retry_backoff_seconds * (2 ** (failed_attempt - 1))


class ReadonlyMarketDataFetchError(RuntimeError):
    """Readonly OHLCV fetch exhausted its bounded retry policy."""


async def fetch_recent_candles(
    symbol: str,
    bars_needed: int,
    timeframe: str,
    exchange_id: str,
    api_key: str,
    api_secret: str,
    exchange_config: CcxtExchangeConfig,
    policy: ReadonlyMarketDataFetchPolicy,
    *,
    fetch_recent_ohlcv_fn: FetchRecentOHLCV | None = None,
    sleep: Sleep | None = None,
) -> pd.DataFrame:
    """Fetch recent candles with bounded readonly retries and timeout."""
    fetch = fetch_recent_ohlcv_fn or _fetch_recent_ohlcv_once
    pause = sleep or asyncio.sleep

    for attempt in range(1, policy.max_attempts + 1):
        try:
            df = await asyncio.wait_for(
                fetch(
                    exchange_id=exchange_id,
                    api_key=api_key,
                    api_secret=api_secret,
                    exchange_config=exchange_config,
                    symbol=symbol,
                    timeframe=timeframe,
                    limit=bars_needed,
                ),
                timeout=policy.request_timeout_seconds,
            )
            df.attrs["symbol"] = symbol
            return df
        except Exception as exc:
            detail = _failure_detail(exc)
            if attempt >= policy.max_attempts:
                raise ReadonlyMarketDataFetchError(
                    f"Readonly OHLCV fetch failed for {symbol} after "
                    f"{policy.max_attempts} attempts: {detail}"
                ) from exc

            backoff_seconds = policy.backoff_seconds_after(attempt)
            logger.warning(
                f"Readonly OHLCV fetch retry for {symbol}: "
                f"attempt {attempt}/{policy.max_attempts} failed ({detail}); "
                f"backing off {backoff_seconds:.1f}s."
            )
            await pause(backoff_seconds)

    raise AssertionError("Readonly OHLCV retry loop exhausted without returning or raising")


async def _fetch_recent_ohlcv_once(
    *,
    exchange_id: str,
    api_key: str,
    api_secret: str,
    exchange_config: CcxtExchangeConfig,
    symbol: str,
    timeframe: str,
    limit: int,
) -> pd.DataFrame:
    async with CcxtMarketDataAdapter(
        exchange_id,
        api_key,
        api_secret,
        exchange_config,
    ) as adapter:
        return await adapter.fetch_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )


def _failure_detail(exc: Exception) -> str:
    if isinstance(exc, TimeoutError):
        return "request timed out"
    return f"{type(exc).__name__}: {exc}"
