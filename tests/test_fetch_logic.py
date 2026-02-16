import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import shutil

# Add src to path
sys.path.append(".")

from src.data.fetcher.core import fetch_data
from src.data.fetcher import storage

def log_progress(progress, message):
    print(f"[{progress*100:.0f}%] {message}")

def run_test():
    exchange = "binance"
    symbol = "BNB/USDT"
    timeframe = "1d"
    
    # 1. Cleanup: Ensure we start fresh
    print("\n--- STEP 1: Cleanup ---")
    data_dir = Path("data")
    file_path = storage.get_file_path(data_dir, exchange, timeframe, symbol)
    if file_path.exists():
        file_path.unlink()
        print(f"Deleted existing file: {file_path}")
    
    # 2. Initial Fetch
    print("\n--- STEP 2: Initial Fetch (Jan 2024) ---")
    start_dt = datetime(2024, 1, 1)
    end_dt = datetime(2024, 1, 31)
    
    df1 = fetch_data(exchange, symbol, timeframe, start_dt, end_dt, progress_callback=log_progress)
    print(f"Result: DataFrame with {len(df1)} rows.")
    
    # 3. Duplicate Fetch
    print("\n--- STEP 3: Duplicate Fetch (Exact Same Range) ---")
    df2 = fetch_data(exchange, symbol, timeframe, start_dt, end_dt, progress_callback=log_progress)
    print(f"Result: DataFrame with {len(df2)} rows.")
    
    # 4. Extended Fetch
    print("\n--- STEP 4: Extended Fetch (Adding Feb 1-10) ---")
    end_dt_ext = datetime(2024, 2, 10)
    df3 = fetch_data(exchange, symbol, timeframe, start_dt, end_dt_ext, progress_callback=log_progress)
    print(f"Result: DataFrame with {len(df3)} rows.")

if __name__ == "__main__":
    run_test()
