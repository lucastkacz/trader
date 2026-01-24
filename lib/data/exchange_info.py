import ccxt
import pandas as pd
from typing import Optional
from lib.utils.logger import setup_logger

logger = setup_logger(__name__)

def get_top_pairs(exchange_id: str = 'binance', limit: int = 20, unique_base: bool = True) -> pd.DataFrame:
    """
    Fetches available pairs from the specified exchange, sorted by 24h quote volume.
    
    Args:
        exchange_id: The CCXT exchange ID (e.g., 'binance', 'binanceusdm', 'binancecoinm').
        limit: Number of top pairs to return. None for all.
        unique_base: If True, returns only the highest volume pair for each base asset (e.g. BTC/USDT vs BTC/BUSD).
        
    Returns:
        pd.DataFrame: DataFrame containing symbol, volume (quote), and close price.
    """
    try:
        exchange_class = getattr(ccxt, exchange_id)
    except AttributeError:
        logger.error(f"Exchange '{exchange_id}' not found in ccxt.")
        return pd.DataFrame()

    # Initialize exchange
    exchange = exchange_class({'enableRateLimit': True})
    
    # Specific handling for generic 'binance' to default to futures if implied, 
    # but usually specific IDs like 'binanceusdm' are preferred for futures.
    # If the user passes 'binance', it defaults to Spot in CCXT unless options are set.
    # Given the context of 'quant strategy', futures are likely, but let's trust the exchange_id passed.
    
    logger.info(f"Fetching tickers for {exchange_id}...")
    
    try:
        # load_markets is often required before fetching tickers to ensure all symbols are known
        exchange.load_markets()
        tickers = exchange.fetch_tickers()
    except Exception as e:
        logger.error(f"Error fetching tickers from {exchange_id}: {e}")
        return pd.DataFrame()

    data = []
    for symbol, ticker in tickers.items():
        # filtering out pairs with no volume to avoid noise
        quote_vol = ticker.get('quoteVolume')
        if quote_vol is None:
            quote_vol = 0.0
            
        data.append({
            'symbol': symbol,
            'volume': quote_vol,
            'close': ticker.get('close', 0.0),
            'percentage': ticker.get('percentage', 0.0)
        })
    
    df = pd.DataFrame(data)
    
    if not df.empty:
        # Sort by volume descending
        df = df.sort_values(by='volume', ascending=False).reset_index(drop=True)
        
        if unique_base:
            # Extract base currency (e.g., "BTC" from "BTC/USDT:USDT")
            # CCXT symbols are usually "BASE/QUOTE" or "BASE/QUOTE:SETTLE"
            df['base'] = df['symbol'].apply(lambda x: x.split('/')[0])
            
            # Drop duplicates keeping the first (highest volume)
            df = df.drop_duplicates(subset='base', keep='first')
            
            # Clean up temporary column
            df = df.drop(columns=['base'])
            
            logger.info("Filtered duplicates to keep unique base assets.")
        
        # Format volume for readability (optional, but keeps data clean in DF)
        # We keep raw numbers for calculation, formatting can happen at display time.
        
        if limit:
            df = df.head(limit)
            
    logger.info(f"Retrieved top {len(df)} pairs by volume from {exchange_id}")
    return df
