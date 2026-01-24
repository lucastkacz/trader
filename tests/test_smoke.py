import pytest
from statarb.core.config import AppConfig

def test_imports():
    """Verify key modules can be imported."""
    print("Testing imports...")
    from statarb.infra.market_data import fetcher
    from statarb.infra.lakehouse import storage
    from statarb.infra.observability import logger
    print("Imports successful")

def test_config_load_local():
    """Verify local config can be loaded."""
    config = AppConfig.load("local")
    assert config.environment == "local"
    assert "binance" in config.market_data.exchanges
    assert config.risk.max_drawdown_pct == 0.10
