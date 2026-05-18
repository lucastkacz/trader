from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.engine.trader.config import load_pipeline_config
from src.engine.trader.runtime.monitoring.health import (
    build_trader_health_snapshot,
    render_trader_health_snapshot,
)
from src.engine.trader.runtime.trader_runner import _notify_boot_health
from src.engine.trader.state_manager import TradeStateManager


def test_health_snapshot_reports_stale_tick(tmp_path):
    state = TradeStateManager(db_path=str(tmp_path / "trader.db"))
    try:
        state.record_tick_signal(
            pair_label="BTC|ETH",
            z_score=0.1,
            weight_a=0.5,
            weight_b=0.5,
            signal="FLAT",
            action="SKIP",
            price_a=100.0,
            price_b=50.0,
        )
        latest = state.get_tick_signals()[-1]["timestamp"]
        now = datetime.fromisoformat(latest).astimezone(timezone.utc) + timedelta(minutes=10)

        snapshot = build_trader_health_snapshot(
            state,
            environment="TEST",
            stale_after_minutes=5,
            now=now,
        )
    finally:
        state.close()

    assert snapshot.status == "STALE"
    assert snapshot.latest_tick_age_minutes == 10
    assert "Status: <b>STALE</b>" in render_trader_health_snapshot(snapshot)


def test_health_snapshot_reports_no_ticks(tmp_path):
    state = TradeStateManager(db_path=str(tmp_path / "trader.db"))
    try:
        snapshot = build_trader_health_snapshot(
            state,
            environment="TEST",
            stale_after_minutes=5,
        )
    finally:
        state.close()

    assert snapshot.status == "NO_TICKS"
    assert snapshot.latest_tick_at is None


@pytest.mark.asyncio
async def test_boot_health_notifies_when_runtime_has_no_ticks(tmp_path):
    state = TradeStateManager(db_path=str(tmp_path / "trader.db"))
    pipeline_cfg = load_pipeline_config("configs/pipelines/dev.yml")
    notifier = SimpleNamespace(send=AsyncMock())
    try:
        await _notify_boot_health(state, pipeline_cfg, notifier)
    finally:
        state.close()

    notifier.send.assert_awaited_once()
    message = notifier.send.await_args.args[0]
    assert "BOOT HEALTH" in message
    assert "Status: <b>NO_TICKS</b>" in message
