"""Verbose live OHLCV probe for a few explicit symbols.

Run explicitly with:
    .venv/bin/python -m pytest tests/exchange/data/test_live_selected_ohlcv_probe.py -m live -s
"""

from __future__ import annotations

import os

import pandas as pd
import pytest

from src.engine.trader.config import load_pipeline_config
from src.exchange.config.venue import load_ccxt_exchange_config
from src.exchange.data.ccxt_adapter import CcxtMarketDataAdapter

PIPELINE_CONFIG = "configs/pipelines/dev.yml"
DEFAULT_SYMBOLS = ("BTC/USDT:USDT", "ETH/USDT:USDT", "XRP/USDT:USDT")


@pytest.mark.live
@pytest.mark.asyncio
async def test_dev_config_fetches_selected_live_ohlcv_rows() -> None:
    """Print the candles fetched for BTC, ETH, and XRP from live CCXT."""
    print(
        "\nTEST: Live probe that loads the dev pipeline config, fetches selected "
        "BTC/ETH/XRP OHLCV rows, and prints the candles."
    )
    pipeline_cfg = load_pipeline_config(PIPELINE_CONFIG)
    exchange_cfg = load_ccxt_exchange_config(pipeline_cfg.venue.market_profile_config)
    symbols = _symbols_from_env("LIVE_OHLCV_SYMBOLS", DEFAULT_SYMBOLS)
    limit = int(os.environ.get("LIVE_OHLCV_LIMIT", "5"))

    _print_header("LIVE SELECTED OHLCV PROBE")
    _print_kv("pipeline config", PIPELINE_CONFIG)
    _print_kv("pipeline name", pipeline_cfg.name)
    _print_kv("exchange id", pipeline_cfg.venue.exchange_id)
    _print_kv("market profile config", pipeline_cfg.venue.market_profile_config)
    _print_kv("timeframe", pipeline_cfg.timeframe)
    _print_kv("limit per symbol", limit)
    _print_kv("symbols", ", ".join(symbols))

    print("\nAbout to run:")
    print(
        "  CcxtMarketDataAdapter.fetch_ohlcv("
        "symbol=<each symbol>, "
        f"timeframe={pipeline_cfg.timeframe!r}, "
        f"limit={limit})"
    )

    async with CcxtMarketDataAdapter(
        pipeline_cfg.venue.exchange_id,
        "",
        "",
        exchange_cfg,
    ) as adapter:
        frames = {
            symbol: await adapter.fetch_ohlcv(
                symbol,
                pipeline_cfg.timeframe,
                limit,
            )
            for symbol in symbols
        }

    for symbol, frame in frames.items():
        print(f"\n{symbol} returned {len(frame)} rows:")
        print(_display_ohlcv(frame).to_string(index=False))

    assert frames
    for symbol, frame in frames.items():
        assert not frame.empty, symbol
        assert {"timestamp", "open", "high", "low", "close", "volume"} <= set(
            frame.columns
        )
        assert frame["close"].iloc[-1] > 0


def _display_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    display = frame.copy()
    display.insert(
        0,
        "datetime_utc",
        pd.to_datetime(display["timestamp"], unit="ms", utc=True),
    )
    return display[
        ["datetime_utc", "open", "high", "low", "close", "volume"]
    ]


def _symbols_from_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.environ.get(name)
    if raw is None:
        return default
    symbols = tuple(part.strip() for part in raw.split(",") if part.strip())
    return symbols or default


def _print_header(title: str) -> None:
    print(f"\n=== {title} ===")


def _print_kv(label: str, value: object) -> None:
    print(f"{label:<26} {value}")
