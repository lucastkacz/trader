import pandas as pd
import pytest

from src.data.ohlcv import (
    OHLCVFrameError,
    OHLCVRetentionPolicy,
    apply_ohlcv_retention,
    merge_ohlcv_frames,
    normalize_ohlcv_frame,
    validate_ohlcv_frame,
)


def test_normalize_ohlcv_frame_sorts_deduplicates_and_casts():
    _announce(
        "Normalizes a messy OHLCV frame by sorting timestamps, removing duplicate "
        "candles, and casting numeric values."
    )
    frame = pd.DataFrame(
        {
            "timestamp": [1600000060000, 1600000000000, 1600000060000],
            "open": ["11", "10", "12"],
            "high": ["12", "11", "13"],
            "low": ["10", "9", "11"],
            "close": ["11.5", "10.5", "12.5"],
            "volume": ["100", "90", "110"],
        }
    )

    normalized = normalize_ohlcv_frame(frame)

    assert normalized["timestamp"].tolist() == [1600000000000, 1600000060000]
    assert normalized["close"].tolist() == [10.5, 12.5]
    assert str(normalized["close"].dtype) == "float64"


def test_normalize_ohlcv_frame_requires_contract_columns():
    _announce(
        "Checks that OHLCV normalization rejects frames that are missing required "
        "columns like open, high, low, volume."
    )
    frame = pd.DataFrame({"timestamp": [1600000000000], "close": [10.0]})

    with pytest.raises(OHLCVFrameError, match="missing required columns"):
        normalize_ohlcv_frame(frame)


def test_validate_ohlcv_frame_rejects_duplicate_timestamps():
    _announce(
        "Checks that canonical OHLCV validation rejects duplicate candle timestamps."
    )
    frame = pd.DataFrame(
        {
            "timestamp": [1600000000000, 1600000000000],
            "open": [10.0, 11.0],
            "high": [11.0, 12.0],
            "low": [9.0, 10.0],
            "close": [10.5, 11.5],
            "volume": [100.0, 110.0],
        }
    )

    with pytest.raises(OHLCVFrameError, match="duplicate timestamps"):
        validate_ohlcv_frame(frame)


def test_validate_ohlcv_frame_rejects_unsorted_timestamps():
    _announce(
        "Checks that canonical OHLCV validation rejects candles that are not sorted "
        "oldest to newest."
    )
    frame = pd.DataFrame(
        {
            "timestamp": [1600000060000, 1600000000000],
            "open": [11.0, 10.0],
            "high": [12.0, 11.0],
            "low": [10.0, 9.0],
            "close": [11.5, 10.5],
            "volume": [110.0, 100.0],
        }
    )

    with pytest.raises(OHLCVFrameError, match="sorted ascending"):
        validate_ohlcv_frame(frame)


def test_merge_ohlcv_frames_keeps_latest_duplicate_timestamp():
    _announce(
        "Merges existing and incoming OHLCV frames and confirms the incoming candle "
        "wins when timestamps overlap."
    )
    existing = pd.DataFrame(
        {
            "timestamp": [1600000000000],
            "open": [10.0],
            "high": [11.0],
            "low": [9.0],
            "close": [10.5],
            "volume": [100.0],
        }
    )
    incoming = pd.DataFrame(
        {
            "timestamp": [1600000000000, 1600000060000],
            "open": [20.0, 30.0],
            "high": [21.0, 31.0],
            "low": [19.0, 29.0],
            "close": [20.5, 30.5],
            "volume": [200.0, 300.0],
        }
    )

    merged = merge_ohlcv_frames(existing, incoming)

    assert merged["timestamp"].tolist() == [1600000000000, 1600000060000]
    assert merged["close"].tolist() == [20.5, 30.5]


def test_apply_ohlcv_retention_by_max_bars_and_age():
    _announce(
        "Applies OHLCV retention rules and confirms old candles are trimmed by age "
        "and max-bar count."
    )
    frame = pd.DataFrame(
        {
            "timestamp": [1600000000000, 1600086400000, 1600172800000],
            "open": [1.0, 2.0, 3.0],
            "high": [1.0, 2.0, 3.0],
            "low": [1.0, 2.0, 3.0],
            "close": [1.0, 2.0, 3.0],
            "volume": [1.0, 2.0, 3.0],
        }
    )

    retained = apply_ohlcv_retention(
        frame,
        OHLCVRetentionPolicy(max_bars=1, max_age_days=2),
        now_ms=1600172800000,
    )

    assert retained["timestamp"].tolist() == [1600172800000]


def _announce(message: str) -> None:
    print(f"\nTEST: {message}")
