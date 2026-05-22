"""CLI for read-only promoted-pair market-data refresh."""

import argparse
import asyncio
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from src.core.config import settings
from src.core.logger import configure_logger
from src.data.fetcher.exchange_client import create_exchange, fetch_klines
from src.data.storage.local_parquet import ParquetStorage
from src.engine.trader.config import load_pipeline_config
from src.engine.trader.runtime.pair_validity import (
    PairDataRefreshPolicy,
    refresh_promoted_pair_market_data,
)
from src.engine.trader.runtime.artifacts import promoted_pair_artifact_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Refresh local OHLCV for symbols in the promoted pair artifact"
    )
    parser.add_argument(
        "--pipeline",
        required=True,
        help="Path to typed pipeline YAML, e.g. configs/pipelines/dev.yml",
    )
    parser.add_argument(
        "--artifact-path",
        default=None,
        help="Optional promoted artifact path override",
    )
    parser.add_argument(
        "--overlap-bars",
        type=int,
        default=5,
        help="Closed bars to refetch before the latest local candle",
    )
    parser.add_argument(
        "--missing-lookback-bars",
        type=int,
        default=1500,
        help="Bars to fetch when a promoted symbol has no local parquet",
    )
    parser.add_argument(
        "--fetch-limit",
        type=int,
        default=1000,
        help="Maximum OHLCV rows requested per exchange call",
    )
    parser.add_argument(
        "--now",
        default=None,
        help="Optional ISO timestamp for deterministic refresh windows",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    args = parser.parse_args(argv)

    if args.json:
        configure_logger(log_level="silent")

    return asyncio.run(_async_main(args))


async def _async_main(args: argparse.Namespace) -> int:
    pipeline_cfg = load_pipeline_config(args.pipeline)
    execution_cfg = pipeline_cfg.execution
    if execution_cfg.credential_tier != "readonly":
        raise ValueError(
            "Pair-data refresh requires pipeline execution.credential_tier='readonly'"
        )

    artifact_path = (
        Path(args.artifact_path)
        if args.artifact_path is not None
        else promoted_pair_artifact_path(
            pipeline_cfg.timeframe,
            execution_cfg.artifact_base_dir,
        )
    )
    policy = PairDataRefreshPolicy(
        overlap_bars=args.overlap_bars,
        missing_lookback_bars=args.missing_lookback_bars,
        fetch_limit=args.fetch_limit,
    )
    exchange = create_exchange(
        execution_cfg.exchange,
        settings.exchange_readonly_api_key or "",
        settings.exchange_readonly_api_secret or "",
    )
    try:
        report = await refresh_promoted_pair_market_data(
            surviving_pairs_path=artifact_path,
            storage=ParquetStorage(execution_cfg.market_data_base_dir),
            exchange=exchange,
            exchange_id=execution_cfg.exchange,
            timeframe=pipeline_cfg.timeframe,
            policy=policy,
            fetch_klines=fetch_klines,
            now=_parse_now(args.now),
        )
    finally:
        await exchange.close()

    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        _print_report(report)
    return 0


def _print_report(report) -> None:
    print("PROMOTED PAIR DATA REFRESH")
    print(f"Artifact: {report.artifact_path}")
    print(f"Scope: {report.exchange} {report.timeframe}")
    print(f"Symbols: {report.symbol_count}")
    print(f"Started: {report.started_at}")
    print(f"Finished: {report.finished_at}")
    print()
    print(f"{'Symbol':<18} {'Status':<12} {'Fetched':>7} {'Saved':>7} {'After Latest':<25}")
    print(f"{'-'*18} {'-'*12} {'-'*7} {'-'*7} {'-'*25}")
    for result in report.results:
        print(
            f"{result.symbol:<18} {result.status:<12} "
            f"{result.fetched_bars:>7} {result.saved_bars:>7} "
            f"{result.after_latest_at or 'N/A':<25}"
        )
        if result.notes:
            print(f"  notes: {', '.join(result.notes)}")


def _parse_now(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


if __name__ == "__main__":
    raise SystemExit(main())

