import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

from . import storage
from . import provider

DATA_DIR = Path("data")

def fetch_data(
    exchange_id: str, 
    symbol: str, 
    timeframe: str = '1h', 
    start_date: Optional[datetime] = None, 
    end_date: Optional[datetime] = None,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> pd.DataFrame:
    """
    Smart fetch: Checks local storage and only fetches missing segments from the API.
    """
    # Defaults
    if start_date is None:
        start_date = datetime(2023, 1, 1)
    if end_date is None:
        end_date = datetime.now()
        
    # Setup
    file_path = storage.get_file_path(DATA_DIR, exchange_id, timeframe, symbol)
    exchange = provider.get_exchange(exchange_id) # Initialize once

    # 1. Check Metadata
    meta = storage.get_stored_metadata(file_path)
    
    stored_start = meta.get('start_date')
    stored_end = meta.get('end_date')
    
    # Ranges to fetch
    fetch_ranges = []
    
    if not stored_start or not stored_end:
        # No data or invalid -> Fetch All
        fetch_ranges.append((start_date, end_date))
    else:
        # Calculate gaps
        
        # Gap before?
        if start_date < stored_start:
            # Fetch from requested_start up to stored_start
            # Subtracting a small buffer (e.g. 1ms) isn't strictly necessary with inclusive/exclusive logic 
            # but usually safely overlapping by 1 candle is fine for deduplication.
            fetch_ranges.append((start_date, stored_start))
            
        # Gap after?
        if end_date > stored_end:
            fetch_ranges.append((stored_end, end_date))
            
        # What if requested range is entirely inside? -> No fetch needed
        # What if requested range is non-overlapping? 
        # (e.g. req: 2020-2021, stored: 2023-2024) -> We fetch the gap? 
        # Creating a huge hole might be bad for plotting contiguous series.
        # Ideally we fetch the "gap" in between too if we want a contiguous file.
        # For simplicity in this version, let's treat the file as a "growing contiguous block".
        # If the requested data is completely disjoint from stored data, we might just append it,
        # but plotting would show a gap.
        
        # Check if we are requesting data *inside* a gap? 
        # e.g. Stored: Jan-Feb, Requested: Mar-Apr... (Gap Feb-Mar not filled).
        # We should just fetch what is requested. 
    
    # 2. Execute Fetches
    new_data_segments = []
    
    total_segments = len(fetch_ranges)
    for i, (seg_start, seg_end) in enumerate(fetch_ranges):
        if progress_callback:
            progress_callback(0.0, f"Fetching segment {i+1}/{total_segments}: {seg_start} -> {seg_end}")
            
        raw_ohlcv = provider.fetch_ohlcv_range(
            exchange, symbol, timeframe, seg_start, seg_end, progress_callback
        )
        
        if raw_ohlcv:
            df_seg = pd.DataFrame(raw_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df_seg['timestamp'] = pd.to_datetime(df_seg['timestamp'], unit='ms')
            df_seg = df_seg.set_index('timestamp').sort_index()

            # --- Funding Rate Integration ---
            try:
                # Attempt to fetch funding rates for this same segment
                funding_data = provider.fetch_funding_rate_history(exchange, symbol, seg_start, seg_end)
                if funding_data:
                    df_fund = pd.DataFrame(funding_data)
                    # Keep timestamp and fundingRate
                    if 'timestamp' in df_fund.columns and 'fundingRate' in df_fund.columns:
                        df_fund['timestamp'] = pd.to_datetime(df_fund['timestamp'], unit='ms')
                        df_fund = df_fund.set_index('timestamp')[['fundingRate']]
                        
                        # Merge: Left join on OHLCV timestamp
                        # Note: Funding rates usually happen every 8h. OHLCV might be 1h.
                        # We want the funding rate column to have values at the 8h mark? 
                        # Or forward fill? Standard is usually point-in-time event.
                        # MERGE with tolerance? Or just exact match?
                        # Let's do a join. Most rows will be NaN.
                        df_seg = df_seg.join(df_fund, how='left')
            except Exception as e:
                print(f"Funding fetch warning: {e}")
                
            # If fundingRate column missing (spot or failed), ensure it exists as NaN for schema consistency
            if 'fundingRate' not in df_seg.columns:
                 df_seg['fundingRate'] = float('nan')

            new_data_segments.append(df_seg)
            
    # 3. Merge & Save
    if new_data_segments:
        # Combine all new segments
        new_df = pd.concat(new_data_segments)
        # Verify timestamps are legitimate
        new_df = new_df[~new_df.index.duplicated(keep='last')]
        
        print(f"Fetched {len(new_df)} new rows via smart fetch.")
        
        # Save (merges with existing)
        storage.save_data(new_df, file_path, exchange_id, symbol)
        
        if progress_callback:
            progress_callback(1.0, f"💾 Saved {len(new_df)} new rows to storage.")
        
    else:
        print("Data fully cached. No API calls made.")
        if progress_callback:
            progress_callback(1.0, "✨ Data fully cached. No API calls made.")

    # 4. Return Requested View
    # Reload fully to return the consistent requested range
    final_df = storage.load_data(file_path, start_date, end_date)
    return final_df

def update_dataset(exchange_id: str, symbol: str, timeframe: str, progress_callback: Optional[Callable[[int, str], None]] = None):
    """
    Convenience wrapper to update to 'now'.
    """
    # This leverages the smart fetch logic automatically since end_date defaults to now.
    return fetch_data(exchange_id, symbol, timeframe, start_date=None, end_date=datetime.now(), progress_callback=progress_callback)

def get_available_symbols(exchange_id: str):
    return provider.get_all_symbols(exchange_id)
    
def fetch_top_markets(exchange_id: str = 'binance', limit: int = 50):
    return provider.get_market_tickers(exchange_id, limit)
