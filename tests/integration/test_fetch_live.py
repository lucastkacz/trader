import pytest
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
from statarb.infra.market_data.fetcher import fetch_all_ohlcv
from statarb.infra.lakehouse.reader import DuckDBReader

@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_btc_live_data(tmp_path):
    """
    Integration test that actually hits Binance API to fetch BTC data
    and verifies it is written correctly to the Lakehouse.
    """
    # Use a temporary directory for the lakehouse to avoid polluting real data
    # OR user wants to see it in market_data? The user asked to "save it in market_data".
    # But usually tests shouldn't write to production folders.
    # However, the user said "save it in market_data" in the previous turn.
    # I will use the real market_data folder as requested for this manual-style verification test.
    
    lake_dir = Path("market_data")
    symbols = ["BTC/USDT:USDT"]
    exchange = "binanceusdm"
    timeframe = "1h"
    
    end_date = datetime.utcnow().strftime("%Y-%m-%d")
    start_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    # Run fetcher
    await fetch_all_ohlcv(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        db_path=lake_dir,
        timeframe=timeframe,
        exchange_id=exchange
    )
    
    # Verify file exists
    # Note: The writer sanitizes BTC/USDT -> symbol=BTC-USDT
    file_path = lake_dir / f"exchange={exchange}/timeframe={timeframe}/symbol=BTC-USDT:USDT/data.parquet"
    assert file_path.exists(), f"Parquet file should exist at {file_path}"
    
    # Verify Content
    reader = DuckDBReader(lake_dir)
    df = reader.load_ohlcv("BTC/USDT:USDT", exchange, timeframe)
    
    assert not df.empty, "Dataframe should not be empty"
    
    # Check output
    print(f"\nFetched {len(df)} rows.")
    print("Head:\n", df.head())
    print("Tail:\n", df.tail())
    print("Schema:\n", df.dtypes)
    
    # Validations
    expected_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'symbol', 'exchange', 'timeframe']
    for col in expected_cols:
        assert col in df.columns, f"Missing column {col}"
        
    # Check types
    assert pd.api.types.is_datetime64_any_dtype(df['timestamp'])
    assert pd.api.types.is_float_dtype(df['close'])
