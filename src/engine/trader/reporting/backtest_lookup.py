"""Backtest lookup loading for report generation."""

import json
from typing import Any

from src.core.logger import logger


def _load_backtest_lookup(surviving_pairs_path: str) -> dict[str, dict[str, Any]]:
    """Load surviving_pairs.json and build a lookup keyed by pair label."""
    try:
        with open(surviving_pairs_path) as f:
            pairs = json.load(f)
    except FileNotFoundError:
        logger.warning(f"Backtest file not found: {surviving_pairs_path}")
        return {}

    lookup = {}
    for p in pairs:
        label = f"{p['Asset_X']}|{p['Asset_Y']}"
        lookup[label] = p
    return lookup
