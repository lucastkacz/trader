import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")

def load_data(symbols: list[str], timeframe: str = '1h') -> dict[str, pd.DataFrame]:
    """
    Loads Parquet data for multiple symbols.
    Searches recursively in data/ for matching symbol files.
    """
    data = {}
    for symbol in symbols:
        safe_symbol = symbol.replace('/', '_')
        
        # Search anywhere in data/ for {safe_symbol}.parquet
        # We assume timeframe matches if we had it in filename, but now it's in folder name
        # We should filter by timeframe folder too ideally.
        
        # Matches: data/binance/1h/BTC_USDT.parquet
        found_files = list(DATA_DIR.rglob(f"*/{timeframe}/{safe_symbol}.parquet"))
        
        if not found_files:
            # Fallback for old flat structure if any
            found_files = list(DATA_DIR.glob(f"*{safe_symbol}*{timeframe}.parquet"))
            
        if not found_files:
            print(f"Warning: File not found for {symbol} (tf={timeframe})")
            continue
            
        # Pick the first match
        filename = found_files[0]
        
        df = pd.read_parquet(filename)
        # Ensure timestamp is index
        if 'timestamp' in df.columns:
            df.set_index('timestamp', inplace=True)
            
        data[symbol] = df.sort_index()
        print(f"Loaded {symbol} from {filename}: {len(df)} rows")
        
    return data

def get_aligned_close_prices(symbols: list[str], timeframe: str = '1h') -> pd.DataFrame:
    """
    Returns a single DataFrame with 'close' prices for all symbols, aligned by timestamp.
    Useful for simple vector calculations.
    """
    data_dict = load_data(symbols, timeframe)
    
    # Extract 'close' columns
    close_prices = {}
    for sym, df in data_dict.items():
        if 'close' in df.columns:
            close_prices[sym] = df['close']
            
    # Combine into one DF (outer join to keep all timestamps, or inner to keep overlapping)
    # Inner join is safer for pairs trading to ensure both exist
    aligned_df = pd.DataFrame(close_prices).dropna() 
    
    return aligned_df

if __name__ == "__main__":
    # Smoke test
    df = get_aligned_close_prices(['BTC/USDT', 'ETH/USDT'])
    print("\nAligned Close Prices Head:")
    print(df.head())
    print("\nShape:", df.shape)
