"""Timed live probe for the staged universe volume filters.

Run explicitly with:
    PYTHONPATH=. .venv/bin/python -m pytest tests/universe/test_live_volume_filter_probe.py -m live -s

This probe always writes to a fresh repo-local test store. It does not assume
any previous OHLCV data exists.
"""

from __future__ import annotations

import time
import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from src.core.config import settings
from src.core.logger import configure_logger
from src.data.ohlcv import OHLCVMarketMetadata
from src.data.storage.local_parquet import LocalOHLCVParquetStore
from src.data.sync import OHLCVBackfillRequest, OHLCVBackfillService
from src.data.sync.config import load_ohlcv_backfill_config
from src.data.sync.helpers import aggregate_sync_results
from src.engine.trader.config import (
    load_pipeline_config,
    load_run_profile_config,
    load_universe_config,
)
from src.exchange.config.venue import (
    load_ccxt_exchange_config,
    load_exchange_venue_config,
)
from src.exchange.data.ccxt_adapter import CcxtMarketDataAdapter
from src.universe.filters.market_tickers import select_symbols_by_quote_volume
from src.universe.filters.ohlcv_liquidity import select_by_quote_volume_metric
from src.utils.timeframe_math import get_timeframe_minutes, last_closed_candle_open_ms

RUN_CONFIG = "configs/runs/dev_1m_research.yml"


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_volume_filter_flow_prints_counts_and_stage_timings() -> None:
    """Fetch live tickers, apply all liquidity stages, and print bottlenecks."""
    run_cfg = load_run_profile_config(RUN_CONFIG)
    pipeline_cfg = load_pipeline_config(run_cfg.pipeline)
    venue_cfg = load_exchange_venue_config(run_cfg.venue)
    exchange_cfg = load_ccxt_exchange_config(run_cfg.market_profile)
    universe_cfg = load_universe_config(run_cfg.universe)
    backfill_policy = load_ohlcv_backfill_config(
        pipeline_cfg.data.backfill_policy_config
    ).to_fetch_policy()

    output_dir = _fresh_output_dir()
    _assert_safe_output_dir(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    configure_logger(
        log_path=str(output_dir / "live_volume_filter_probe.jsonl"),
        log_level="silent",
    )

    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    stored_cfg = universe_cfg.filters.stored_data_liquidity
    pre_cfg = universe_cfg.filters.prefilter_liquidity
    end_ts = last_closed_candle_open_ms(stored_cfg.timeframe, now_ms=now_ms)
    prefilter_end_ts = last_closed_candle_open_ms(pre_cfg.timeframe, now_ms=now_ms)
    start_ts = end_ts - pipeline_cfg.historical_days * 86_400_000
    end_dt = datetime.fromtimestamp(end_ts / 1000, tz=timezone.utc)
    start_dt = datetime.fromtimestamp(start_ts / 1000, tz=timezone.utc)
    prefilter_end_dt = datetime.fromtimestamp(
        prefilter_end_ts / 1000,
        tz=timezone.utc,
    )

    print("\n=== LIVE VOLUME FILTER PROBE ===")
    print("\nConfig files used:")
    _print_config_path("run config", RUN_CONFIG)
    _print_config_path("pipeline config", run_cfg.pipeline)
    _print_config_path("venue config", run_cfg.venue)
    _print_config_path("market profile config", run_cfg.market_profile)
    _print_config_path("universe config", run_cfg.universe)
    _print_config_path(
        "backfill policy config",
        pipeline_cfg.data.backfill_policy_config,
    )
    _print_kv("fresh output dir", output_dir)
    _print_kv("exchange", venue_cfg.exchange_id)
    _print_kv("credential tier", venue_cfg.credential_tier)
    _print_kv("market profile", exchange_cfg.market_contract.name)
    _print_kv("research timeframe", pipeline_cfg.timeframe)
    _print_kv("research historical days", pipeline_cfg.historical_days)
    _print_kv("prefilter frozen end UTC", prefilter_end_dt.isoformat())
    _print_kv("backfill frozen end UTC", end_dt.isoformat())
    _print_filter_config(universe_cfg)

    timings: dict[str, float] = {}
    api_key, api_secret = _credentials_for_tier(venue_cfg.credential_tier)

    async with CcxtMarketDataAdapter(
        venue_cfg.exchange_id,
        api_key,
        api_secret,
        exchange_cfg,
    ) as market_data:
        tickers, timings["fetch_market_tickers"] = await _time_async(
            market_data.fetch_market_tickers,
        )
        print("\n[1] Market tickers")
        _print_kv("tickers fetched", len(tickers))
        _print_kv("duration", _seconds(timings["fetch_market_tickers"]))
        _print_sample("ticker symbols", [ticker.symbol for ticker in tickers])

        ticker_cfg = universe_cfg.filters.ticker_liquidity
        t0 = time.perf_counter()
        if ticker_cfg.enabled:
            after_ticker = select_symbols_by_quote_volume(
                tickers,
                min_quote_volume=ticker_cfg.min_24h_quote_volume,
            )
        else:
            after_ticker = [ticker.symbol for ticker in tickers]
        timings["ticker_liquidity"] = time.perf_counter() - t0
        print("\n[2] Ticker liquidity")
        _print_kv("enabled", ticker_cfg.enabled)
        _print_kv(
            "rule",
            f"24h quoteVolume > ${ticker_cfg.min_24h_quote_volume:,.0f}",
        )
        _print_kv("before", len(tickers))
        _print_kv("after", len(after_ticker))
        _print_kv("removed", len(tickers) - len(after_ticker))
        _print_kv("duration", _seconds(timings["ticker_liquidity"]))
        _print_sample("after ticker_liquidity", after_ticker)

        prefilter_start = time.perf_counter()
        prefilter_frames: dict[str, pd.DataFrame] = {}
        prefilter_failures: dict[str, str] = {}
        if pre_cfg.enabled and after_ticker:
            prefilter_frames, prefilter_failures = await _fetch_prefilter_frames(
                market_data=market_data,
                symbols=after_ticker,
                timeframe=pre_cfg.timeframe,
                lookback_bars=pre_cfg.lookback_bars,
                end_ts=prefilter_end_ts,
                pause_seconds=backfill_policy.request_pause_seconds,
            )
            prefilter_selection = select_by_quote_volume_metric(
                prefilter_frames,
                lookback_bars=pre_cfg.lookback_bars,
                metric=pre_cfg.metric,
                min_value=pre_cfg.min_value,
                percentile=pre_cfg.percentile,
            )
            after_prefilter = list(prefilter_selection.pool)
        else:
            after_prefilter = list(after_ticker)
        timings["prefilter_liquidity"] = time.perf_counter() - prefilter_start
        print("\n[3] Prefilter liquidity")
        _print_kv("enabled", pre_cfg.enabled)
        _print_kv(
            "rule",
            f"{pre_cfg.metric} over {pre_cfg.lookback_bars} x {pre_cfg.timeframe}",
        )
        _print_kv("min", f"${pre_cfg.min_value:,.0f}")
        _print_kv("before", len(after_ticker))
        _print_kv("frames fetched", len(prefilter_frames))
        _print_kv("failures/no-data", len(prefilter_failures))
        _print_kv("after", len(after_prefilter))
        _print_kv("removed", len(after_ticker) - len(after_prefilter))
        _print_kv("duration", _seconds(timings["prefilter_liquidity"]))
        _print_sample("after prefilter_liquidity", after_prefilter)
        _print_failures("prefilter failures/no-data", prefilter_failures)

        store = LocalOHLCVParquetStore(str(output_dir))
        service = OHLCVBackfillService(
            market_data=market_data,
            store=store,
            policy=backfill_policy,
        )

        backfill_start = time.perf_counter()
        backfill_results = []
        if after_prefilter:
            request = OHLCVBackfillRequest(
                exchange_id=venue_cfg.exchange_id,
                timeframe=stored_cfg.timeframe,
                start_ts=start_ts,
                end_ts=end_ts,
                symbols=after_prefilter,
                market=OHLCVMarketMetadata(
                    market_type=exchange_cfg.market_contract.default_type,
                    market_sub_type=exchange_cfg.market_contract.default_sub_type,
                    settle=exchange_cfg.market_contract.default_settle,
                ),
            )
            for index, symbol in enumerate(after_prefilter, start=1):
                backfill_results.append(await service.backfill_symbol(request, symbol))
                if index % 10 == 0 or index == len(after_prefilter):
                    ok = sum(
                        r.status not in {"FAILED", "NO_DATA"}
                        for r in backfill_results
                    )
                    failed = len(backfill_results) - ok
                    print(
                        f"    backfilled {index}/{len(after_prefilter)} "
                        f"| ok={ok} | failed/no_data={failed}",
                        flush=True,
                    )
        else:
            _print_kv("fresh backfill skipped", "no symbols survived prefilter")
        backfill_sync = aggregate_sync_results(
            venue_cfg.exchange_id,
            stored_cfg.timeframe,
            backfill_results,
        )
        timings["fresh_backfill"] = time.perf_counter() - backfill_start
        print("\n[4] Fresh backfill")
        _print_kv("timeframe", stored_cfg.timeframe)
        _print_kv("window start UTC", start_dt.isoformat())
        _print_kv("window end UTC", end_dt.isoformat())
        _print_kv("requested symbols", backfill_sync.symbol_count)
        _print_kv("success count", backfill_sync.success_count)
        _print_kv("failure count", backfill_sync.failure_count)
        _print_kv("status counts", _status_counts(backfill_sync.results))
        _print_kv("duration", _seconds(timings["fresh_backfill"]))
        backfilled_symbols = [
            result.symbol
            for result in backfill_sync.results
            if result.status not in {"FAILED", "NO_DATA"}
        ]
        _print_sample("freshly backfilled symbols", backfilled_symbols)
        _print_sync_failures(backfill_sync.results)

        stored_start = time.perf_counter()
        stored_frames = {}
        for result in backfill_sync.results:
            if result.status in {"FAILED", "NO_DATA"}:
                continue
            stored_frames[result.symbol] = store.load_ohlcv(
                result.symbol,
                stored_cfg.timeframe,
                venue_cfg.exchange_id,
            )
        if stored_cfg.enabled and stored_frames:
            stored_selection = select_by_quote_volume_metric(
                stored_frames,
                lookback_bars=stored_cfg.lookback_bars,
                metric=stored_cfg.metric,
                min_value=stored_cfg.min_value,
                percentile=stored_cfg.percentile,
            )
            after_stored = list(stored_selection.pool)
        else:
            after_stored = list(stored_frames)
        timings["stored_data_liquidity"] = time.perf_counter() - stored_start
        print("\n[5] Stored-data liquidity")
        _print_kv("enabled", stored_cfg.enabled)
        _print_kv(
            "rule",
            f"{stored_cfg.metric} over {stored_cfg.lookback_bars} x {stored_cfg.timeframe}",
        )
        _print_kv("min", f"${stored_cfg.min_value:,.0f}")
        _print_kv("before", len(stored_frames))
        _print_kv("after", len(after_stored))
        _print_kv("removed", len(stored_frames) - len(after_stored))
        _print_kv("duration", _seconds(timings["stored_data_liquidity"]))
        _print_sample("after stored_data_liquidity", after_stored)

    print("\n=== SUMMARY ===")
    print("\nConfig files used:")
    _print_config_path("run config", RUN_CONFIG)
    _print_config_path("pipeline config", run_cfg.pipeline)
    _print_config_path("venue config", run_cfg.venue)
    _print_config_path("market profile config", run_cfg.market_profile)
    _print_config_path("universe config", run_cfg.universe)
    _print_config_path(
        "backfill policy config",
        pipeline_cfg.data.backfill_policy_config,
    )
    _print_kv("fresh output dir", output_dir)
    _print_kv("tickers fetched", len(tickers))
    _print_kv("after ticker_liquidity", len(after_ticker))
    _print_kv("after prefilter_liquidity", len(after_prefilter))
    _print_kv("freshly stored symbols", len(stored_frames))
    _print_kv("after stored_data_liquidity", len(after_stored))
    print("\nStage timings:")
    for name, seconds in timings.items():
        _print_kv(name, _seconds(seconds))

    assert tickers
    assert after_ticker
    assert after_prefilter
    assert after_stored


async def _fetch_prefilter_frames(
    *,
    market_data: CcxtMarketDataAdapter,
    symbols: list[str],
    timeframe: str,
    lookback_bars: int,
    end_ts: int,
    pause_seconds: float,
) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    start_ts = end_ts - int(get_timeframe_minutes(timeframe) * 60_000) * lookback_bars
    frames = {}
    failures = {}
    for index, symbol in enumerate(symbols, start=1):
        try:
            frame = await market_data.fetch_ohlcv(
                symbol,
                timeframe,
                lookback_bars,
                since=start_ts,
                end_ts=end_ts,
            )
            if not frame.empty:
                frames[symbol] = frame
            else:
                failures[symbol] = "NO_DATA: exchange_returned_no_rows"
        except Exception as exc:
            failures[symbol] = f"{type(exc).__name__}: {exc}"
        if index % 25 == 0 or index == len(symbols):
            print(
                f"    prefilter fetched {index}/{len(symbols)} "
                f"| frames={len(frames)} | failures={len(failures)}",
                flush=True,
            )
        if pause_seconds:
            await asyncio.sleep(pause_seconds)
    return frames, failures


async def _time_async(fn):
    start = time.perf_counter()
    result = await fn()
    return result, time.perf_counter() - start


def _credentials_for_tier(credential_tier: str) -> tuple[str, str]:
    if credential_tier == "live":
        return settings.exchange_live_api_key or "", settings.exchange_live_api_secret or ""
    return settings.exchange_readonly_api_key or "", settings.exchange_readonly_api_secret or ""


def _fresh_output_dir() -> Path:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / "test" / "live_volume_filter_probe" / run_id


def _assert_safe_output_dir(output_dir: Path) -> None:
    resolved = output_dir.resolve()
    repo_root = Path(__file__).resolve().parents[2]
    required_root = (repo_root / "data" / "test" / "live_volume_filter_probe").resolve()
    forbidden_roots = [
        Path("/private/tmp").resolve(),
        (repo_root / "data" / "parquet").resolve(),
    ]
    if not resolved.is_relative_to(required_root):
        raise AssertionError(f"probe output must stay under {required_root}: {resolved}")
    for forbidden_root in forbidden_roots:
        if resolved == forbidden_root or resolved.is_relative_to(forbidden_root):
            raise AssertionError(f"probe output must not use {forbidden_root}: {resolved}")


def _print_filter_config(universe_cfg) -> None:
    ticker = universe_cfg.filters.ticker_liquidity
    prefilter = universe_cfg.filters.prefilter_liquidity
    stored = universe_cfg.filters.stored_data_liquidity
    print("\nFilter config:")
    _print_kv("ticker min 24h quote", f"${ticker.min_24h_quote_volume:,.0f}")
    _print_kv(
        "prefilter rule",
        f"{prefilter.metric} >= ${prefilter.min_value:,.0f} "
        f"over {prefilter.lookback_bars} x {prefilter.timeframe}",
    )
    _print_kv(
        "stored rule",
        f"{stored.metric} >= ${stored.min_value:,.0f} "
        f"over {stored.lookback_bars} x {stored.timeframe}",
    )


def _print_config_path(label: str, path: str) -> None:
    resolved = (Path.cwd() / path).resolve()
    _print_kv(label, f"{path} ({resolved})")


def _print_sample(label: str, symbols: list[str], *, limit: int = 12) -> None:
    sample = symbols[:limit]
    suffix = "" if len(symbols) <= limit else f" ... +{len(symbols) - limit} more"
    _print_kv(f"{label} sample", f"{sample}{suffix}")


def _print_failures(label: str, failures: dict[str, str], *, limit: int = 20) -> None:
    if not failures:
        _print_kv(label, "none")
        return
    print(f"{label}:")
    for index, (symbol, reason) in enumerate(failures.items(), start=1):
        if index > limit:
            print(f"  ... +{len(failures) - limit} more")
            break
        print(f"  {symbol}: {reason}")


def _status_counts(results) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    return counts


def _print_sync_failures(results, *, limit: int = 20) -> None:
    failed = [
        result
        for result in results
        if result.status in {"FAILED", "NO_DATA"}
    ]
    if not failed:
        _print_kv("backfill failures/no-data", "none")
        return
    print("backfill failures/no-data:")
    for index, result in enumerate(failed, start=1):
        if index > limit:
            print(f"  ... +{len(failed) - limit} more")
            break
        notes = "; ".join(result.notes) if result.notes else result.status
        print(f"  {result.symbol}: {result.status} ({notes})")


def _seconds(seconds: float) -> str:
    return f"{seconds:.2f}s"


def _print_kv(label: str, value: object) -> None:
    print(f"{label:<32} {value}")
