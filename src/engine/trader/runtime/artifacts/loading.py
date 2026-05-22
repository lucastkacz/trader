"""Promoted eligible-pair artifact loading helpers."""

import json
from pathlib import Path
from typing import Any

from src.core.logger import logger
from src.engine.trader.runtime.artifacts.contract import extract_pair_artifact_pairs
from src.engine.trader.runtime.artifacts.lifecycle import promoted_pair_artifact_path


def load_tier1_pairs(
    timeframe: str,
    min_sharpe: float,
    exchange: str,
    artifact_base_dir: str | Path,
) -> list[dict[str, Any]]:
    """Load the promoted surviving pairs artifact and filter to Tier 1."""
    path = promoted_pair_artifact_path(timeframe, artifact_base_dir)
    if not path.exists():
        raise FileNotFoundError(
            f"Surviving pairs artifact missing: {path}. "
            "Run research first for this timeframe before launching execute."
        )

    with path.open() as f:
        all_pairs = extract_pair_artifact_pairs(
            artifact=json.load(f),
            source_path=path,
            expected_timeframe=timeframe,
            expected_exchange=exchange,
        )

    tier1 = [
        pair for pair in all_pairs
        if pair["Performance"]["sharpe_ratio"] >= min_sharpe
    ]

    logger.info(
        f"Loaded {len(tier1)} Tier 1 pairs (Sharpe >= {min_sharpe}) "
        f"from {len(all_pairs)} total survivors."
    )
    return tier1
