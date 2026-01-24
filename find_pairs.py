import pandas as pd
from pathlib import Path
from datetime import datetime, timezone, timedelta
import sys

# Ensure local library is in path
sys.path.append(str(Path.cwd()))

from lib.data import run_fetch, get_top_pairs, MarketDataDB
from lib.analysis import (
    calculate_correlation_matrix, 
    get_highly_correlated_pairs,
    find_cointegrated_pairs,
    filter_tradable_pairs,
    calculate_rolling_stats,
    calculate_zscore,
    get_trade_signals
)
from lib.analysis.cointegration import calculate_rolling_hedge_ratio
from lib.backtest import BacktestEngine, calculate_backtest_stats
from lib.plots import plot_unified_dashboard
from lib.utils.logger import setup_logger

logger = setup_logger("pair_finder")

# --- CONFIGURATION ---
CONFIG = {
    "data": {
        "exchange": "bybit",
        "timeframe": "1h",
        "fetch_lookback": 60,       
        "scan_lookback": 14,        
        "top_n_assets": 50,
        "storage_path": "market_data" 
    },
    "filters": {
        "correlation": {
            "threshold": 0.70,      # Lowered to capture hidden gems
            "method": "pearson"
        },
        "cointegration": {
            "p_value_threshold": 0.05
        },
        "statistics": {
            "max_half_life": 48.0,
            "max_hurst": 0.6
        }
    },
    "trading": {
        "z_score_window_halflife_multiplier": 2.0,
        "entry_threshold": 2.0,
        "exit_threshold": 0.0,
        "stop_loss": 4.0
    },
    "backtest": {
        "initial_capital": 10000, 
        "fee_rate": 0.0005,       
        "slippage": 0.0005,       
        "leverage": 5.0
    }
}

def main():
    logger.info("Starting Pair Selection Funnel...")
    
    # 1. Setup Dates
    end_date = datetime.now(timezone.utc)
    fetch_start_date = end_date - timedelta(days=CONFIG['data']['fetch_lookback'])
    scan_start_date = end_date - timedelta(days=CONFIG['data']['scan_lookback'])
    
    str_fetch_start = fetch_start_date.strftime('%Y-%m-%d')
    str_scan_start = scan_start_date.strftime('%Y-%m-%d')
    str_end = end_date.strftime('%Y-%m-%d')
    
    logger.info(f"Context Period: {str_fetch_start} to {str_end} ({CONFIG['data']['fetch_lookback']} days)")
    logger.info(f"Scanning Period: {str_scan_start} to {str_end} ({CONFIG['data']['scan_lookback']} days)")

    # ---------------------------------------------------------
    # 2. DATA ACQUISITION
    # ---------------------------------------------------------
    # Get Universe
    top_pairs_df = get_top_pairs(
        exchange_id=CONFIG['data']['exchange'], 
        limit=CONFIG['data']['top_n_assets'],
        unique_base=True
    )
    if top_pairs_df.empty: return

    symbols = top_pairs_df['symbol'].tolist()
    
    # Fetch FULL history (60 days)
    run_fetch(
        symbols=symbols,
        start_date=str_fetch_start,
        end_date=str_end,
        db_path=CONFIG['data']['storage_path'],
        timeframe=CONFIG['data']['timeframe'],
        exchange_id=CONFIG['data']['exchange']
    )

    db = MarketDataDB(CONFIG['data']['storage_path'])

    # ---------------------------------------------------------
    # 3. SCANNER (Last 14 Days)
    # ---------------------------------------------------------
    logger.info(">>> Phase 1: Scanning Recent Market Data...")
    
    # Calculate Matrix on SCAN window
    corr_matrix = calculate_correlation_matrix(
        db=db,
        exchange=CONFIG['data']['exchange'],
        timeframe=CONFIG['data']['timeframe'],
        symbols=symbols,
        start_date=str_scan_start, 
        end_date=str_end,
        method=CONFIG['filters']['correlation']['method']
    )
    
    correlated_pairs = get_highly_correlated_pairs(corr_matrix, threshold=CONFIG['filters']['correlation']['threshold'])
    logger.info(f"-> Candidates (Corr > {CONFIG['filters']['correlation']['threshold']}): {len(correlated_pairs)}")

    if not correlated_pairs:
        logger.warning("No pairs found in scan window.")
        db.close()
        return

    # Check Cointegration on SCAN window
    price_df_scan = db.get_close_prices_pivot(
        CONFIG['data']['exchange'], CONFIG['data']['timeframe'], symbols, str_scan_start, str_end
    )
    
    cointegrated_pairs = find_cointegrated_pairs(
        price_matrix=price_df_scan, 
        candidates=correlated_pairs, 
        p_value_threshold=CONFIG['filters']['cointegration']['p_value_threshold']
    )
    
    # Statistical Filter
    final_pairs = filter_tradable_pairs(
        cointegrated_pairs, 
        max_half_life=CONFIG['filters']['statistics']['max_half_life'],
        max_hurst=CONFIG['filters']['statistics']['max_hurst']
    )

    if not final_pairs:
        logger.warning("No tradable pairs found in current window.")
        db.close()
        return

    # ---------------------------------------------------------
    # 4. RESULTS
    # ---------------------------------------------------------
    print("\n" + "="*60)
    print(f"CURRENT TRADABLE PAIRS (Last {CONFIG['data']['scan_lookback']} Days)")
    print("="*60)
    
    df_results = pd.DataFrame(final_pairs)
    cols = ['symbol_a', 'symbol_b', 'correlation', 'p_value', 'half_life', 'hurst_exponent', 'hedge_ratio']
    df_results = df_results[cols].sort_values(by='p_value', ascending=True)
    
    pd.set_option('display.max_rows', None)
    pd.set_option('display.width', 1000)
    pd.set_option('display.float_format', '{:.4f}'.format)
    print(df_results)
    print("="*60)
    
    df_results.to_csv("tradable_pairs.csv", index=False)

    # ---------------------------------------------------------
    # 5. DEEP DIVE & BACKTEST
    # ---------------------------------------------------------
    logger.info(">>> Phase 2: Historical Validation, Signals & Backtest...")
    
    # Rolling Window parameters
    window_hours = CONFIG['data']['scan_lookback'] * 24
    
    for pair in final_pairs:
        s1 = pair['symbol_a']
        s2 = pair['symbol_b']
        half_life = pair['half_life']
        
        logger.info(f"Analyzing: {s1} vs {s2}")
        
        # Load FULL history (60 days)
        df1 = db.load_ohlcv(s1, CONFIG['data']['exchange'], CONFIG['data']['timeframe'])
        df2 = db.load_ohlcv(s2, CONFIG['data']['exchange'], CONFIG['data']['timeframe'])
        
        if df1.empty or df2.empty:
            continue
        
        # Align
        common_idx = df1['timestamp'].isin(df2['timestamp'])
        df1 = df1[common_idx].set_index('timestamp')['close']
        df2 = df2[df2['timestamp'].isin(df1.index)].set_index('timestamp')['close']

        # A. Rolling Stats (Analysis)
        rolling_df = calculate_rolling_stats(
            df1, df2, 
            window_hours=window_hours, 
            step_hours=24
        )
        
        # B. Z-Score Signals (Using Rolling Beta)
        # We calculate rolling beta over the 'window_hours' (14 days)
        rolling_beta_full = calculate_rolling_hedge_ratio(df1, df2, window=window_hours)
        
        # Calculate Spread
        spread_full = df1 - (rolling_beta_full * df2)
        
        # Z-Score
        z_window = int(max(half_life * CONFIG['trading']['z_score_window_halflife_multiplier'], 5))
        z_score_full = calculate_zscore(spread_full, window=z_window)
        
        # Slice for Backtest Period
        scan_start_ts = pd.Timestamp(scan_start_date).replace(tzinfo=None)
        z_score_scan = z_score_full[z_score_full.index >= scan_start_ts]
        
        if z_score_scan.empty: continue
            
        longs, shorts, exits = get_trade_signals(
            z_score_scan,
            entry_threshold=CONFIG['trading']['entry_threshold'],
            exit_threshold=CONFIG['trading']['exit_threshold'],
            stop_loss=CONFIG['trading']['stop_loss']
        )
        
        # C. Backtest
        df1_scan = df1[df1.index >= scan_start_ts]
        df2_scan = df2[df2.index >= scan_start_ts]
        rolling_beta_scan = rolling_beta_full[rolling_beta_full.index >= scan_start_ts]
        
        engine = BacktestEngine(
            initial_capital=CONFIG['backtest']['initial_capital'],
            fee_rate=CONFIG['backtest']['fee_rate'],
            slippage=CONFIG['backtest']['slippage'],
            leverage=CONFIG['backtest']['leverage']
        )
        
        # Pass Rolling Beta to Engine
        equity_df, trades, total_fees = engine.run(
            df1_scan, df2_scan, z_score_scan, 
            rolling_beta_scan,
            entry_threshold=CONFIG['trading']['entry_threshold'],
            exit_threshold=CONFIG['trading']['exit_threshold'],
            stop_loss=CONFIG['trading']['stop_loss'],
            symbol_a_name=s1,
            symbol_b_name=s2
        )
        
        if not equity_df.empty:
            stats = calculate_backtest_stats(
                equity_df['equity'], 
                trades,
                total_fees,
                CONFIG['backtest']['initial_capital']
            )
            
            # PLOT UNIFIED DASHBOARD
            plot_unified_dashboard(
                s1, s2,
                rolling_df,
                z_score_scan,
                longs, shorts, exits,
                equity_df,
                stats,
                trades,
                half_life,
                CONFIG['backtest']['initial_capital'],
                z_thresholds={
                    'entry': CONFIG['trading']['entry_threshold']
                }
            )
            
            logger.info(f"Backtest Return: {stats.get('Total Return', '0%')}")

    db.close()

if __name__ == "__main__":
    main()