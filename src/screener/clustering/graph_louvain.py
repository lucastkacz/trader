import pandas as pd
import networkx as nx
import community.community_louvain as louvain # python-louvain
from typing import Dict, List
from src.core.logger import logger, LogContext

class LouvainTaxonomist:
    """
    Generates deterministic asset cohorts utilizing NetworkX Graph Theory
    and the Louvain heuristic over a Spearman-Rank correlation space.
    """
    def __init__(self, correlation_threshold: float):
        self.threshold = correlation_threshold
        self.logger_ctx = LogContext(trade_id="SCREENER_LOUVAIN")

    def clusterize(self, returns_matrix: pd.DataFrame) -> Dict[str, List[str]]:
        
        # 1. Spearman Rank Correlation 
        # (Much more robust against crypto non-linear noise than Pearson)
        corr_matrix = returns_matrix.corr(method="spearman")
        
        # 2. NetworkX Graph Topography
        G = nx.Graph()
        
        # Populate nodes
        for node in corr_matrix.columns:
            G.add_node(node)
            
        # Add edges for highly correlated pairs
        for i in range(len(corr_matrix.columns)):
            for j in range(i + 1, len(corr_matrix.columns)):
                asset_a = corr_matrix.columns[i]
                asset_b = corr_matrix.columns[j]
                weight = corr_matrix.iloc[i, j]
                
                # We drop weak or structurally inverse bonds from the community
                if weight > self.threshold:
                    G.add_edge(asset_a, asset_b, weight=weight)
                    
        # 3. Community Detection (Louvain)
        # partition is a dict mapping: { asset: cluster_id }
        partition = louvain.best_partition(G, weight="weight")
        
        # 4. Reverse map to { "Cohort_0": [AssetA, AssetB...] }
        clusters = {}
        for node, cluster_id in partition.items():
            cohort_name = f"Cohort_{cluster_id}"
            if cohort_name not in clusters:
                clusters[cohort_name] = []
            clusters[cohort_name].append(node)
            
        # Clean isolated cohorts (Size < 2 cannot be paired)
        valid_clusters = {k: v for k, v in clusters.items() if len(v) >= 2}
        
        logger.bind(**self.logger_ctx.model_dump(exclude_none=True)).info(
            f"Graph Partitioning complete. Extracted {len(valid_clusters)} valid cohesive cohorts."
        )
        
        return valid_clusters
