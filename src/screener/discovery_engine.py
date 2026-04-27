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

class DiscoveryEngine:
    def __init__(self, storage: ParquetStorage):
        self.storage = storage

    def run(self, timeframe: str, exchange: str, universe_cfg: dict, strategy_cfg: dict):
        logger.info("Initializing Epoch 1 Phase 3 & 4 Discovery Engine...")
        
        filters_cfg = universe_cfg["filters"]
        exclude_mega_caps = filters_cfg["exclude_top_n_mega_caps"]
        recent_vol_bars = filters_cfg["volume_lookback_bars"]
        min_volume = filters_cfg["min_volume_liquidity"]
        max_volume = filters_cfg["max_volume_liquidity"]
        sieve_bars = filters_cfg["min_data_maturity_bars"]
        
        clustering_cfg = universe_cfg["clustering"]
        returns_clip = clustering_cfg["returns_clip_percentile"]
        louvain_thresh = clustering_cfg["louvain_correlation_threshold"]
        
        coint_cfg = universe_cfg["cointegration"]
        p_value_thresh = coint_cfg["p_value_threshold"]
        half_life_max = coint_cfg["max_half_life_bars"]

        base_path = f"data/parquet/{exchange}/{timeframe}"
        
        if not os.path.exists(base_path):
            logger.error(f"Cannot find populated parquet directory at {base_path}")
            return False
            
        files = [f for f in os.listdir(base_path) if f.endswith(".parquet")]
        logger.info(f"Detected {len(files)} historical datasets.")
        
        # 1. Ingestion
        pool = {}
        volumes = {}
        for f in files:
            symbol = f.replace(".parquet", "").replace("_", "/")
            
            if "USDC" in symbol:
                continue
                
            try:
                df = self.storage.load_ohlcv(symbol, timeframe, exchange=exchange)
                df.set_index("timestamp", inplace=True)
                
                recent_df = df.iloc[-recent_vol_bars:]
                dollar_vol = (recent_df["volume"] * recent_df["close"]).mean()
                
                if dollar_vol < min_volume:
                    continue
                    
                if dollar_vol > max_volume:
                    continue
                    
                volumes[symbol] = dollar_vol
                pool[symbol] = df
            except Exception as e:
                logger.warning(f"Failed loading {symbol}: {e}")
                
        sorted_cap = sorted(volumes.keys(), key=lambda k: volumes[k], reverse=True)
        mega_caps = sorted_cap[:exclude_mega_caps]
        logger.warning(f"Omitting Tier-1 Mega-Caps computationally: {mega_caps}")
        for cap in mega_caps:
            if cap in pool:
                del pool[cap]
                
        logger.info(f"Loaded {len(pool)} assets into RAM memory safely.")
        
        # 2. Maturity Sieve
        sieve = DataMaturityFilter(min_days=sieve_bars)
        surviving_symbols = sieve.filter(pool)
        
        mature_pool = {sym: pool[sym] for sym in surviving_symbols}
        
        # 3. Matrix Transformation
        builder = MatrixBuilder(clip_percentile=returns_clip)
        returns_matrix = builder.build(mature_pool)
        
        # 4. Louvain Clustering
        taxonomist = LouvainTaxonomist(correlation_threshold=louvain_thresh)
        clusters = taxonomist.clusterize(returns_matrix)
        
        universe_dir = f"data/universes/{timeframe}"
        os.makedirs(universe_dir, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
        cluster_path = f"{universe_dir}/clusters_{timestamp}.json"
        with open(cluster_path, "w") as f:
            json.dump(clusters, f, indent=4)
            
        logger.info(f"Phase 3 Complete. Clusters exported to {cluster_path}")
        
        # 5. Cointegration Edge Processing
        logger.info("Entering Phase 4: Cointegration Alpha Core Generation...")
        cointegration_engine = CointegrationEngine(p_value_threshold=p_value_thresh, max_half_life=half_life_max)
        
        final_pairs = []
        
        for cohort_name, members in clusters.items():
            logger.debug(f"Evaluating {cohort_name} ({len(members)} assets)...")
            for i in range(len(members)):
                for j in range(i+1, len(members)):
                    asset_x = members[i]
                    asset_y = members[j]
                    
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
                            "Half_Life": result["half_life"],
                            "Best_Params": {
                                "lookback_bars": strategy_cfg["execution"]["ew_ols_lookback_bars"],
                                "entry_z": strategy_cfg["execution"]["entry_z_score"]
                            },
                            "Performance": {
                                "sharpe_ratio": 1.0, 
                                "final_pnl_pct": 0.0
                            }
                        })
                        
        logger.info(f"Phase 4 Alpha Core yielded {len(final_pairs)} pristine pairs out of thousands of combinations.")
        
        with open(f"{universe_dir}/surviving_pairs.json", "w") as f:
            json.dump(final_pairs, f, indent=4)
            
        logger.info(f"Epoch 1 Pipeline Orchestration complete. Written to {universe_dir}/surviving_pairs.json.")
        return True
