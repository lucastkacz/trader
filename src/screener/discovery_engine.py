"""Research discovery workflow for candidate pair artifacts."""

from pathlib import Path

from src.core.logger import logger
from src.data.storage.local_parquet import ParquetStorage
from src.engine.trader.config import StrategyConfig, UniverseConfig
from src.engine.trader.runtime.artifacts import write_candidate_pair_artifact
from src.screener.discovery_clusters import build_clusters, write_cluster_artifact
from src.screener.discovery_pairs import discover_cointegrated_pairs
from src.screener.discovery_universe import load_filtered_symbol_pool


class DiscoveryEngine:
    """Run universe filtering, clustering, and cointegration discovery."""

    def __init__(self, storage: ParquetStorage):
        self.storage = storage

    def run(
        self,
        timeframe: str,
        exchange: str,
        universe_cfg: UniverseConfig,
        strategy_cfg: StrategyConfig,
        artifact_base_dir: str | Path,
    ) -> bool:
        logger.info("Initializing candidate pair discovery workflow.")

        mature_pool = load_filtered_symbol_pool(
            storage=self.storage,
            timeframe=timeframe,
            exchange=exchange,
            universe_cfg=universe_cfg,
        )
        if mature_pool is None:
            return False

        clusters = build_clusters(mature_pool, universe_cfg)
        write_cluster_artifact(clusters, timeframe, artifact_base_dir)
        final_pairs = discover_cointegrated_pairs(
            mature_pool=mature_pool,
            clusters=clusters,
            universe_cfg=universe_cfg,
            strategy_cfg=strategy_cfg,
        )
        candidate_path = write_candidate_pair_artifact(
            pair_rows=final_pairs,
            timeframe=timeframe,
            exchange=exchange,
            base_dir=artifact_base_dir,
        )

        logger.info(f"Candidate pair discovery wrote artifact: {candidate_path}")
        return True
