import json

import pytest

from src.engine.trader.reconciliation import (
    ExchangePositionSnapshot,
    ReadOnlyReconciliationAuditor,
    run_boot_reconciliation,
    run_read_only_audit,
)
from src.engine.trader.state_manager import TradeStateManager


class FakeSnapshotProvider:
    def __init__(self, positions):
        self.positions = positions
        self.called = False

    async def fetch_open_positions(self):
        self.called = True
        return self.positions


class FailingSnapshotProvider:
    async def fetch_open_positions(self):
        raise RuntimeError("account snapshot unavailable")


@pytest.fixture
def state():
    mgr = TradeStateManager(db_path=":memory:")
    yield mgr
    mgr.close()


def _open_long_spread(state):
    return state.open_position(
        pair_label="BTC/USDT|ETH/USDT",
        asset_x="BTC/USDT",
        asset_y="ETH/USDT",
        side="LONG_SPREAD",
        entry_price_a=100.0,
        entry_price_b=50.0,
        weight_a=0.6,
        weight_b=0.4,
        entry_z=-2.0,
        lookback_bars=21,
    )


@pytest.mark.asyncio
async def test_boot_reconciliation_records_matched_legs(state):
    spread_id = _open_long_spread(state)
    provider = FakeSnapshotProvider(
        [
            ExchangePositionSnapshot(symbol="BTC/USDT", side="LONG", qty=0.6),
            ExchangePositionSnapshot(symbol="ETH/USDT", side="SHORT", qty=0.4),
        ]
    )

    run_id = await run_boot_reconciliation(
        state=state,
        snapshot_provider=provider,
        credentials_available=True,
    )

    assert provider.called is True
    runs = state.get_reconciliation_runs()
    deltas = state.get_reconciliation_deltas(run_id=run_id)
    assert runs[0]["status"] == "MATCHED"
    assert [delta["delta_type"] for delta in deltas] == ["MATCHED", "MATCHED"]
    assert {delta["spread_id"] for delta in deltas} == {spread_id}
    assert {delta["action_taken"] for delta in deltas} == {"NO_ACTION"}
    assert len(state.get_open_positions()) == 1


@pytest.mark.asyncio
async def test_boot_reconciliation_records_mismatch_deltas_without_actions(state):
    _open_long_spread(state)
    provider = FakeSnapshotProvider(
        [
            ExchangePositionSnapshot(symbol="BTC/USDT", side="SHORT", qty=0.6),
            ExchangePositionSnapshot(symbol="ETH/USDT", side="SHORT", qty=0.9),
            ExchangePositionSnapshot(symbol="SOL/USDT", side="LONG", qty=1.0),
        ]
    )

    run_id = await run_boot_reconciliation(
        state=state,
        snapshot_provider=provider,
        credentials_available=True,
    )

    runs = state.get_reconciliation_runs()
    deltas = state.get_reconciliation_deltas(run_id=run_id)
    assert runs[0]["status"] == "DELTA_FOUND"
    assert [delta["delta_type"] for delta in deltas] == [
        "SIDE_MISMATCH",
        "QTY_MISMATCH",
        "EXCHANGE_ONLY_POSITION",
    ]
    assert {delta["action_taken"] for delta in deltas} == {"NO_ACTION"}
    assert len(state.get_open_positions()) == 1

    qty_payload = json.loads(deltas[1]["payload_json"])
    assert qty_payload["local_leg"]["target_qty"] == 0.4
    assert qty_payload["exchange_position"]["qty"] == 0.9


@pytest.mark.asyncio
async def test_boot_reconciliation_records_local_only_positions(state):
    _open_long_spread(state)
    provider = FakeSnapshotProvider([])

    run_id = await run_boot_reconciliation(
        state=state,
        snapshot_provider=provider,
        credentials_available=True,
    )

    deltas = state.get_reconciliation_deltas(run_id=run_id)
    assert [delta["delta_type"] for delta in deltas] == [
        "LOCAL_ONLY_POSITION",
        "LOCAL_ONLY_POSITION",
    ]
    assert all(delta["action_taken"] == "NO_ACTION" for delta in deltas)


@pytest.mark.asyncio
async def test_boot_reconciliation_records_symbol_mismatch(state):
    spread_id = _open_long_spread(state)
    provider = FakeSnapshotProvider(
        [
            ExchangePositionSnapshot(
                symbol="DOGE/USDT",
                side="LONG",
                qty=0.6,
                spread_id=spread_id,
            ),
        ]
    )

    run_id = await run_boot_reconciliation(
        state=state,
        snapshot_provider=provider,
        credentials_available=True,
    )

    delta_types = [
        delta["delta_type"]
        for delta in state.get_reconciliation_deltas(run_id=run_id)
    ]
    assert "SYMBOL_MISMATCH" in delta_types


@pytest.mark.asyncio
async def test_boot_reconciliation_skips_without_provider(state):
    _open_long_spread(state)

    run_id = await run_boot_reconciliation(
        state=state,
        snapshot_provider=None,
        credentials_available=True,
    )

    runs = state.get_reconciliation_runs()
    deltas = state.get_reconciliation_deltas(run_id=run_id)
    assert runs[0]["status"] == "SKIPPED_NO_SNAPSHOT_PROVIDER"
    assert deltas == []
    assert len(state.get_open_positions()) == 1


@pytest.mark.asyncio
async def test_boot_reconciliation_skips_without_credentials(state):
    _open_long_spread(state)
    provider = FakeSnapshotProvider(
        [ExchangePositionSnapshot(symbol="BTC/USDT", side="LONG", qty=0.6)]
    )

    run_id = await run_boot_reconciliation(
        state=state,
        snapshot_provider=provider,
        credentials_available=False,
    )

    runs = state.get_reconciliation_runs()
    assert provider.called is False
    assert runs[0]["status"] == "SKIPPED_NO_CREDENTIALS"
    assert state.get_reconciliation_deltas(run_id=run_id) == []


@pytest.mark.asyncio
async def test_boot_reconciliation_records_snapshot_provider_failure(state):
    _open_long_spread(state)

    run_id = await run_boot_reconciliation(
        state=state,
        snapshot_provider=FailingSnapshotProvider(),
        credentials_available=True,
    )

    runs = state.get_reconciliation_runs()
    assert runs[0]["id"] == run_id
    assert runs[0]["status"] == "FAILED"
    snapshot = json.loads(runs[0]["exchange_snapshot_json"])
    assert snapshot["error"] == "account snapshot unavailable"
    assert state.get_reconciliation_deltas(run_id=run_id) == []


@pytest.mark.asyncio
async def test_read_only_auditor_surfaces_unresolved_deltas_without_position_mutation(state):
    _open_long_spread(state)
    provider = FakeSnapshotProvider(
        [
            ExchangePositionSnapshot(symbol="BTC/USDT", side="SHORT", qty=0.6),
            ExchangePositionSnapshot(symbol="ETH/USDT", side="SHORT", qty=0.9),
        ]
    )
    positions_before = state.get_all_orders()
    legs_before = state.get_leg_fills()

    report = await run_read_only_audit(
        state=state,
        snapshot_provider=provider,
        credentials_available=True,
    )

    assert report.status == "DELTA_FOUND"
    assert report.has_unresolved_deltas is True
    assert report.unresolved_delta_count == 2
    assert [delta["delta_type"] for delta in report.unresolved_deltas] == [
        "SIDE_MISMATCH",
        "QTY_MISMATCH",
    ]
    assert {delta["action_taken"] for delta in report.unresolved_deltas} == {"NO_ACTION"}
    assert state.get_all_orders() == positions_before
    assert state.get_leg_fills() == legs_before


@pytest.mark.asyncio
async def test_read_only_auditor_can_run_scheduled_with_explicit_limit(state):
    _open_long_spread(state)
    provider = FakeSnapshotProvider(
        [
            ExchangePositionSnapshot(symbol="BTC/USDT", side="LONG", qty=0.6),
            ExchangePositionSnapshot(symbol="ETH/USDT", side="SHORT", qty=0.4),
        ]
    )
    auditor = ReadOnlyReconciliationAuditor(
        state=state,
        snapshot_provider=provider,
        credentials_available=True,
    )

    reports = await auditor.run_scheduled(interval_seconds=0.0, max_runs=2)

    assert [report.status for report in reports] == ["MATCHED", "MATCHED"]
    assert [report.unresolved_delta_count for report in reports] == [0, 0]
    assert len(state.get_reconciliation_runs()) == 2
