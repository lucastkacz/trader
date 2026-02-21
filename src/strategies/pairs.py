import pandas as pd
from typing import Dict, Tuple, Optional
from src.engine.data.loader import DataLoader
from src.stats.cointegration import test_cointegration, calculate_spread
from src.stats.zscore import calculate_z_score, generate_signals

class PairsTradingStrategy:
    """
    Production Strategy Class for Pairs Trading.
    Responsible for:
    1. Finding cointegrated pairs from a universe.
    2. Generating entry/exit signals based on Z-Scores.
    3. Outputting a `target_weights` DataFrame expected by VectorizedEngine.
    """
    
    def __init__(
        self, 
        timeframe: str = '1h',
        cointegration_p_value_threshold: float = 0.05,
        zscore_window: int = 30,
        entry_threshold: float = 2.0,
        exit_threshold: float = 0.0,
        capital_per_pair: float = 0.1 # Allocate 10% of portfolio max per pair
    ):
        self.timeframe = timeframe
        self.coint_threshold = cointegration_p_value_threshold
        self.zscore_window = zscore_window
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.capital_per_pair = capital_per_pair
        
        self.active_pairs: Dict[Tuple[str, str], float] = {} # (asset_a, asset_b) -> hedge_ratio
        
    def train(self, prices: pd.DataFrame) -> None:
        """
        Phase 1: Research/Training.
        Given historical prices, find pairs that are cointegrated.
        (In a real production system, this could be run rolling every week).
        """
        # Simplistic approach: just check all combinations (slow for large universes)
        # Ideally, this receives pre-filtered correlated pairs.
        symbols = prices.columns
        found = 0
        
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                asset_a = symbols[i]
                asset_b = symbols[j]
                
                # Need enough history without NaNs
                df_pair = prices[[asset_a, asset_b]].dropna()
                if len(df_pair) < self.zscore_window + 10:
                    continue
                    
                beta, _, p_value = test_cointegration(df_pair[asset_a], df_pair[asset_b])
                
                if p_value < self.coint_threshold:
                    self.active_pairs[(asset_a, asset_b)] = beta
                    found += 1
                    
        print(f"PairsStrategy Train complete. Found {found} cointegrated pairs.")

    def generate_target_weights(self, prices: pd.DataFrame) -> pd.DataFrame:
        """
        Phase 2: Execution.
        Given continuous prices and our trained pairs, generate portfolio weights.
        """
        if not self.active_pairs:
            print("Warning: No active pairs found. Did you run train()?")
            return pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
            
        # Initialize an empty target weight matrix
        weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
        
        for (asset_a, asset_b), beta in self.active_pairs.items():
            # 1. Calc Spread
            df_pair = prices[[asset_a, asset_b]].ffill()
            spread = calculate_spread(df_pair[asset_a], df_pair[asset_b], beta)
            
            # 2. Calc Z-Score
            z_score = calculate_z_score(spread, window=self.zscore_window)
            
            # 3. Generate Signals (-1, 0, 1) per pair
            signals_df = generate_signals(
                z_score, 
                entry_threshold=self.entry_threshold, 
                exit_threshold=self.exit_threshold
            )
            positions = signals_df['position'] # 1 means long spread (buy A, sell B), -1 means short spread.
            
            # 4. Convert Signals to Portfolio Weights
            # If position is 1 (Long Spread):
            # We want to Buy A, Sell B.
            # We allocate self.capital_per_pair.
            # Standard weight math: 
            # w_A = capital * 1.0 (long)
            # w_B = capital * -beta (short, sized by hedge ratio)
            
            # To be precise on capital allocation: total gross exposure should be `capital_per_pair`
            # For simplicity let's assume `capital_per_pair` represents exposure to the primary leg (A).
            
            # For every bar where position is non-zero:
            # Add to the global weights matrix
            weights[asset_a] += positions * self.capital_per_pair
            weights[asset_b] += positions * (-beta * self.capital_per_pair)
            
        return weights
