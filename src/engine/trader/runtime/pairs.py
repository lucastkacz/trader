"""Surviving-pair loading helpers for the trader runtime."""

import json
from typing import Any

from src.core.logger import logger


def load_tier1_pairs(timeframe: str, min_sharpe: float) -> list[dict[str, Any]]:
    """Load surviving pairs and filter to Tier 1 by Sharpe threshold."""
    path = f"data/universes/{timeframe}/surviving_pairs.json"
    with open(path) as f:
        all_pairs = json.load(f)

    tier1 = [
        p for p in all_pairs
        if p.get("Performance", {}).get("sharpe_ratio", 0) >= min_sharpe
    ]

    logger.info(
        f"Loaded {len(tier1)} Tier 1 pairs (Sharpe >= {min_sharpe}) "
        f"from {len(all_pairs)} total survivors."
    )
    return tier1
