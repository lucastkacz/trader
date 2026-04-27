"""
Tests for ParquetStorage.
Uses pytest tmp_path for isolated filesystem operations.
"""

import os
import pandas as pd

from src.data.storage.local_parquet import ParquetStorage


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

    storage = ParquetStorage(base_dir=str(tmp_path))

    # 2. Write it using our specific logic — exchange is required
    storage.save_ohlcv("BTC_USDT", "1h", df, custom_metadata, exchange="bybit")

    assert os.path.exists(tmp_path / "bybit" / "1h" / "BTC_USDT.parquet")

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

    storage = ParquetStorage(base_dir=str(tmp_path))
    storage.save_ohlcv("ETH_USDT", "4h", df, {"status": "COMPLETE"}, exchange="bybit")

    loaded = storage.load_ohlcv("ETH_USDT", "4h", exchange="bybit")
    assert len(loaded) == 2
    assert loaded["close"].iloc[0] == 10.5


def test_load_missing_file_raises(tmp_path):
    """Loading a non-existent file should raise FileNotFoundError."""
    storage = ParquetStorage(base_dir=str(tmp_path))

    with __import__("pytest").raises(FileNotFoundError):
        storage.load_ohlcv("FAKE_COIN", "1h", exchange="bybit")
