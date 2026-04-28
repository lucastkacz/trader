
class RiskLimitExceeded(Exception):
    """Custom Kill-Switch Exception for when architectural constraints are broken."""
    pass

class VaultSizer:
    """
    Portfolio Allocation and Margin Limits rule engine.
    Ensures that mathematical targets never cross operational exchange limits.
    """
    def __init__(self, max_cluster_exposure: float, max_leverage: float):
        self.max_cluster_exposure = max_cluster_exposure
        self.max_leverage = max_leverage
        
    def calculate_parity(self, total_capital: float, vol_a: float, vol_b: float) -> tuple[float, float]:
        """
        Derives Volatility Risk Parity sizing.
        Capitally punishes volatile assets and rewards stable assets to 
        prevent single-asset Beta dominance in the spread portfolio.
        """
        # Hard Cap on absolute dollar exposure to this pair
        deployable_capital = total_capital * self.max_cluster_exposure
        
        # Inverse Volatility Weighting
        inv_vol_a = 1.0 / vol_a
        inv_vol_b = 1.0 / vol_b
        
        sum_inv_vol = inv_vol_a + inv_vol_b
        
        weight_a = inv_vol_a / sum_inv_vol
        weight_b = inv_vol_b / sum_inv_vol
        
        alloc_a = deployable_capital * weight_a
        alloc_b = deployable_capital * weight_b
        
        return alloc_a, alloc_b

    def calculate_sized_by_risk(self, total_capital: float, target_risk_dollars: float, vol_a: float, vol_b: float):
        """
        Determines the explicit lot sizes required to hit a specific dollar risk target.
        Enforces maximum leverage safety limits.
        """
        alloc_a, alloc_b = self.calculate_parity(total_capital, vol_a, vol_b)
        
        # Calculate expected dollar variance per asset size
        # Expected swing = Allocation * Daily Volatility
        expected_swing_a = alloc_a * vol_a
        
        # If the expected swing required to hit target_risk requires 
        # multiplying our allocation drastically, we monitor the leverage factor.
        leverage_required = target_risk_dollars / expected_swing_a
        
        if leverage_required > self.max_leverage:
            # We explicitly abort if mathematically required sizes hit Binance's Isolated ceilings
            raise RiskLimitExceeded(f"Leverage ceiling violated. Demanded: {leverage_required:.2f}x, Max: {self.max_leverage}x")
            
        return alloc_a * leverage_required, alloc_b * leverage_required
