import shutil
from pathlib import Path
import pandas as pd
import pytest
from datetime import datetime, timezone

from statarb.infra.lakehouse.writer import ParquetWriter
from statarb.infra.lakehouse.reader import DuckDBReader

@pytest.fixture
def temp_lake(tmp_path):
    lake_dir = tmp_path / "lake"
    yield lake_dir
    # Cleanup
    if lake_dir.exists():
        shutil.rmtree(lake_dir)

def test_write_and_read(temp_lake):
    writer = ParquetWriter(temp_lake)
    reader = DuckDBReader(temp_lake)

    # create dummy data
    data = {
        'timestamp': [
            datetime(2023, 1, 1, 10, 0, 0),
            datetime(2023, 1, 1, 11, 0, 0),
            datetime(2023, 1, 1, 12, 0, 0)
        ],
        'open': [100.0, 101.0, 102.0],
        'high': [102.0, 103.0, 104.0],
        'low': [99.0, 100.0, 101.0],
        'close': [101.0, 102.0, 103.0],
        'volume': [10.0, 20.0, 30.0]
    }
    df = pd.DataFrame(data)

    symbol = "BTC/USDT"
    exchange = "binance"
    timeframe = "1h"

    # Write
    writer.write(df, symbol, exchange, timeframe)

    # Read back
    df_read = reader.load_ohlcv(symbol, exchange, timeframe)
    
    assert not df_read.empty
    assert len(df_read) == 3
    assert df_read.iloc[0]['close'] == 101.0
    # Check hive partitioning columns attached
    assert df_read.iloc[0]['symbol'] == "BTC/USDT"
    assert df_read.iloc[0]['exchange'] == "binance"
    
def test_deduplication(temp_lake):
    writer = ParquetWriter(temp_lake)
    reader = DuckDBReader(temp_lake)
    
    symbol = "ETH/USDT"
    exchange = "bybit"
    timeframe = "15m"

    # Batch 1
    df1 = pd.DataFrame({
        'timestamp': [datetime(2023, 1, 1, 10, 0), datetime(2023, 1, 1, 10, 15)],
        'open': [10, 11], 'high': [10, 11], 'low': [10, 11], 'close': [10, 11], 'volume': [100, 100]
    })
    writer.write(df1, symbol, exchange, timeframe)

    # Batch 2 (Overlap with update)
    # 10:15 is updated (close 11 -> 12), 10:30 is new
    df2 = pd.DataFrame({
        'timestamp': [datetime(2023, 1, 1, 10, 15), datetime(2023, 1, 1, 10, 30)],
        'open': [11, 12], 'high': [11, 12], 'low': [11, 12], 'close': [12, 13], 'volume': [100, 100]
    })
    writer.write(df2, symbol, exchange, timeframe)

    df_read = reader.load_ohlcv(symbol, exchange, timeframe)
    
    # Should have 3 rows: 10:00, 10:15 (updated), 10:30
    assert len(df_read) == 3
    # Check update
    row_1015 = df_read[df_read['timestamp'] == pd.Timestamp('2023-01-01 10:15:00')]
    assert row_1015.iloc[0]['close'] == 12.0
