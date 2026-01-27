import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")

def load_data(symbols: list[str], timeframe: str = '1h') -> dict[str, pd.DataFrame]:
    """
    Loads Parquet data for multiple symbols.
    Returns a dictionary of {symbol: dataframe}.
    Ensures all dataframes have datetime index.
    """
    data = {}
    for symbol in symbols:
        safe_symbol = symbol.replace('/', '_')
        filename = DATA_DIR / f"{safe_symbol}_{timeframe}.parquet"
        
        if not filename.exists():
            print(f"Warning: File not found for {symbol} at {filename}")
            continue
            
        df = pd.read_parquet(filename)
        # Ensure timestamp is index
        if 'timestamp' in df.columns:
            df.set_index('timestamp', inplace=True)
            
        data[symbol] = df.sort_index()
        print(f"Loaded {symbol}: {len(df)} rows")
        
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
