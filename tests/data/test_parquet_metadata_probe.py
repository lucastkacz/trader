"""Verbose Parquet metadata probe for OHLCV files written by live backfills.

Run after the live backfill probe:
    .venv/bin/python -m pytest tests/data/test_parquet_metadata_probe.py -m live -s
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from src.data.storage.local_parquet import LocalOHLCVParquetStore


@pytest.mark.live
def test_print_local_ohlcv_parquet_metadata() -> None:
    """Print schema-level metadata without calling the exchange."""
    print(
        "\nTEST: Reads local OHLCV Parquet files from the live backfill probe and "
        "prints raw plus typed metadata without calling the exchange."
    )
    base_dir = Path(
        os.environ.get("OHLCV_LIVE_BACKFILL_DIR", "data/test/live_backfill_probe")
    )
    store = LocalOHLCVParquetStore(str(base_dir))
    parquet_paths = sorted(base_dir.glob("*/*/*.parquet"))
    if not parquet_paths:
        pytest.skip(
            "No probe parquet files found. Run "
            "tests/data/test_live_backfill_probe.py first."
        )

    _print_header("LOCAL PARQUET METADATA PROBE")
    _print_kv("base dir", base_dir)
    _print_kv("files found", len(parquet_paths))

    for path in parquet_paths:
        exchange = path.parent.parent.name
        timeframe = path.parent.name
        clean_symbol = path.stem
        raw_metadata = store.read_metadata(clean_symbol, timeframe, exchange)
        typed_metadata = store.read_ohlcv_metadata(clean_symbol, timeframe, exchange)
        frame = store.load_ohlcv(clean_symbol, timeframe, exchange)
        parquet_file = pq.ParquetFile(path)

        print(f"\n{path}")
        _print_kv("exchange", exchange)
        _print_kv("timeframe", timeframe)
        _print_kv("path symbol", clean_symbol)
        _print_kv("parquet rows", parquet_file.metadata.num_rows)
        _print_kv("row groups", parquet_file.metadata.num_row_groups)
        _print_kv("columns", ", ".join(frame.columns))
        if not frame.empty:
            _print_kv("first row", _format_ts(int(frame["timestamp"].min())))
            _print_kv("last row", _format_ts(int(frame["timestamp"].max())))

        print("typed metadata:")
        if typed_metadata is None:
            print("  <missing>")
        else:
            for key, value in typed_metadata.model_dump().items():
                print(f"  {key}: {value}")

        print("raw parquet metadata:")
        for key, value in sorted(raw_metadata.items()):
            print(f"  {key}: {value}")

    assert parquet_paths


def _format_ts(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def _print_header(title: str) -> None:
    print(f"\n=== {title} ===")


def _print_kv(label: str, value: object) -> None:
    print(f"{label:<26} {value}")
