import numpy as np
import pandas as pd

from src.engine.trader.config import load_strategy_config, load_universe_config
from src.screener.discovery_pairs import discover_cointegrated_pairs


def test_discovery_rejects_nonpositive_prices_without_crashing():
    rows = 600
    stable_prices = pd.DataFrame({"close": np.linspace(100.0, 105.0, rows)})
    bad_prices = pd.DataFrame({"close": np.zeros(rows)})
    mature_pool = {
        "GOOD/USDT": stable_prices,
        "BAD/USDT": bad_prices,
    }

    pairs = discover_cointegrated_pairs(
        mature_pool=mature_pool,
        clusters={"Cohort_0": ["GOOD/USDT", "BAD/USDT"]},
        universe_cfg=load_universe_config("configs/universe/alpha_v1_dev_1m.yml"),
        strategy_cfg=load_strategy_config("configs/strategy/alpha_v1.yml"),
    )

    assert pairs == []
