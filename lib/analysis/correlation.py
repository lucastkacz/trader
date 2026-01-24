import pandas as pd
import numpy as np
from typing import List, Tuple
from lib.data.storage import MarketDataDB
from lib.utils.logger import setup_logger

logger = setup_logger(__name__)

def calculate_log_returns(price_matrix: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates the log returns of the price matrix.
    Log Returns = ln(P_t / P_{t-1})
    """
    if price_matrix.empty:
        return pd.DataFrame()
        
    # Use numpy for log calculation
    log_prices = np.log(price_matrix)
    
    # Calculate difference
    log_returns = log_prices.diff()
    
    # Drop the first row which is now NaN
    return log_returns.dropna()

def calculate_correlation_matrix(
    db: MarketDataDB,
    exchange: str,
    timeframe: str,
    symbols: List[str],
    start_date: str,
    end_date: str,
    method: str = 'pearson'
) -> pd.DataFrame:
    """
    Calculates the correlation matrix of LOG RETURNS for the given assets.
    
    Args:
        db: MarketDataDB instance.
        exchange: Exchange ID.
        timeframe: Timeframe (e.g., '1h').
        symbols: List of symbols to analyze.
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).
        method: Correlation method ('pearson', 'kendall', 'spearman').
        
    Returns:
        pd.DataFrame: Correlation matrix (N x N).
    """
    logger.info(f"Calculating {method} correlation for {len(symbols)} symbols ({start_date} to {end_date})...")
    
    # 1. Fetch Pivot Data (Aligned Close Prices)
    price_matrix = db.get_close_prices_pivot(exchange, timeframe, symbols, start_date, end_date)
    
    if price_matrix.empty:
        logger.error("No data found for the requested criteria. Returning empty matrix.")
        return pd.DataFrame()
    
    # 2. Data Validation (Strict Mode)
    # The pivot table contains the UNION of all timestamps found across all files.
    # If Asset A has data at T1 and Asset B does not, Asset B will be NaN at T1.
    
    # Check for columns that are entirely NaN first
    price_matrix = price_matrix.dropna(axis=1, how='all')
    
    # Strict Quality Control: Drop assets with ANY gaps relative to the union of data
    total_rows = len(price_matrix)
    clean_symbols = []
    
    for symbol in price_matrix.columns:
        # Count missing rows for this symbol
        missing_count = price_matrix[symbol].isna().sum()
        
        if missing_count > 0:
            pct_missing = (missing_count / total_rows) * 100
            logger.warning(f"Dropping {symbol}: Missing {missing_count} rows ({pct_missing:.2f}%) relative to group.")
        else:
            clean_symbols.append(symbol)
            
    if not clean_symbols:
        logger.error("No symbols passed the strict data quality check (all had at least one gap).")
        return pd.DataFrame()
        
    if len(clean_symbols) < 2:
        logger.warning(f"Insufficient clean symbols left: {clean_symbols}")
        return pd.DataFrame()

    # Filter to only clean symbols
    price_matrix_clean = price_matrix[clean_symbols]

    # 3. Calculate Log Returns
    # Since we ensured no NaNs exist in the price data, we can safely calculate returns.
    # The first row will be NaN (diff), which we drop.
    returns = calculate_log_returns(price_matrix_clean)
    
    if returns.empty:
        logger.error("Returns calculation resulted in empty DataFrame.")
        return pd.DataFrame()

    # 4. Correlation
    # min_periods=24 is still good practice, though strictly our data is now dense.
    corr_matrix = returns.corr(method=method, min_periods=24)
    
    logger.info(f"Correlation matrix calculated for {len(corr_matrix)} clean symbols.")
    return corr_matrix

def get_highly_correlated_pairs(corr_matrix: pd.DataFrame, threshold: float = 0.9) -> List[Tuple[str, str, float]]:
    """
    Extracts pairs with correlation above a certain threshold.
    Excludes self-correlation (diagonal) and duplicates (A-B vs B-A).
    """
    if corr_matrix.empty:
        return []
        
    # Create a mask to ignore the diagonal and the lower triangle (to avoid duplicates)
    mask = np.triu(np.ones(corr_matrix.shape), k=1).astype(bool)
    
    # Apply mask
    upper_triangle = corr_matrix.where(mask)
    
    # Stack to get a Series of (Symbol A, Symbol B) -> Correlation
    pairs = upper_triangle.stack()
    
    # Filter by threshold
    high_corr_pairs = pairs[pairs > threshold]
    
    # Convert to list of tuples: [(SymA, SymB, Corr), ...]
    result = []
    for (sym_a, sym_b), corr in high_corr_pairs.items():
        result.append((sym_a, sym_b, float(corr)))
        
    # Sort by correlation descending
    result.sort(key=lambda x: x[2], reverse=True)
    
    return result
