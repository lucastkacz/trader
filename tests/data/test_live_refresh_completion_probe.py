"""Live probe for completing local OHLCV data after new candles close.

Run explicitly with:
    .venv/bin/python -m pytest tests/data/test_live_refresh_completion_probe.py -m live -s

This probe waits 180 seconds by default. Override for manual experiments:
    OHLCV_LIVE_COMPLETION_WAIT_SECONDS=60 .venv/bin/python -m pytest \
        tests/data/test_live_refresh_completion_probe.py -m live -s
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from src.data.storage.local_parquet import LocalOHLCVParquetStore
from src.data.sync import (
    OHLCVFetchPolicy,
    OHLCVMarketMetadata,
    OHLCVRefreshRequest,
    OHLCVRefreshService,
)
from src.engine.trader.config import load_pipeline_config
from src.exchange.config.venue import (
    load_ccxt_exchange_config,
    load_exchange_venue_config,
)
from src.exchange.data.ccxt_adapter import CcxtMarketDataAdapter
from src.utils.timeframe_math import get_timeframe_minutes

PIPELINE_CONFIG = "configs/pipelines/dev.yml"
VENUE_CONFIG = "configs/exchange/venues/dev.yml"
MARKET_PROFILE_CONFIG = "configs/exchange/market_profiles/linear_usdt_swap.yml"
DEFAULT_SYMBOL = "BTC/USDT:USDT"
DEFAULT_TIMEFRAME = "1m"
DEFAULT_MISSING_LOOKBACK_BARS = 5


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_refresh_completes_bitcoin_after_waiting_for_new_1m_candles() -> None:
    print(
        "\nTEST: Live completion probe. It downloads a small BTC 1m OHLCV window, "
        "waits for new candles to close, refreshes the same local Parquet file, "
        "and confirms only the missing tail was appended."
    )
    pipeline_cfg = load_pipeline_config(PIPELINE_CONFIG)
    venue_cfg = load_exchange_venue_config(VENUE_CONFIG)
    exchange_cfg = load_ccxt_exchange_config(MARKET_PROFILE_CONFIG)
    exchange_id = venue_cfg.exchange_id
    symbol = os.environ.get("OHLCV_LIVE_COMPLETION_SYMBOL", DEFAULT_SYMBOL)
    timeframe = os.environ.get("OHLCV_LIVE_COMPLETION_TIMEFRAME", DEFAULT_TIMEFRAME)
    wait_seconds = int(os.environ.get("OHLCV_LIVE_COMPLETION_WAIT_SECONDS", "180"))
    output_dir = _output_dir()
    store = LocalOHLCVParquetStore(str(output_dir))

    _print_header("LIVE REFRESH COMPLETION PROBE")
    _print_kv("pipeline config", PIPELINE_CONFIG)
    _print_kv("venue config", VENUE_CONFIG)
    _print_kv("market profile config", MARKET_PROFILE_CONFIG)
    _print_kv("pipeline name", pipeline_cfg.name)
    _print_kv("exchange id", exchange_id)
    _print_kv("symbol", symbol)
    _print_kv("timeframe", timeframe)
    _print_kv("wait seconds", wait_seconds)
    _print_kv("missing lookback bars", DEFAULT_MISSING_LOOKBACK_BARS)
    _print_kv("output dir", output_dir)

    policy = OHLCVFetchPolicy(
        fetch_limit=DEFAULT_MISSING_LOOKBACK_BARS,
        max_retries=1,
        retry_backoff_seconds=1,
        request_pause_seconds=0.2,
    )

    async with CcxtMarketDataAdapter(exchange_id, "", "", exchange_cfg) as adapter:
        service = OHLCVRefreshService(
            market_data=adapter,
            store=store,
            policy=policy,
        )

        first_end_ts = _closed_candle_end_ms(timeframe)
        print("\nFirst refresh:")
        _print_kv("target closed candle", _format_ts(first_end_ts))
        first_result = await service.run(
            OHLCVRefreshRequest(
                exchange_id=exchange_id,
                timeframe=timeframe,
                symbols=[symbol],
                end_ts=first_end_ts,
                overlap_bars=0,
                missing_lookback_bars=DEFAULT_MISSING_LOOKBACK_BARS,
                market=OHLCVMarketMetadata(
                    market_type=exchange_cfg.market_contract.default_type,
                    market_sub_type=exchange_cfg.market_contract.default_sub_type,
                    settle=exchange_cfg.market_contract.default_settle,
                ),
            )
        )
        first_frame = store.load_ohlcv(symbol, timeframe, exchange_id)
        first_metadata = store.read_ohlcv_metadata(symbol, timeframe, exchange_id)
        assert first_metadata is not None
        _print_result(first_result.results[0])
        _print_kv("saved rows after first refresh", len(first_frame))
        _print_kv("local latest after first refresh", _format_ts(first_metadata.last_ts))
        print(_display_tail(first_frame).to_string(index=False))

        print(f"\nWaiting {wait_seconds} seconds for new {timeframe} candles to close...")
        await asyncio.sleep(wait_seconds)

        second_end_ts = _closed_candle_end_ms(timeframe)
        print("\nSecond refresh:")
        _print_kv("target closed candle", _format_ts(second_end_ts))
        assert first_metadata.last_ts is not None
        assert second_end_ts > first_metadata.last_ts, (
            "The wait did not produce a newer closed candle. Increase "
            "OHLCV_LIVE_COMPLETION_WAIT_SECONDS."
        )

        second_result = await service.run(
            OHLCVRefreshRequest(
                exchange_id=exchange_id,
                timeframe=timeframe,
                symbols=[symbol],
                end_ts=second_end_ts,
                overlap_bars=0,
                missing_lookback_bars=DEFAULT_MISSING_LOOKBACK_BARS,
                market=OHLCVMarketMetadata(
                    market_type=exchange_cfg.market_contract.default_type,
                    market_sub_type=exchange_cfg.market_contract.default_sub_type,
                    settle=exchange_cfg.market_contract.default_settle,
                ),
            )
        )

    second_frame = store.load_ohlcv(symbol, timeframe, exchange_id)
    second_metadata = store.read_ohlcv_metadata(symbol, timeframe, exchange_id)
    assert second_metadata is not None
    assert second_metadata.last_ts is not None
    _print_result(second_result.results[0])
    _print_kv("saved rows after second refresh", len(second_frame))
    _print_kv("local latest after second refresh", _format_ts(second_metadata.last_ts))

    new_rows = second_frame[second_frame["timestamp"] > first_metadata.last_ts]
    print("\nRows appended by the second refresh:")
    print(_display_tail(new_rows, rows=10).to_string(index=False))

    parquet_path = store.path_for_ohlcv(symbol, timeframe, exchange_id)
    _print_kv("parquet path", parquet_path)

    assert first_result.success_count == 1
    assert second_result.success_count == 1
    assert parquet_path.exists()
    assert len(second_frame) > len(first_frame)
    assert second_metadata.last_ts > first_metadata.last_ts
    assert not new_rows.empty


def _output_dir() -> Path:
    configured = os.environ.get("OHLCV_LIVE_COMPLETION_DIR")
    if configured is not None:
        return Path(configured)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("data/test/live_refresh_completion_probe") / run_id


def _closed_candle_end_ms(timeframe: str) -> int:
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    bar_ms = int(get_timeframe_minutes(timeframe) * 60_000)
    return (now_ms // bar_ms) * bar_ms - bar_ms


def _display_tail(frame: pd.DataFrame, *, rows: int = 5) -> pd.DataFrame:
    display = frame.tail(rows).copy()
    if display.empty:
        return display
    display.insert(
        0,
        "datetime_utc",
        pd.to_datetime(display["timestamp"], unit="ms", utc=True),
    )
    return display[["datetime_utc", "open", "high", "low", "close", "volume"]]


def _format_ts(ms: int | None) -> str:
    if ms is None:
        return "-"
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def _print_header(title: str) -> None:
    print(f"\n=== {title} ===")


def _print_kv(label: str, value: object) -> None:
    print(f"{label:<30} {value}")


def _print_result(result: object) -> None:
    _print_kv("status", getattr(result, "status"))
    _print_kv("fetched bars", getattr(result, "fetched_bars"))
    _print_kv("saved bars", getattr(result, "saved_bars"))
    _print_kv("first ts", _format_ts(getattr(result, "first_ts")))
    _print_kv("last ts", _format_ts(getattr(result, "last_ts")))
