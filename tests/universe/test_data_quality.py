from src.data.ohlcv import OHLCVMetadata
from src.universe.filters.data_quality import metadata_passes_quality


def test_metadata_passes_quality_requires_complete_validated_gapless_data():
    assert metadata_passes_quality(
        _metadata(
            coverage_status="COMPLETE",
            quality_status="VALIDATED",
            missing_candles=0,
            gap_count=0,
        ),
        require_coverage_status="COMPLETE",
        require_quality_status="VALIDATED",
        max_missing_candles=0,
        max_gap_count=0,
    )
    assert not metadata_passes_quality(
        _metadata(
            coverage_status="INCOMPLETE",
            quality_status="VALIDATED",
            missing_candles=0,
            gap_count=0,
        ),
        require_coverage_status="COMPLETE",
        require_quality_status="VALIDATED",
        max_missing_candles=0,
        max_gap_count=0,
    )
    assert not metadata_passes_quality(
        _metadata(
            coverage_status="COMPLETE",
            quality_status="HAS_GAPS",
            missing_candles=1,
            gap_count=1,
        ),
        require_coverage_status="COMPLETE",
        require_quality_status="VALIDATED",
        max_missing_candles=0,
        max_gap_count=0,
    )


def test_metadata_passes_quality_rejects_missing_metadata():
    assert not metadata_passes_quality(
        None,
        require_coverage_status="COMPLETE",
        require_quality_status="VALIDATED",
        max_missing_candles=0,
        max_gap_count=0,
    )


def _metadata(
    *,
    coverage_status: str,
    quality_status: str,
    missing_candles: int,
    gap_count: int,
) -> OHLCVMetadata:
    return OHLCVMetadata(
        symbol="BTC/USDT:USDT",
        exchange="bybit",
        timeframe="1m",
        source="bybit",
        coverage_status=coverage_status,
        quality_status=quality_status,
        total_candles=10,
        expected_candles=10,
        missing_candles=missing_candles,
        gap_count=gap_count,
        max_gap_ms=0,
    )
