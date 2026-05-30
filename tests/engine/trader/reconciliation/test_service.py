import json
from datetime import datetime, timedelta, timezone

import pytest

from src.engine.trader.reconciliation import (
    ExchangePositionSnapshot,
    ReadOnlyReconciliationAuditor,
    ReconciliationPolicy,
    run_boot_reconciliation,
    run_read_only_audit,
)
from src.engine.trader.state.manager import TradeStateManager


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


class StalledSnapshotProvider:
    async def fetch_open_positions(self):
        import asyncio

        await asyncio.Event().wait()


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


def _policy(
    *,
    snapshot_timeout_seconds: float = 1.0,
    stale_order_after_seconds: float = 60.0,
) -> ReconciliationPolicy:
    return ReconciliationPolicy(
        snapshot_timeout_seconds=snapshot_timeout_seconds,
        stale_order_after_seconds=stale_order_after_seconds,
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
        policy=_policy(),
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
        policy=_policy(),
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
        policy=_policy(),
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
        policy=_policy(),
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
        policy=_policy(),
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
        policy=_policy(),
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
        policy=_policy(),
    )

    runs = state.get_reconciliation_runs()
    assert runs[0]["id"] == run_id
    assert runs[0]["status"] == "FAILED"
    snapshot = json.loads(runs[0]["exchange_snapshot_json"])
    assert snapshot["error"] == "account snapshot unavailable"
    deltas = state.get_reconciliation_deltas(run_id=run_id)
    assert [delta["delta_type"] for delta in deltas] == ["SNAPSHOT_PROVIDER_FAILURE"]
    assert deltas[0]["action_taken"] == "NO_ACTION"


@pytest.mark.asyncio
async def test_boot_reconciliation_times_out_stalled_snapshot_provider(state):
    run_id = await run_boot_reconciliation(
        state=state,
        snapshot_provider=StalledSnapshotProvider(),
        credentials_available=True,
        policy=_policy(snapshot_timeout_seconds=0.001),
    )

    runs = state.get_reconciliation_runs()
    assert runs[0]["id"] == run_id
    assert runs[0]["status"] == "FAILED"
    deltas = state.get_reconciliation_deltas(run_id=run_id)
    assert [delta["delta_type"] for delta in deltas] == ["SNAPSHOT_PROVIDER_FAILURE"]
    payload = json.loads(deltas[0]["payload_json"])
    assert payload["error"] == "snapshot request timed out"


@pytest.mark.asyncio
async def test_boot_reconciliation_surfaces_local_partial_fill_without_mutation(state):
    spread_id = _open_long_spread(state)
    first_leg, second_leg = state.get_leg_fills(spread_id=spread_id)
    state.record_leg_submit_requested(first_leg["id"], client_order_id="client-1")
    state.record_leg_acknowledged(first_leg["id"], exchange_order_id="exchange-1")
    state.record_leg_partially_filled(first_leg["id"], filled_qty=0.25, avg_fill_price=101.0)
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
        policy=_policy(),
    )

    deltas = state.get_reconciliation_deltas(run_id=run_id)
    assert state.get_reconciliation_runs()[0]["status"] == "DELTA_FOUND"
    assert [delta["delta_type"] for delta in deltas] == [
        "LOCAL_PARTIAL_FILL",
        "MATCHED",
        "MATCHED",
    ]
    payload = json.loads(deltas[0]["payload_json"])
    assert payload["local_leg"]["filled_qty"] == 0.25
    assert payload["local_leg"]["status"] == "PARTIALLY_FILLED"
    assert state.get_position_for_pair("BTC/USDT|ETH/USDT") is not None


@pytest.mark.asyncio
async def test_boot_reconciliation_surfaces_stale_local_order_without_mutation(state):
    spread_id = _open_long_spread(state)
    first_leg, _ = state.get_leg_fills(spread_id=spread_id)
    state.record_leg_submit_requested(first_leg["id"], client_order_id="client-1")
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
        policy=_policy(stale_order_after_seconds=30.0),
        now=datetime.now(timezone.utc) + timedelta(minutes=5),
    )

    deltas = state.get_reconciliation_deltas(run_id=run_id)
    assert state.get_reconciliation_runs()[0]["status"] == "DELTA_FOUND"
    assert [delta["delta_type"] for delta in deltas] == [
        "STALE_LOCAL_ORDER",
        "MATCHED",
        "MATCHED",
    ]
    payload = json.loads(deltas[0]["payload_json"])
    assert payload["local_leg"]["status"] == "SUBMIT_REQUESTED"
    assert payload["stale_order_after_seconds"] == 30.0
    assert state.get_position_for_pair("BTC/USDT|ETH/USDT") is not None


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
        policy=_policy(),
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
        policy=_policy(),
    )

    reports = await auditor.run_scheduled(interval_seconds=0.0, max_runs=2)

    assert [report.status for report in reports] == ["MATCHED", "MATCHED"]
    assert [report.unresolved_delta_count for report in reports] == [0, 0]
    assert len(state.get_reconciliation_runs()) == 2
