import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.engine.trader.config import (
    PipelineConfig,
    load_pipeline_config,
    load_risk_config,
    load_strategy_config,
)
from src.engine.trader.runtime.artifacts import build_pair_artifact
from src.engine.trader.runtime.monitoring.run_status import (
    OBSERVER_RUN_STATE_KEY,
    build_run_status_snapshot,
    record_observer_run_started,
)
from src.engine.trader.runtime.trader_runner import run_trader_loop
from src.engine.trader.state.manager import TradeStateManager


def _open_test_position(state: TradeStateManager) -> int:
    return state.open_position(
        pair_label="BTC/USDT|ETH/USDT",
        asset_x="BTC/USDT",
        asset_y="ETH/USDT",
        side="LONG_SPREAD",
        entry_price_a=100.0,
        entry_price_b=50.0,
        weight_a=0.5,
        weight_b=0.5,
        entry_z=-2.0,
        lookback_bars=120,
    )


def _pipeline_with_db(tmp_path) -> PipelineConfig:
    pipeline_cfg = load_pipeline_config("configs/pipelines/dev.yml")
    pipeline_data = pipeline_cfg.model_dump()
    pipeline_data["execution"]["db_path"] = str(tmp_path / "trader.db")
    pipeline_data["execution"]["artifact_base_dir"] = str(tmp_path / "universes")
    pipeline_data["execution"]["market_data_base_dir"] = str(tmp_path / "parquet")
    pipeline_data["execution"]["max_ticks"] = 180
    return PipelineConfig.model_validate(pipeline_data)


def _write_test_pair_artifact(tmp_path):
    artifact_path = tmp_path / "surviving_pairs.json"
    artifact_path.write_text(
        json.dumps(
            build_pair_artifact(
                [
                    {
                        "Asset_X": "BTC/USDT",
                        "Asset_Y": "ETH/USDT",
                        "Hedge_Ratio": 1.0,
                        "Best_Params": {"lookback_bars": 120, "entry_z": 2.0},
                        "Performance": {
                            "final_pnl_pct": 1.0,
                            "sharpe_ratio": 3.0,
                        },
                    }
                ],
                timeframe="1m",
                exchange="bybit",
                generated_at="2026-05-16T23:50:56+00:00",
            )
        ),
        encoding="utf-8",
    )
    return artifact_path


def test_observer_start_marker_captures_existing_open_positions(tmp_path):
    state = TradeStateManager(db_path=str(tmp_path / "trader.db"))
    try:
        spread_id = _open_test_position(state)

        record_observer_run_started(state, max_ticks=180)

        marker = state.get_runtime_state(OBSERVER_RUN_STATE_KEY)
    finally:
        state.close()

    assert marker["status"] == "RUNNING"
    assert marker["max_ticks"] == 180
    assert marker["completed_ticks"] == 0
    assert marker["open_position_ids"] == [spread_id]


def test_run_status_classifies_old_running_marker_without_ticks_as_stale(tmp_path):
    state = TradeStateManager(db_path=str(tmp_path / "trader.db"))
    started_at = datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc)
    now = started_at + timedelta(minutes=20)
    try:
        spread_id = _open_test_position(state)
        state.set_runtime_state(
            OBSERVER_RUN_STATE_KEY,
            {
                "status": "RUNNING",
                "started_at": started_at.isoformat(),
                "max_ticks": 180,
                "completed_ticks": 0,
                "completed_at": None,
                "open_position_ids": [],
            },
        )

        snapshot = build_run_status_snapshot(
            state,
            environment="TEST",
            stale_after_minutes=5,
            surviving_pairs_path=_write_test_pair_artifact(tmp_path),
            now=now,
        )
    finally:
        state.close()

    assert snapshot.observer_status == "STALE_RUN_MARKER"
    assert "no tick arrived within 5.0 minutes" in snapshot.observer_detail
    assert "no active process is implied" in snapshot.observer_detail
    assert snapshot.open_position_ids == [spread_id]
    assert snapshot.health.open_positions == 1


def test_run_status_classifies_running_marker_without_started_at_as_stale(tmp_path):
    state = TradeStateManager(db_path=str(tmp_path / "trader.db"))
    now = datetime(2026, 5, 29, 12, 20, tzinfo=timezone.utc)
    try:
        state.set_runtime_state(
            OBSERVER_RUN_STATE_KEY,
            {
                "status": "RUNNING",
                "started_at": None,
                "max_ticks": 180,
                "completed_ticks": 0,
                "completed_at": None,
                "open_position_ids": [],
            },
        )

        snapshot = build_run_status_snapshot(
            state,
            environment="TEST",
            stale_after_minutes=5,
            surviving_pairs_path=_write_test_pair_artifact(tmp_path),
            now=now,
        )
    finally:
        state.close()

    assert snapshot.observer_status == "STALE_RUN_MARKER"
    assert "start time is missing or invalid" in snapshot.observer_detail


def test_run_status_classifies_old_running_marker_with_stale_tick_as_stale(tmp_path):
    state = TradeStateManager(db_path=str(tmp_path / "trader.db"))
    try:
        spread_id = _open_test_position(state)
        state.record_tick_signal(
            pair_label="BTC/USDT|ETH/USDT",
            z_score=-1.0,
            weight_a=0.5,
            weight_b=0.5,
            signal="LONG_SPREAD",
            action="HOLD",
            price_a=101.0,
            price_b=49.0,
        )
        latest = datetime.fromisoformat(
            state.get_tick_signals()[-1]["timestamp"]
        ).astimezone(timezone.utc)
        state.set_runtime_state(
            OBSERVER_RUN_STATE_KEY,
            {
                "status": "RUNNING",
                "started_at": (latest - timedelta(minutes=10)).isoformat(),
                "max_ticks": 180,
                "completed_ticks": 0,
                "completed_at": None,
                "open_position_ids": [],
            },
        )

        snapshot = build_run_status_snapshot(
            state,
            environment="TEST",
            stale_after_minutes=5,
            surviving_pairs_path=_write_test_pair_artifact(tmp_path),
            now=latest + timedelta(minutes=10),
        )
    finally:
        state.close()

    assert snapshot.observer_status == "STALE_RUN_MARKER"
    assert "latest tick is stale" in snapshot.observer_detail
    assert "Current open local positions: 1" in snapshot.observer_detail
    assert snapshot.open_position_ids == [spread_id]


def test_run_status_keeps_fresh_running_marker_waiting_for_first_tick(tmp_path):
    state = TradeStateManager(db_path=str(tmp_path / "trader.db"))
    started_at = datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc)
    try:
        state.set_runtime_state(
            OBSERVER_RUN_STATE_KEY,
            {
                "status": "RUNNING",
                "started_at": started_at.isoformat(),
                "max_ticks": 180,
                "completed_ticks": 0,
                "completed_at": None,
                "open_position_ids": [],
            },
        )

        snapshot = build_run_status_snapshot(
            state,
            environment="TEST",
            stale_after_minutes=5,
            surviving_pairs_path=_write_test_pair_artifact(tmp_path),
            now=started_at + timedelta(minutes=1),
        )
    finally:
        state.close()

    assert snapshot.observer_status == "RUNNING_WAITING_FOR_FIRST_TICK"
    assert "no tick recorded yet" in snapshot.observer_detail


@pytest.mark.asyncio
async def test_cancelled_trader_run_records_interrupted_with_open_positions(
    monkeypatch,
    tmp_path,
):
    pipeline_cfg = _pipeline_with_db(tmp_path)
    strategy_cfg = load_strategy_config("configs/strategy/dev.yml")
    risk_cfg = load_risk_config("configs/risk/alpha_v1.yml")

    state = TradeStateManager(db_path=pipeline_cfg.execution.db_path)
    try:
        spread_id = _open_test_position(state)
    finally:
        state.close()

    monkeypatch.setattr(
        "src.engine.trader.runtime.trader_runner.load_tier1_pairs",
        lambda *args, **kwargs: [
            {
                "Asset_X": "BTC/USDT",
                "Asset_Y": "ETH/USDT",
                "Hedge_Ratio": 1.0,
                "Best_Params": {"lookback_bars": 120, "entry_z": 2.0},
            }
        ],
    )

    async def noop_boot_reconciliation(*args, **kwargs):
        return None

    async def noop_boot_health(*args, **kwargs):
        return None

    async def cancelled_ticks(*args, **kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr(
        "src.engine.trader.runtime.trader_runner._run_boot_reconciliation",
        noop_boot_reconciliation,
    )
    monkeypatch.setattr(
        "src.engine.trader.runtime.trader_runner._notify_boot_health",
        noop_boot_health,
    )
    monkeypatch.setattr(
        "src.engine.trader.runtime.trader_runner._run_ticks",
        cancelled_ticks,
    )

    notifier = SimpleNamespace(send=AsyncMock())
    with pytest.raises(asyncio.CancelledError):
        await run_trader_loop(
            pipeline_cfg=pipeline_cfg,
            strategy_cfg=strategy_cfg,
            risk_cfg=risk_cfg,
            notifier=notifier,
        )

    state = TradeStateManager(db_path=pipeline_cfg.execution.db_path)
    try:
        marker = state.get_runtime_state(OBSERVER_RUN_STATE_KEY)
    finally:
        state.close()

    assert marker["status"] == "INTERRUPTED"
    assert marker["max_ticks"] == 180
    assert marker["completed_ticks"] == 0
    assert marker["open_position_ids"] == [spread_id]
    assert marker["interrupted_at"] is not None
