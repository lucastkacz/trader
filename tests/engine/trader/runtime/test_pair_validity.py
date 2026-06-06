import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from src.data.storage.local_parquet import LocalOHLCVParquetStore
from src.engine.trader.runtime.artifacts import build_pair_artifact
from src.engine.trader.runtime.pair_validity import (
    build_pair_validity_report,
    build_pair_validity_report_if_configured,
)
from src.engine.trader.runtime.pair_validity.models import PairValidityConfig
from src.engine.trader.state.manager import TradeStateManager


def test_pair_validity_computes_recent_drift_and_artifact_age(tmp_path):
    artifact_path = _write_artifact(
        tmp_path,
        generated_at="2026-05-18T00:00:00+00:00",
    )
    storage = LocalOHLCVParquetStore(base_dir=str(tmp_path / "parquet"))
    frame_x, frame_y = _cointegrated_ohlcv_frames(periods=180)
    storage.save_ohlcv("AAA/USDT", "1m", frame_x, {}, exchange="bybit")
    storage.save_ohlcv("BBB/USDT", "1m", frame_y, {}, exchange="bybit")
    state = TradeStateManager(db_path=":memory:")

    try:
        report = build_pair_validity_report(
            surviving_pairs_path=artifact_path,
            market_data_base_dir=tmp_path / "parquet",
            state=state,
            config=PairValidityConfig(
                recent_window_bars=120,
                min_recent_bars=60,
                max_latest_data_age_bars=None,
                open_position_review_half_life_multiple=None,
            ),
            now=datetime(2026, 5, 18, 3, 0, tzinfo=timezone.utc),
        )
    finally:
        state.close()

    snapshot = report.snapshots[0]
    assert snapshot.pair_label == "AAA/USDT|BBB/USDT"
    assert snapshot.recent_observation_bars == 120
    assert snapshot.bars_since_artifact_generation == 179
    assert snapshot.wall_clock_age_minutes_since_artifact_generation == 180.0
    assert snapshot.recent_hedge_ratio is not None
    assert snapshot.hedge_ratio_drift_pct is not None
    assert snapshot.recent_correlation is not None
    assert snapshot.recent_p_value is not None
    assert "missing_research_window_end" in snapshot.notes
    assert "missing_research_spread_mean" in snapshot.notes


def test_pair_validity_uses_research_baseline_fields_when_present(tmp_path):
    artifact_path = _write_artifact(
        tmp_path,
        pair_overrides={
            "Research_Window": {
                "start": "2026-05-18T00:00:00+00:00",
                "end": "2026-05-18T02:59:00+00:00",
                "bars": 180,
            },
            "Correlation": 0.91,
            "Spread_Mean": 0.12,
            "Spread_Std": 0.04,
        },
    )
    storage = LocalOHLCVParquetStore(base_dir=str(tmp_path / "parquet"))
    frame_x, frame_y = _cointegrated_ohlcv_frames(periods=180)
    storage.save_ohlcv("AAA/USDT", "1m", frame_x, {}, exchange="bybit")
    storage.save_ohlcv("BBB/USDT", "1m", frame_y, {}, exchange="bybit")
    state = TradeStateManager(db_path=":memory:")

    try:
        report = build_pair_validity_report(
            surviving_pairs_path=artifact_path,
            market_data_base_dir=tmp_path / "parquet",
            state=state,
            config=PairValidityConfig(
                recent_window_bars=120,
                min_recent_bars=60,
                max_latest_data_age_bars=None,
                open_position_review_half_life_multiple=None,
            ),
            now=datetime(2026, 5, 18, 3, 0, tzinfo=timezone.utc),
        )
    finally:
        state.close()

    snapshot = report.snapshots[0]
    assert snapshot.research_window_start == "2026-05-18T00:00:00+00:00"
    assert snapshot.research_window_end == "2026-05-18T02:59:00+00:00"
    assert snapshot.research_correlation == 0.91
    assert snapshot.research_spread_mean == 0.12
    assert snapshot.research_spread_std == 0.04
    assert "missing_research_window_start" not in snapshot.notes
    assert "missing_research_window_end" not in snapshot.notes
    assert "missing_research_correlation" not in snapshot.notes
    assert "missing_research_spread_mean" not in snapshot.notes
    assert "missing_research_spread_std" not in snapshot.notes


def test_pair_validity_records_missing_market_data_without_mutation(tmp_path):
    artifact_path = _write_artifact(tmp_path)
    state = TradeStateManager(db_path=":memory:")

    try:
        report = build_pair_validity_report(
            surviving_pairs_path=artifact_path,
            market_data_base_dir=tmp_path / "empty_parquet",
            state=state,
            config=PairValidityConfig(
                recent_window_bars=60,
                min_recent_bars=30,
                max_latest_data_age_bars=None,
                open_position_review_half_life_multiple=None,
            ),
            now=datetime(2026, 5, 18, 3, 0, tzinfo=timezone.utc),
        )
    finally:
        state.close()

    snapshot = report.snapshots[0]
    assert snapshot.latest_data_at is None
    assert snapshot.recent_observation_bars == 0
    assert snapshot.recent_hedge_ratio is None
    assert "missing_recent_market_data" in snapshot.notes
    assert "missing_recent_market_data" in snapshot.operator_review_reasons


def test_pair_validity_flags_market_data_older_than_latest_age_limit(tmp_path):
    artifact_path = _write_artifact(tmp_path)
    storage = LocalOHLCVParquetStore(base_dir=str(tmp_path / "parquet"))
    frame_x, frame_y = _cointegrated_ohlcv_frames(periods=180)
    storage.save_ohlcv("AAA/USDT", "1m", frame_x, {}, exchange="bybit")
    storage.save_ohlcv("BBB/USDT", "1m", frame_y, {}, exchange="bybit")
    state = TradeStateManager(db_path=":memory:")

    try:
        report = build_pair_validity_report(
            surviving_pairs_path=artifact_path,
            market_data_base_dir=tmp_path / "parquet",
            state=state,
            config=PairValidityConfig(
                recent_window_bars=60,
                min_recent_bars=30,
                max_latest_data_age_bars=5,
                open_position_review_half_life_multiple=None,
            ),
            now=datetime(2026, 5, 18, 3, 10, tzinfo=timezone.utc),
        )
    finally:
        state.close()

    assert "market_data_older_than_latest_age_limit" in (
        report.snapshots[0].operator_review_reasons
    )


def test_open_position_half_life_review_reason_does_not_close_position(tmp_path):
    artifact_path = _write_artifact(
        tmp_path,
        pair_overrides={"Half_Life": 10.0},
    )
    storage = LocalOHLCVParquetStore(base_dir=str(tmp_path / "parquet"))
    frame_x, frame_y = _cointegrated_ohlcv_frames(periods=90)
    storage.save_ohlcv("AAA/USDT", "1m", frame_x, {}, exchange="bybit")
    storage.save_ohlcv("BBB/USDT", "1m", frame_y, {}, exchange="bybit")
    state = TradeStateManager(db_path=":memory:")
    spread_id = state.open_position(
        pair_label="AAA/USDT|BBB/USDT",
        asset_x="AAA/USDT",
        asset_y="BBB/USDT",
        side="LONG_SPREAD",
        entry_price_a=100.0,
        entry_price_b=90.0,
        weight_a=0.5,
        weight_b=0.5,
        entry_z=-2.0,
        lookback_bars=30,
    )
    state.conn.execute(
        "UPDATE spread_positions SET opened_at=? WHERE id=?",
        ("2026-05-18T00:30:00+00:00", spread_id),
    )
    state.conn.commit()

    try:
        report = build_pair_validity_report(
            surviving_pairs_path=artifact_path,
            market_data_base_dir=tmp_path / "parquet",
            state=state,
            config=PairValidityConfig(
                recent_window_bars=60,
                min_recent_bars=30,
                max_latest_data_age_bars=None,
                open_position_review_half_life_multiple=2.0,
            ),
            now=datetime(2026, 5, 18, 3, 0, tzinfo=timezone.utc),
        )
        snapshot = report.snapshots[0]
        assert snapshot.open_position_id == spread_id
        assert snapshot.open_position_holding_bars == 59
        assert snapshot.open_position_half_life_multiple == 5.9
        assert (
            "open_position_exceeds_half_life_multiple"
            in snapshot.open_position_review_reasons
        )
        assert state.get_position_for_pair("AAA/USDT|BBB/USDT") is not None
    finally:
        state.close()


def test_pair_validity_flags_market_data_older_than_artifact_and_position(tmp_path):
    artifact_path = _write_artifact(
        tmp_path,
        generated_at="2026-05-18T03:00:00+00:00",
    )
    storage = LocalOHLCVParquetStore(base_dir=str(tmp_path / "parquet"))
    frame_x, frame_y = _cointegrated_ohlcv_frames(periods=90)
    storage.save_ohlcv("AAA/USDT", "1m", frame_x, {}, exchange="bybit")
    storage.save_ohlcv("BBB/USDT", "1m", frame_y, {}, exchange="bybit")
    state = TradeStateManager(db_path=":memory:")
    spread_id = state.open_position(
        pair_label="AAA/USDT|BBB/USDT",
        asset_x="AAA/USDT",
        asset_y="BBB/USDT",
        side="LONG_SPREAD",
        entry_price_a=100.0,
        entry_price_b=90.0,
        weight_a=0.5,
        weight_b=0.5,
        entry_z=-2.0,
        lookback_bars=30,
    )
    state.conn.execute(
        "UPDATE spread_positions SET opened_at=? WHERE id=?",
        ("2026-05-18T02:00:00+00:00", spread_id),
    )
    state.conn.commit()

    try:
        report = build_pair_validity_report(
            surviving_pairs_path=artifact_path,
            market_data_base_dir=tmp_path / "parquet",
            state=state,
            config=PairValidityConfig(
                recent_window_bars=60,
                min_recent_bars=30,
                max_latest_data_age_bars=None,
                open_position_review_half_life_multiple=3.0,
            ),
            now=datetime(2026, 5, 18, 3, 30, tzinfo=timezone.utc),
        )
    finally:
        state.close()

    snapshot = report.snapshots[0]
    assert "market_data_older_than_artifact_generation" in (
        snapshot.operator_review_reasons
    )
    assert "market_data_older_than_open_position" in (
        snapshot.open_position_review_reasons
    )


def test_pair_validity_optional_builder_skips_unconfigured_report(tmp_path):
    state = TradeStateManager(db_path=":memory:")
    try:
        report = build_pair_validity_report_if_configured(
            surviving_pairs_path=tmp_path / "missing.json",
            market_data_base_dir=None,
            state=state,
            config=None,
        )
    finally:
        state.close()

    assert report is None


def test_pair_validity_optional_builder_returns_unavailable_report_on_failure(tmp_path):
    state = TradeStateManager(db_path=":memory:")
    try:
        report = build_pair_validity_report_if_configured(
            surviving_pairs_path=tmp_path / "missing.json",
            market_data_base_dir=tmp_path / "parquet",
            state=state,
            config=PairValidityConfig(
                recent_window_bars=60,
                min_recent_bars=30,
                max_latest_data_age_bars=None,
                open_position_review_half_life_multiple=None,
            ),
        )
    finally:
        state.close()

    assert report is not None
    assert report.timeframe == "unknown"
    assert report.exchange == "unknown"
    assert report.snapshots == []
    assert report.notes[0].startswith("pair_validity_unavailable:")


def _write_artifact(
    tmp_path,
    *,
    generated_at: str = "2026-05-18T00:00:00+00:00",
    pair_overrides: dict | None = None,
):
    pair = {
        "Asset_X": "AAA/USDT",
        "Asset_Y": "BBB/USDT",
        "P_Value": 0.03,
        "Hedge_Ratio": 0.7,
        "Half_Life": 40.0,
        "Best_Params": {"lookback_bars": 60, "entry_z": 1.5},
        "Performance": {"sharpe_ratio": 1.2, "final_pnl_pct": 0.04},
    }
    if pair_overrides:
        pair.update(pair_overrides)
    artifact_path = tmp_path / "surviving_pairs.json"
    artifact_path.write_text(
        json.dumps(
            build_pair_artifact(
                [pair],
                timeframe="1m",
                exchange="bybit",
                generated_at=generated_at,
            )
        ),
        encoding="utf-8",
    )
    return artifact_path


def _cointegrated_ohlcv_frames(periods: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(42)
    timestamps = pd.date_range(
        "2026-05-18T00:00:00Z",
        periods=periods,
        freq="1min",
    )
    log_y = np.log(100.0) + rng.normal(0.0, 0.01, periods).cumsum()
    stationary_noise = rng.normal(0.0, 0.002, periods)
    log_x = 0.7 * log_y + 1.2 + stationary_noise
    return (
        _ohlcv_frame(timestamps, np.exp(log_x)),
        _ohlcv_frame(timestamps, np.exp(log_y)),
    )


def _ohlcv_frame(timestamps: pd.DatetimeIndex, close: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": np.full(len(close), 1000.0),
        }
    )
