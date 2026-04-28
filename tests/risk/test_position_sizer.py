import pytest
import numpy as np

from src.engine.trader.config import load_risk_config

try:
    from src.risk.position_sizer import VaultSizer, RiskLimitExceeded
except ImportError:
    pass

def test_vault_sizer_requires_explicit_risk_limits():
    with pytest.raises(TypeError):
        VaultSizer()

def test_volatility_risk_parity():
    """
    Simulates a total bankroll of $10,000.
    Asset A moves 1% daily. Asset B moves 5% daily.
    The test asserts Vault assigns mathematically larger USD
    allocation to Asset A to match Notional Volatility.
    """
    total_capital = 10000.0
    
    # Passing raw standard deviations (e.g. log returns std)
    vol_a = 0.01  # 1% standard deviation
    vol_b = 0.05  # 5% standard deviation
    
    risk_cfg = load_risk_config("configs/risk/alpha_v1.yml")
    vault = VaultSizer(
        max_cluster_exposure=risk_cfg.max_cluster_exposure,
        max_leverage=risk_cfg.max_leverage,
    )
    
    # We allocate to the Pair (Cluster limit is 10% of 10,000 = $1,000 Exposure Total)
    alloc_a, alloc_b = vault.calculate_parity(total_capital, vol_a, vol_b)
    
    # 1. Parity constraint: vol_a * alloc_a == vol_b * alloc_b 
    # (i.e. Risk dollars are identical)
    risk_a = alloc_a * vol_a
    risk_b = alloc_b * vol_b
    assert np.isclose(risk_a, risk_b, rtol=1e-5)
    
    # 2. Exposure constraint: alloc_a + alloc_b must equal EXACTLY $1,000 (10%)
    assert np.isclose(alloc_a + alloc_b, 1000.0, rtol=1e-5)
    
    # 3. Asset A should have 5x more capital than Asset B
    assert alloc_a > alloc_b
    assert np.isclose(alloc_a / alloc_b, 5.0, rtol=1e-5)

def test_leverage_limit_violation():
    """
    Simulates incredibly small volatilities causing the model to attempt
    infinitely leveraged positions to maintain arbitrary exposure. 
    Asserts the Vault safely raises the RiskLimitExceeded kill-switch.
    """
    total_capital = 10000.0
    
    # E.g. two stablecoins tethered hard, volatility effectively zeroes
    vol_a = 0.000001
    vol_b = 0.000001
    
    # Even though it wants to deploy $1,000 (10%), if those 1,000 dollars
    # theoretically need 100x leverage on Binance to yield expected return parity...
    # Wait, the leverage here is dictated by the absolute minimum dollar tick sizing 
    # OR if the user-defined sizing targets fixed dollar risk.
    # In our Vault, we cap Notional Leverage defined as (PositionSize / IsolatedMargin).
    
    risk_cfg = load_risk_config("configs/risk/alpha_v1.yml")
    vault = VaultSizer(
        max_cluster_exposure=risk_cfg.max_cluster_exposure,
        max_leverage=risk_cfg.max_leverage,
    )
    
    # Mocking a scenario where to achieve the $100 Target Risk, 
    # it requires $10,000,000 in notional position.
    target_risk_dollars = 100.0 
    
    with pytest.raises(RiskLimitExceeded, match="Leverage ceiling violated"):
        vault.calculate_sized_by_risk(total_capital, target_risk_dollars, vol_a, vol_b)
