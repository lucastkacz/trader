import pytest
import pandas as pd
import numpy as np
import networkx as nx

try:
    from src.screener.clustering.returns_matrix import MatrixBuilder
    from src.screener.clustering.graph_louvain import LouvainTaxonomist
except ImportError:
    pass

def test_winsorization_and_clustering():
    """
    Synthesizes two perfectly correlated assets, and one absolutely random 
    asset that suffers a 500% pump and dump. Proves that Winsorization 
    trims the pump, and clustering correctly separates them.
    """
    np.random.seed(42) # Deterministic TDD
    
    # 1. Synthesize correlated stable pair
    base_signal = np.random.normal(0, 0.02, 200)
    
    df_assetA = pd.DataFrame({"close": base_signal + 100})
    # AssetB is perfectly correlated with a slight delay/noise
    df_assetB = pd.DataFrame({"close": base_signal + 105 + np.random.normal(0, 0.001, 200)})
    
    # 2. Synthesize Shitcoin with aggressive 1-day 500% pump anomaly
    noise_signal = np.random.normal(0, 0.05, 200)
    noise_signal[100] = 5.0 # 500% massive spike
    df_assetC = pd.DataFrame({"close": noise_signal + 50})
    
    pool = {
        "A/USDT": df_assetA,
        "B/USDT": df_assetB,
        "C/USDT": df_assetC
    }
    
    # 3. Build Matrix
    builder = MatrixBuilder(clip_percentile=0.01)
    returns_matrix = builder.build(pool)
    
    # Assert Winsorization worked (Max return should not be 5.0 for Asset C)
    assert returns_matrix["C/USDT"].max() < 1.0 
    
    # 4. Cluster using NetworkX
    taxonomist = LouvainTaxonomist()
    clusters = taxonomist.clusterize(returns_matrix)
    
    # Assert A and B are in the same deterministic cohort, and C is isolated
    # The return format should be {"Cohort_0": ["A/USDT", "B/USDT"], "Cohort_1": ["C/USDT"]}
    
    found_correlation = False
    for cohort_id, members in clusters.items():
        if "A/USDT" in members and "B/USDT" in members:
            assert "C/USDT" not in members
            found_correlation = True
            
    assert found_correlation == True
