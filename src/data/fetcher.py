import ccxt
import pandas as pd
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable
import pyarrow as pa
import pyarrow.parquet as pq
import json

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

def fetch_data(
    exchange_id: str, 
    symbol: str, 
    timeframe: str = '1h', 
    start_date: Optional[datetime] = None, 
    end_date: Optional[datetime] = None,
    progress_callback: Optional[Callable[[int, str], None]] = None
):
    """
    Fetches historical OHLCV data from a specific exchange.
    
    Args:
        exchange_id: CCXT exchange ID (e.g., 'binance', 'bybit')
        symbol: Trading pair (e.g., 'BTC/USDT')
        timeframe: Candle size (e.g., '1h', '1d', '15m')
        start_date: Start datetime (UTC)
        end_date: End datetime (UTC). Defaults to now.
        progress_callback: Function(percentage, message) to report status.
    """
    try:
        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class()
    except AttributeError:
        raise ValueError(f"Exchange '{exchange_id}' not found in CCXT.")

    # Sort and set index
    # ... logic continues ...
    
    # Save Logic
    safe_symbol = symbol.replace('/', '_')
    save_dir = DATA_DIR / exchange_id / timeframe
    save_dir.mkdir(parents=True, exist_ok=True)
    file_path = save_dir / f"{safe_symbol}.parquet"
    
    # ---------------------------------------------------------
    # SMART FETCH: Check coverage before fetching from API
    # ---------------------------------------------------------
    # To do this effectively, we need to inspect the file *before* the while-loop API calls.
    # But this function structure currently prepares the while-loop first.
    # I should move this check to the VERY TOP of the function.
    # However, since I am using `replace_file_content` which works on chunks, 
    # and I can't restart the whole function easily without a massive replace,
    # I will modify the logic to check existence early.
    
    # Actually, `fetch_data` is called with specific start/end. 
    # If I check simply:
    if file_path.exists():
        try:
            # Quick Metadata Check
            meta = pq.read_metadata(file_path)
            meta_dict = meta.metadata or {}
            if b'start_date' in meta_dict and b'end_date' in meta_dict:
                file_start = datetime.strptime(meta_dict[b'start_date'].decode('utf-8'), '%Y-%m-%d %H:%M:%S')
                file_end = datetime.strptime(meta_dict[b'end_date'].decode('utf-8'), '%Y-%m-%d %H:%M:%S')
                
                # Check for full coverage
                # Buffer of 1 hour/interval to be safe?
                if start_date >= file_start and (end_date is None or end_date <= file_end):
                    msg = f"Data fully exists locally ({file_start} to {file_end}). Skipping API fetch."
                    print(msg)
                    if progress_callback: progress_callback(1.0, f"Skipped: Local data covers request.")
                    return pd.read_parquet(file_path)
        except Exception:
            pass # Fallback to fetch if check fails
            
    # Estimate total candles... (original code follows)
    
    start_ts = int(start_date.timestamp() * 1000)
    # ...
    # This is rough because we don't know exchange limits perfectly or gaps
    # But good enough for UI feedback
    total_duration_ms = end_ts - since
    # Parse timeframe to ms (approximate for layout)
    tf_seconds = exchange.parse_timeframe(timeframe)
    expected_candles = total_duration_ms / (tf_seconds * 1000) if tf_seconds else 1000
    
    print(f"Fetching {symbol} from {exchange_id} ({timeframe})...")
    
    while True:
        try:
            # Respect rate limits
            time.sleep(exchange.rateLimit / 1000)
            
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=current_since, limit=limit)
            if not ohlcv:
                break
            
            # Filter matches only within range (ccxt sometimes returns before since, or we overshoot)
            # Actually we just append and filter later usually, but let's check the last timestamp
            last_ts = ohlcv[-1][0]
            
            all_ohlcv.extend(ohlcv)
            current_since = last_ts + 1
            
            # Update Progress
            fetched_duration = last_ts - since
            progress = min(0.99, fetched_duration / total_duration_ms)
            if progress_callback:
                current_date_str = datetime.fromtimestamp(last_ts / 1000).strftime('%Y-%m-%d')
                progress_callback(progress, f"Fetched up to {current_date_str}")
            
            if last_ts >= end_ts:
                break
                
        except Exception as e:
            print(f"Error fetching: {e}")
            if progress_callback:
                progress_callback(0, f"Error: {str(e)}")
            return

    if not all_ohlcv:
        if progress_callback: progress_callback(1.0, "No data found.")
        return

    # Convert to DataFrame
    df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # Final filter for strict range
    mask = (df['timestamp'] >= start_date)
    if end_date:
        mask &= (df['timestamp'] <= end_date)
    df = df[mask]
    
    # Sort and set index
    df = df.sort_values('timestamp').set_index('timestamp')
    
    # Check for missing data at the start (gap between requested start and actual first candle)
    # We use a threshold (e.g., 2 periods) to avoid noise from slight misalignments
    actual_start = df.index.min()
    warning_msg = ""
    if actual_start > start_date:
        gap = actual_start - start_date
        # If gap is substantial (e.g. > 24h), warn the user
        if gap.total_seconds() > 86400: # 1 day
            warning_msg = f"Warning: Data started at {actual_start} (requested {start_date}). Prior data unavailable."
            print(warning_msg)

    # Save Logic
    safe_symbol = symbol.replace('/', '_')
    save_dir = DATA_DIR / exchange_id / timeframe
    save_dir.mkdir(parents=True, exist_ok=True)
    file_path = save_dir / f"{safe_symbol}.parquet"
    
    if file_path.exists():
        # If exists, we might want to merge or overwrite. 
        # For this function, let's assume if it returns data, we allow the caller to handle, 
        # BUT if called from UI as "Fetch", we usually imply "Get this specific range".
        # However, to keep it simple: "Fetch" = Overwrite/Create New for that range? 
        # User wants "Complete Data" as a separate option.
        # Let's read existing, merge, and save to keep data contiguous.
        try:
            existing_df = pd.read_parquet(file_path)
            # Combine and drop duplicates on index
            df = pd.concat([existing_df, df])
            df = df[~df.index.duplicated(keep='last')]
            df = df.sort_index()
        except Exception as e:
            print(f"Error reading existing file {file_path}: {e}")

    # Final DataFrame is ready (df) - merged and sorted.
    
    # Calculate Metadata
    meta_start = df.index.min().strftime('%Y-%m-%d %H:%M:%S')
    meta_end = df.index.max().strftime('%Y-%m-%d %H:%M:%S')
    
    # Convert to PyArrow Table
    table = pa.Table.from_pandas(df)
    
    # Prepare Custom Metadata
    custom_meta = {
        'start_date': meta_start,
        'end_date': meta_end,
        'rows': str(len(df)),
        'symbol': symbol,
        'exchange': exchange_id
    }
    
    # Merge with existing PyArrow metadata (which contains pandas schema info)
    existing_meta = table.schema.metadata or {}
    # Parquet metadata keys must be bytes
    for k, v in custom_meta.items():
        existing_meta[k.encode('utf-8')] = v.encode('utf-8')
        
    table = table.replace_schema_metadata(existing_meta)
    
    # Write with pyarrow directly
    pq.write_table(table, file_path, write_statistics=True)
    
    if progress_callback:
        final_msg = f"Completed! Saved {len(df)} rows."
        if warning_msg:
            final_msg += f" \n[{warning_msg}]"
        progress_callback(1.0, final_msg)
    print(f"Saved {len(df)} rows to {file_path}")
    
    return df

def get_available_symbols(exchange_id: str) -> list[str]:
    """
    Fetches all available symbols from the exchange.
    """
    try:
        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class()
        exchange.load_markets()
        return sorted(exchange.symbols)
    except Exception as e:
        print(f"Error fetching symbols: {e}")
        return []

def update_dataset(exchange_id: str, symbol: str, timeframe: str, progress_callback: Optional[Callable[[int, str], None]] = None):
    """
    Fetches missing data from the last available timestamp to now.
    """
    safe_symbol = symbol.replace('/', '_')
    file_path = DATA_DIR / exchange_id / timeframe / f"{safe_symbol}.parquet"
    
    if not file_path.exists():
        if progress_callback: progress_callback(0, "File not found. Fetching full history.")
        # If file doesn't exist, fetch from a default start date (e.g., 2023-01-01)
        # The fetch_data function already handles start_date=None
        return fetch_data(exchange_id, symbol, timeframe, start_date=None, end_date=datetime.now(), progress_callback=progress_callback)

    try:
        existing_df = pd.read_parquet(file_path)
        last_ts = existing_df.index.max()
        
        # Start from last_ts (exclusive, so add a small delta if needed, but CCXT handles 'since' well)
        # Convert last_ts (pandas Timestamp) to datetime
        start_date = last_ts.to_pydatetime()
        end_date = datetime.now()
        
        # If the last timestamp is very recent, no need to update
        if (end_date - start_date).total_seconds() < 60: # e.g., less than 1 minute difference
            if progress_callback: progress_callback(1.0, "Data is already up to date.")
            print("Data is already up to date.")
            return existing_df
        
        if progress_callback: progress_callback(0.1, f"Fetching update from {start_date}...")
        
        # Reuse fetch_data which now handles the merge/save logic
        # fetch_data will return the merged DataFrame
        updated_df = fetch_data(exchange_id, symbol, timeframe, start_date=start_date, end_date=end_date, progress_callback=progress_callback)
        return updated_df
        
    except Exception as e:
        if progress_callback: progress_callback(0, f"Error updating: {e}")
        print(f"Error updating: {e}")
        return None

def fetch_top_markets(exchange_id: str = 'binance', limit: int = 50) -> pd.DataFrame:
    """
    Fetches 24h ticker data and returns top markets by Quote Volume.
    Useful for screening liquid pairs.
    """
    try:
        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class()
    except AttributeError:
        return pd.DataFrame()

    try:
        # Some exchanges require load_markets before fetch_tickers
        exchange.load_markets()
        tickers = exchange.fetch_tickers()
        
        # specific to swap vs spot, let's filter for USDT pairs generally
        # We try to keep it generic but usually we want USDT
        data = []
        for symbol, ticker in tickers.items():
            if '/USDT' not in symbol:
                continue
            
            quote_vol = ticker.get('quoteVolume')
            if quote_vol is None:
                continue
                
            data.append({
                'Symbol': symbol,
                'Price': ticker.get('last'),
                '24h Vol (M)': quote_vol / 1_000_000,
                '24h Change %': ticker.get('percentage'),
            })
            
        df = pd.DataFrame(data)
        if df.empty:
            return df
            
        df = df.sort_values('24h Vol (M)', ascending=False).head(limit)
        return df.reset_index(drop=True)
        
    except Exception as e:
        print(f"Error fetching markets: {e}")
        return pd.DataFrame()

if __name__ == "__main__":
    # Test
    # fetch_data('binance', 'BTC/USDT', start_date=datetime(2024, 1, 1), end_date=datetime(2024, 1, 5))
    print(fetch_top_markets().head())
