import pandas as pd
import numpy as np

class FrictionEngine:
    """
    Simulates real-world market bleed.
    Deducts Exchange Fees per turnover, and perpetually drains capital
    via Funding Rates to model the cost of carrying institutional positions.
    """
    def __init__(self, maker_fee: float = 0.0002, taker_fee: float = 0.0006, annual_fund_rate: float = 0.10):
        # Default ~0.06% Taker limits for Binance USD-M
        # Default 10% annualized generic funding drag
        self.taker_fee = taker_fee
        self.maker_fee = maker_fee
        
        # Translated to hourly continuous bleed
        self.hourly_funding_bleed = annual_fund_rate / (365.0 * 24.0)

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        
        # 1. Turnover Detection (Are we opening or closing?)
        # Diff > 0 implies a trade execution. Both legs are executed at once.
        # Since we trade Pairs, turnover happens on Asset A *and* Asset B.
        turnover = out["position"].diff().abs().fillna(0.0)
        
        # Since we use Market / Aggressive Limit orders to guarantee entries (Pessimism),
        # we suffer the Taker fee per leg. Total fee = 2x nominal taker.
        transaction_cost = turnover * (self.taker_fee * 2.0)
        
        # 2. Funding Carry Cost
        # Whenever we are openly exposed out of market neutral cash (abs(position) > 0),
        # we bleed the hourly funding rate approximation.
        carry_cost = out["position"].abs() * self.hourly_funding_bleed
        
        # 3. Netting
        out["net_returns"] = out["gross_returns"] - transaction_cost - carry_cost
        
        return out
