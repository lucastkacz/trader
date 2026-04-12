import os
import json
import numpy as np
import pandas as pd
from datetime import datetime, timezone

from src.core.logger import logger
from src.data.storage.local_parquet import ParquetStorage
from src.screener.filters.data_maturity import DataMaturityFilter
from src.screener.clustering.returns_matrix import MatrixBuilder
from src.screener.clustering.graph_louvain import LouvainTaxonomist
from src.engine.analysis.cointegration import CointegrationEngine

def discover_alpha():
    logger.info("Initializing Epoch 1 Phase 3 & 4 Orchestrator...")
    
    storage = ParquetStorage()
    base_path = "data/parquet/binanceusdm/4h"
    
    if not os.path.exists(base_path):
        logger.error(f"Cannot find populated parquet directory at {base_path}")
        return
        
    files = [f for f in os.listdir(base_path) if f.endswith(".parquet")]
    logger.info(f"Detected {len(files)} historical datasets.")
    
    # 1. Ingestion
    pool = {}
    volumes = {}
    for f in files:
        symbol = f.replace(".parquet", "").replace("_", "/")
        
        # Omit USDC denominated pairs inherently
        if "USDC" in symbol:
            continue
            
        try:
            df = storage.load_ohlcv(symbol, "4h", exchange="binanceusdm")
            
            # CRITICAL FIX: Align dates
            df.set_index("timestamp", inplace=True)
            
            # Dollar volume proxy on the most recent 30 days (180 bars)
            recent_df = df.iloc[-180:]
            dollar_vol = (recent_df["volume"] * recent_df["close"]).mean()
            volumes[symbol] = dollar_vol
            
            pool[symbol] = df
        except Exception as e:
            logger.warning(f"Failed loading {symbol}: {e}")
            
    # Dynamic Slicing: Drop Top 5 Mega-Caps completely from the universe.
    sorted_cap = sorted(volumes.keys(), key=lambda k: volumes[k], reverse=True)
    mega_caps = sorted_cap[:5]
    logger.warning(f"Omitting Tier-1 Mega-Caps computationally: {mega_caps}")
    for cap in mega_caps:
        if cap in pool:
            del pool[cap]
            
    logger.info(f"Loaded {len(pool)} assets into RAM memory safely.")
    
    # 2. Maturity Sieve (4H timeframe means 180 Days * 6 Candles = 1080 Bars)
    sieve = DataMaturityFilter(min_days=1080)
    surviving_symbols = sieve.filter(pool)
    
    mature_pool = {sym: pool[sym] for sym in surviving_symbols}
    
    # 3. Matrix Transformation
    builder = MatrixBuilder(clip_percentile=0.01)
    returns_matrix = builder.build(mature_pool)
    
    # 4. Louvain Clustering
    taxonomist = LouvainTaxonomist(correlation_threshold=0.5)
    clusters = taxonomist.clusterize(returns_matrix)
    
    # Export the Taxonomist state
    os.makedirs("data/universes", exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    cluster_path = f"data/universes/clusters_{timestamp}.json"
    with open(cluster_path, "w") as f:
        json.dump(clusters, f, indent=4)
        
    logger.info(f"Phase 3 Complete. Clusters exported to {cluster_path}")
    
    # 5. Cointegration Edge Processing
    logger.info("Entering Phase 4: Cointegration Alpha Core Generation...")
    # Max Half-Life of 14 Days on a 4H Timeframe = 14 * 6 = 84 Bars
    cointegration_engine = CointegrationEngine(p_value_threshold=0.05, max_half_life=84.0)
    
    final_pairs = []
    
    for cohort_name, members in clusters.items():
        logger.debug(f"Evaluating {cohort_name} ({len(members)} assets)...")
        for i in range(len(members)):
            for j in range(i+1, len(members)):
                asset_x = members[i]
                asset_y = members[j]
                
                # Alpha core rule: Pass purely logarithmic prices, do not pass winsorized data.
                series_x = np.log(mature_pool[asset_x]["close"])
                series_y = np.log(mature_pool[asset_y]["close"])
                
                df_pair = pd.concat([series_x, series_y], axis=1).dropna()
                if len(df_pair) < 500:
                    continue 
                    
                result = cointegration_engine.evaluate(df_pair.iloc[:, 0], df_pair.iloc[:, 1])
                
                if result["is_cointegrated"]:
                    final_pairs.append({
                        "Cohort": cohort_name,
                        "Asset_X": asset_x,
                        "Asset_Y": asset_y,
                        "P_Value": result["p_value"],
                        "Hedge_Ratio": result["hedge_ratio"],
                        "Half_Life": result["half_life"]
                    })
                    
    logger.info(f"Phase 4 Alpha Core yielded {len(final_pairs)} pristine pairs out of thousands of combinations.")
    
    with open("data/universes/pairs.json", "w") as f:
        json.dump(final_pairs, f, indent=4)
        
    logger.info("Epoch 1 Pipeline Orchestration complete. Written to pairs.json.")

if __name__ == "__main__":
    discover_alpha()
