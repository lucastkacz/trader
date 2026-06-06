"""OHLCV retention policy helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd

from src.data.ohlcv.frames import normalize_ohlcv_frame


@dataclass(frozen=True)
class OHLCVRetentionPolicy:
    """Optional retention rule for trimming stored OHLCV datasets."""

    max_bars: int | None = None
    max_age_days: int | None = None

    def __post_init__(self) -> None:
        if self.max_bars is not None and self.max_bars <= 0:
            raise ValueError("max_bars must be positive when provided")
        if self.max_age_days is not None and self.max_age_days <= 0:
            raise ValueError("max_age_days must be positive when provided")


def apply_ohlcv_retention(
    frame: pd.DataFrame,
    policy: OHLCVRetentionPolicy | None,
    *,
    now_ms: int | None = None,
) -> pd.DataFrame:
    """Apply optional age and bar-count retention to an OHLCV frame."""
    normalized = normalize_ohlcv_frame(frame)
    if policy is None or normalized.empty:
        return normalized

    retained = normalized
    if policy.max_age_days is not None:
        reference_ms = now_ms or int(datetime.now(timezone.utc).timestamp() * 1000)
        cutoff_ms = reference_ms - policy.max_age_days * 24 * 60 * 60 * 1000
        retained = retained[retained["timestamp"] >= cutoff_ms]
    if policy.max_bars is not None:
        retained = retained.tail(policy.max_bars)
    return retained.reset_index(drop=True)
