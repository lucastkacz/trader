"""Stored-data quality filters for post-download universe construction."""

from src.data.ohlcv import OHLCVMetadata


def metadata_passes_quality(
    metadata: OHLCVMetadata | None,
    *,
    require_coverage_status: str,
    require_quality_status: str,
    max_missing_candles: int,
    max_gap_count: int,
) -> bool:
    """Return whether stored OHLCV metadata satisfies the configured quality bar."""
    if metadata is None:
        return False
    if metadata.coverage_status != require_coverage_status:
        return False
    if metadata.quality_status != require_quality_status:
        return False
    if metadata.missing_candles is None or metadata.missing_candles > max_missing_candles:
        return False
    if metadata.gap_count is None or metadata.gap_count > max_gap_count:
        return False
    return True
