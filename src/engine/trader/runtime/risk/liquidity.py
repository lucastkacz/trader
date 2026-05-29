"""Liquidity evidence builders for runtime pre-trade checks."""

import math
from typing import Any

from src.engine.trader.runtime.risk.models import PreTradeLiquiditySnapshot


def liquidity_snapshot_from_candles(
    df_a: Any,
    df_b: Any,
    *,
    lookback_bars: int,
) -> PreTradeLiquiditySnapshot:
    """Build average quote-volume evidence from recent OHLCV candles."""
    quote_volume_a = _average_quote_volume(df_a, lookback_bars)
    quote_volume_b = _average_quote_volume(df_b, lookback_bars)
    return PreTradeLiquiditySnapshot(
        quote_volume_a=quote_volume_a,
        quote_volume_b=quote_volume_b,
        observation_bars=min(_row_count(df_a), _row_count(df_b), lookback_bars),
    )


def _average_quote_volume(df: Any, lookback_bars: int) -> float | None:
    if not {"close", "volume"}.issubset(set(df.columns)):
        return None
    recent = df.tail(lookback_bars)
    if len(recent) < lookback_bars:
        return None
    quote_volume = recent["close"].astype(float) * recent["volume"].astype(float)
    finite_quote_volume = [
        float(value)
        for value in quote_volume
        if math.isfinite(float(value)) and float(value) > 0
    ]
    if len(finite_quote_volume) < lookback_bars:
        return None
    return sum(finite_quote_volume) / len(finite_quote_volume)


def _row_count(df: Any) -> int:
    try:
        return len(df)
    except TypeError:
        return 0
