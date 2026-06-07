"""Verbose live backfill probe that writes a small Parquet sample.

Run explicitly with:
    .venv/bin/python -m pytest tests/data/test_live_backfill_probe.py -m live -s

Output defaults to:
    data/test/live_backfill_probe/bybit/1m/*.parquet
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.data.storage.local_parquet import LocalOHLCVParquetStore
from src.data.sync import (
    OHLCVBackfillRequest,
    OHLCVBackfillService,
    OHLCVFetchPolicy,
    OHLCVMarketMetadata,
)
from src.data.sync.config import load_ohlcv_backfill_config
from src.engine.trader.config import load_pipeline_config, load_universe_config
from src.exchange.config.venue import load_ccxt_exchange_config
from src.exchange.data.ccxt_adapter import CcxtMarketDataAdapter
from src.utils.timeframe_math import get_timeframe_minutes

PIPELINE_CONFIG = "configs/pipelines/dev.yml"
UNIVERSE_CONFIG = "configs/universe/alpha_v1.yml"
DEFAULT_SYMBOLS = ("BTC/USDT:USDT", "ETH/USDT:USDT", "XRP/USDT:USDT")


@pytest.mark.live
@pytest.mark.asyncio
async def test_dev_config_runs_small_live_backfill_and_writes_parquet() -> None:
    """Print the backfill request, result summary, output paths, and metadata."""
    print(
        "\nTEST: Live probe that loads the dev pipeline config, runs a small OHLCV "
        "backfill, writes Parquet, and prints result metadata."
    )
    pipeline_cfg = load_pipeline_config(PIPELINE_CONFIG)
    universe_cfg = load_universe_config(UNIVERSE_CONFIG)
    exchange_cfg = load_ccxt_exchange_config(pipeline_cfg.venue.market_profile_config)
    configured_policy = load_ohlcv_backfill_config(
        pipeline_cfg.data.backfill_policy_config
    ).to_fetch_policy()

    symbols = _symbols_from_env("OHLCV_LIVE_BACKFILL_SYMBOLS", DEFAULT_SYMBOLS)
    output_dir = Path(
        os.environ.get("OHLCV_LIVE_BACKFILL_DIR", "data/test/live_backfill_probe")
    )
    requested_bars = max(2, int(os.environ.get("OHLCV_LIVE_BACKFILL_BARS", "5")))
    bar_ms = int(get_timeframe_minutes(pipeline_cfg.timeframe) * 60_000)
    end_ts = _closed_candle_end_ms(pipeline_cfg.timeframe)
    start_ts = end_ts - (requested_bars - 1) * bar_ms
    policy = OHLCVFetchPolicy(
        fetch_limit=min(configured_policy.fetch_limit, requested_bars),
        max_retries=configured_policy.max_retries,
        retry_backoff_seconds=configured_policy.retry_backoff_seconds,
        request_pause_seconds=configured_policy.request_pause_seconds,
    )

    _print_header("LIVE BACKFILL PROBE")
    _print_kv("pipeline config", PIPELINE_CONFIG)
    _print_kv("pipeline name", pipeline_cfg.name)
    _print_kv("exchange id", pipeline_cfg.venue.exchange_id)
    _print_kv("market profile config", pipeline_cfg.venue.market_profile_config)
    _print_kv("backfill policy config", pipeline_cfg.data.backfill_policy_config)
    _print_kv("universe config", UNIVERSE_CONFIG)
    _print_kv("universe volume floor", f"${universe_cfg.filters.min_volume_liquidity:,.0f}")
    _print_kv("timeframe", pipeline_cfg.timeframe)
    _print_kv("symbols", ", ".join(symbols))
    _print_kv("requested bars", requested_bars)
    _print_kv("fetch limit used", policy.fetch_limit)
    _print_kv("output dir", output_dir)
    _print_kv("window start", _format_ts(start_ts))
    _print_kv("window end", _format_ts(end_ts))

    print("\nAbout to run:")
    print("  OHLCVBackfillService.run(OHLCVBackfillRequest(..., symbols=<above>))")

    store = LocalOHLCVParquetStore(str(output_dir))
    request = OHLCVBackfillRequest(
        exchange_id=pipeline_cfg.venue.exchange_id,
        timeframe=pipeline_cfg.timeframe,
        start_ts=start_ts,
        end_ts=end_ts,
        min_volume=universe_cfg.filters.min_volume_liquidity,
        symbols=symbols,
        market=OHLCVMarketMetadata(
            market_type=exchange_cfg.market_contract.default_type,
            market_sub_type=exchange_cfg.market_contract.default_sub_type,
            settle=exchange_cfg.market_contract.default_settle,
        ),
    )

    async with CcxtMarketDataAdapter(
        pipeline_cfg.venue.exchange_id,
        "",
        "",
        exchange_cfg,
    ) as adapter:
        service = OHLCVBackfillService(
            market_data=adapter,
            store=store,
            policy=policy,
        )
        result = await service.run(request)

    print("\nBackfill result:")
    _print_kv("symbol count", result.symbol_count)
    _print_kv("success count", result.success_count)
    _print_kv("failure count", result.failure_count)
    print(
        "symbol         status             fetched saved first                 last"
    )
    for item in result.results:
        print(
            f"{item.symbol:<14} {item.status:<18} "
            f"{item.fetched_bars:>7} {item.saved_bars:>5} "
            f"{_format_ts(item.first_ts):<21} {_format_ts(item.last_ts)}"
        )
        if item.notes:
            print(f"  notes: {', '.join(item.notes)}")

    print("\nWritten Parquet files and metadata:")
    for item in result.results:
        path = store.path_for_ohlcv(
            item.symbol,
            pipeline_cfg.timeframe,
            pipeline_cfg.venue.exchange_id,
        )
        metadata = store.read_ohlcv_metadata(
            item.symbol,
            pipeline_cfg.timeframe,
            pipeline_cfg.venue.exchange_id,
        )
        print(f"\n{path}")
        if metadata is None:
            print("  metadata: <missing>")
            continue
        for key, value in metadata.model_dump().items():
            print(f"  {key}: {value}")

    assert result.symbol_count == len(symbols)
    assert result.success_count >= 1
    for item in result.results:
        if item.status in {"FAILED", "NO_DATA"}:
            continue
        path = store.path_for_ohlcv(
            item.symbol,
            pipeline_cfg.timeframe,
            pipeline_cfg.venue.exchange_id,
        )
        assert path.exists(), item.symbol


def _closed_candle_end_ms(timeframe: str) -> int:
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    bar_ms = int(get_timeframe_minutes(timeframe) * 60_000)
    return (now_ms // bar_ms) * bar_ms - bar_ms


def _format_ts(ms: int | None) -> str:
    if ms is None:
        return "-"
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


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
