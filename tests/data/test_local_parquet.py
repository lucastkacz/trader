import os
import pytest
import pandas as pd
from datetime import datetime, timezone
import pyarrow.parquet as pq

try:
    from src.data.storage.local_parquet import ParquetStorage
except ImportError:
    pass

def test_parquet_metadata_injection(tmp_path):
    """
    Validates that our custom dict metadata correctly embeds
    in the binary Parquet schema header without needing
    to fully read the payload to memory.
    """
    test_filepath = tmp_path / "test_ohlcv.parquet"
    
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
    
    # 2. Write it using our specific logic
    storage.save_ohlcv("BTC_USDT", "1h", df, custom_metadata)
    
    assert os.path.exists(test_filepath) == False
    assert os.path.exists(tmp_path / "binanceusdm" / "1h" / "BTC_USDT.parquet") == True
    
    written_file = str(tmp_path / "binanceusdm" / "1h" / "BTC_USDT.parquet")
    
    # 3. Read STRICTLY the metadata (No pandas loading)
    read_metadata = storage.read_metadata("BTC_USDT", "1h")
    
    assert read_metadata["rows"] == "2"
    assert read_metadata["start_date"] == custom_metadata["start_date"]
