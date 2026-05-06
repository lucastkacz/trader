"""Clustering helpers for research discovery."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.core.logger import logger
from src.engine.trader.config import UniverseConfig
from src.screener.clustering.graph_louvain import LouvainTaxonomist
from src.screener.clustering.returns_matrix import MatrixBuilder


def build_clusters(
    mature_pool: dict[str, pd.DataFrame],
    universe_cfg: UniverseConfig,
) -> dict[str, list[str]]:
    clustering_cfg = universe_cfg.clustering
    builder = MatrixBuilder(clip_percentile=clustering_cfg.returns_clip_percentile)
    returns_matrix = builder.build(mature_pool)
    taxonomist = LouvainTaxonomist(
        correlation_threshold=clustering_cfg.louvain_correlation_threshold,
    )
    return taxonomist.clusterize(returns_matrix)


def write_cluster_artifact(
    clusters: dict[str, list[str]],
    timeframe: str,
    artifact_base_dir: str | Path,
) -> Path:
    universe_dir = Path(artifact_base_dir) / timeframe
    universe_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    cluster_path = universe_dir / f"clusters_{timestamp}.json"
    with cluster_path.open("w") as f:
        json.dump(clusters, f, indent=4)
    logger.info(f"Phase 3 Complete. Clusters exported to {cluster_path}")
    return cluster_path
