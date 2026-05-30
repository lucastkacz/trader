import asyncio

import pandas as pd
import pytest

from src.engine.trader.execution.market_data import (
    ReadonlyMarketDataFetchError,
    ReadonlyMarketDataFetchPolicy,
    fetch_recent_candles,
)


def _policy(
    *,
    request_timeout_seconds: float = 1.0,
    max_attempts: int = 3,
    retry_backoff_seconds: float = 2.0,
) -> ReadonlyMarketDataFetchPolicy:
    return ReadonlyMarketDataFetchPolicy(
        request_timeout_seconds=request_timeout_seconds,
        max_attempts=max_attempts,
        retry_backoff_seconds=retry_backoff_seconds,
    )


@pytest.mark.asyncio
async def test_fetch_recent_candles_retries_with_bounded_backoff_before_success():
    attempts = []
    delays = []

    async def fake_fetch_live_klines(**kwargs):
        attempts.append(kwargs)
        if len(attempts) < 3:
            raise RuntimeError("readonly provider unavailable")
        return pd.DataFrame({"close": [100.0]})

    async def fake_sleep(delay):
        delays.append(delay)

    candles = await fetch_recent_candles(
        symbol="BTC/USDT",
        bars_needed=20,
        timeframe="1m",
        exchange_id="bybit",
        api_key="",
        api_secret="",
        policy=_policy(),
        fetch_live_klines_fn=fake_fetch_live_klines,
        sleep=fake_sleep,
    )

    assert len(attempts) == 3
    assert delays == [2.0, 4.0]
    assert candles.attrs["symbol"] == "BTC/USDT"


@pytest.mark.asyncio
async def test_fetch_recent_candles_raises_auditable_error_after_bounded_attempts():
    attempts = 0
    delays = []

    async def failing_fetch(**kwargs):
        nonlocal attempts
        attempts += 1
        raise RuntimeError("readonly provider unavailable")

    async def fake_sleep(delay):
        delays.append(delay)

    with pytest.raises(
        ReadonlyMarketDataFetchError,
        match="BTC/USDT.*after 2 attempts.*readonly provider unavailable",
    ):
        await fetch_recent_candles(
            symbol="BTC/USDT",
            bars_needed=20,
            timeframe="1m",
            exchange_id="bybit",
            api_key="",
            api_secret="",
            policy=_policy(max_attempts=2),
            fetch_live_klines_fn=failing_fetch,
            sleep=fake_sleep,
        )

    assert attempts == 2
    assert delays == [2.0]


@pytest.mark.asyncio
async def test_fetch_recent_candles_times_out_a_stalled_readonly_request():
    async def stalled_fetch(**kwargs):
        await asyncio.Event().wait()

    with pytest.raises(
        ReadonlyMarketDataFetchError,
        match="BTC/USDT.*after 1 attempts.*timed out",
    ):
        await fetch_recent_candles(
            symbol="BTC/USDT",
            bars_needed=20,
            timeframe="1m",
            exchange_id="bybit",
            api_key="",
            api_secret="",
            policy=_policy(request_timeout_seconds=0.001, max_attempts=1),
            fetch_live_klines_fn=stalled_fetch,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("request_timeout_seconds", 0.0),
        ("max_attempts", 0),
        ("retry_backoff_seconds", -1.0),
    ],
)
def test_readonly_market_data_fetch_policy_rejects_invalid_values(field, value):
    values = {
        "request_timeout_seconds": 1.0,
        "max_attempts": 3,
        "retry_backoff_seconds": 2.0,
    }
    values[field] = value

    with pytest.raises(ValueError, match=field):
        ReadonlyMarketDataFetchPolicy(**values)
