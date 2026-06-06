"""
Tests for LocalOHLCVParquetStore.
Uses pytest tmp_path for isolated filesystem operations.
"""

import pandas as pd
import pytest

from src.data.ohlcv import OHLCVMetadata
from src.data.storage.local_parquet import LocalOHLCVParquetStore


def test_parquet_metadata_injection(tmp_path):
    """
    Validates that our custom dict metadata correctly embeds
    in the binary Parquet schema header without needing
    to fully read the payload to memory.
    """
    # 1. Synthesize a mock DataFrame
    df = pd.DataFrame({
        "timestamp": [1600000000000, 1600003600000],
        "open": [10.0, 10.5],
        "high": [11.0, 11.2],
        "low": [9.0, 9.8],
        "close": [10.5, 10.9],
        "volume": [1500, 2000]
    })

    custom_metadata = {
        "start_date": "2020-09-13T12:26:40+00:00",
        "end_date": "2020-09-13T13:26:40+00:00",
        "rows": str(len(df)),
    }

    storage = LocalOHLCVParquetStore(base_dir=str(tmp_path))

    # 2. Write it using our specific logic — exchange is required
    storage.save_ohlcv("BTC_USDT", "1h", df, custom_metadata, exchange="bybit")

    assert (tmp_path / "bybit" / "1h" / "BTC_USDT.parquet").exists()

    # 3. Read STRICTLY the metadata (No pandas loading) — exchange is required
    read_metadata = storage.read_metadata("BTC_USDT", "1h", exchange="bybit")

    assert read_metadata["rows"] == "2"
    assert read_metadata["start_date"] == custom_metadata["start_date"]


def test_load_ohlcv_round_trip(tmp_path):
    """Save and load should produce identical data."""
    df = pd.DataFrame({
        "timestamp": [1600000000000, 1600003600000],
        "open": [10.0, 10.5],
        "high": [11.0, 11.2],
        "low": [9.0, 9.8],
        "close": [10.5, 10.9],
        "volume": [1500, 2000]
    })

    storage = LocalOHLCVParquetStore(base_dir=str(tmp_path))
    storage.save_ohlcv("ETH_USDT", "4h", df, {"status": "COMPLETE"}, exchange="bybit")

    loaded = storage.load_ohlcv("ETH_USDT", "4h", exchange="bybit")
    assert len(loaded) == 2
    assert loaded["close"].iloc[0] == 10.5


def test_load_missing_file_raises(tmp_path):
    """Loading a non-existent file should raise FileNotFoundError."""
    storage = LocalOHLCVParquetStore(base_dir=str(tmp_path))

    with pytest.raises(FileNotFoundError):
        storage.load_ohlcv("FAKE_COIN", "1h", exchange="bybit")


def test_save_ohlcv_accepts_typed_metadata(tmp_path):
    df = pd.DataFrame(
        {
            "timestamp": [1600000000000, 1600003600000],
            "open": [10.0, 10.5],
            "high": [11.0, 11.2],
            "low": [9.0, 9.8],
            "close": [10.5, 10.9],
            "volume": [1500, 2000],
        }
    )
    metadata = OHLCVMetadata.from_frame(
        symbol="BTC/USDT",
        exchange="bybit",
        timeframe="1h",
        source="bybit",
        status="COMPLETE",
        frame=df,
        coverage_start_ms=1600000000000,
        coverage_end_ms=1600003600000,
        last_closed_candle_ms=1600003600000,
    )
    storage = LocalOHLCVParquetStore(base_dir=str(tmp_path))

    storage.save_ohlcv("BTC/USDT", "1h", df, metadata, exchange="bybit")

    read = storage.read_ohlcv_metadata("BTC/USDT", "1h", exchange="bybit")
    assert read is not None
    assert read.symbol == "BTC/USDT"
    assert read.total_candles == 2
    assert read.coverage_end_ms == 1600003600000


def test_read_metadata_does_not_create_timeframe_directory(tmp_path):
    storage = LocalOHLCVParquetStore(base_dir=str(tmp_path))

    assert storage.read_metadata("MISSING/USDT", "1m", exchange="bybit") == {}
    assert not (tmp_path / "bybit").exists()
