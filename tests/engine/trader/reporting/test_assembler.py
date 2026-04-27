"""
Tests for the Trade Report Engine.
Uses in-memory SQLite with synthetic data to verify metric computations.
"""

import math
import pytest
from datetime import datetime, timezone, timedelta

from src.engine.trader.state_manager import TradeStateManager
from src.engine.trader.report_engine import (
    generate_report,
    _detect_bars_per_year,
    _compute_sharpe,
    _compute_sortino,
    _compute_max_drawdown,
    _compute_returns,
)
from src.engine.trader.report_generator import render_state_ledger


@pytest.fixture
def state():
    """Create a fresh in-memory state manager for each test."""
    mgr = TradeStateManager(db_path=":memory:")
    yield mgr
    mgr.close()


def _inject_snapshots(state, equities, interval_hours=4.0):
    """
    Helper to inject synthetic equity snapshots with controlled timestamps.
    `equities` is a list of total_equity_pct values.
    """
    base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    for i, eq in enumerate(equities):
        ts = (base + timedelta(hours=i * interval_hours)).isoformat()
        state.conn.execute(
            """INSERT INTO equity_snapshots
               (timestamp, total_equity_pct, open_positions, realized_pnl_pct, unrealized_pnl_pct, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ts, eq, 0, eq, 0.0, ""),
        )
    state.conn.commit()


def _inject_trade(state, pair_label, side, entry_a, entry_b, exit_a, exit_b,
                   weight_a=0.5, weight_b=0.5, entry_z=-2.0, exit_z=0.1,
                   holding_bars=6, pnl=None):
    """Helper to inject a closed trade directly into the database."""
    base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    t_open = base.isoformat()
    t_close = (base + timedelta(hours=holding_bars * 4)).isoformat()

    if pnl is None:
        ret_a = (exit_a - entry_a) / entry_a
        ret_b = (exit_b - entry_b) / entry_b
        if side == "LONG_SPREAD":
            pnl = weight_a * ret_a - weight_b * ret_b
        else:
            pnl = -weight_a * ret_a + weight_b * ret_b

    parts = pair_label.split("|")
    asset_x = parts[0] if len(parts) > 0 else "A"
    asset_y = parts[1] if len(parts) > 1 else "B"

    state.conn.execute(
        """INSERT INTO spread_positions
           (pair_label, asset_x, asset_y, side, entry_price_a, entry_price_b,
            weight_a, weight_b, entry_z, lookback_bars, opened_at,
            closed_at, exit_price_a, exit_price_b, realized_pnl_pct, status,
            exit_z, holding_bars, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CLOSED', ?, ?, ?, ?)""",
        (pair_label, asset_x, asset_y, side, entry_a, entry_b,
         weight_a, weight_b, entry_z, 14, t_open, t_close,
         exit_a, exit_b, pnl, exit_z, holding_bars, t_open, t_close),
    )
    state.conn.commit()


# ─── Tests ───────────────────────────────────────────────────────

def test_empty_database_report(state):
    """Empty database should produce a valid report with zero/default values."""
    # Use a non-existent path for surviving_pairs to test graceful fallback
    report = generate_report(state, min_sharpe=1.0, surviving_pairs_path="/nonexistent/path.json")

    assert report.total_equity_pct == 0.0
    assert report.total_trades == 0
    assert report.active_pairs == 0
    assert report.win_rate == 0.0
    assert report.sharpe_ratio is None
    assert report.sortino_ratio is None
    assert report.max_drawdown_pct == 0.0
    assert report.status == "HEALTHY"
    assert report.per_pair == []
    assert report.trade_log == []
    assert report.state_ledger.total_order_events == 0
    assert report.state_ledger.leg_targets_by_status_role == {}
    assert report.state_ledger.user_commands_by_status == {}
    assert report.state_ledger.latest_reconciliation_run_status is None
    assert report.state_ledger.reconciliation_delta_count == 0


def test_sharpe_ratio_calculation(state):
    """Inject known equity snapshots and verify Sharpe calculation."""
    # Varying returns → should produce a positive, finite Sharpe
    equities = [0.0, 0.01, 0.005, 0.02, 0.015, 0.03, 0.025, 0.04, 0.035, 0.05]
    _inject_snapshots(state, equities, interval_hours=4.0)

    curve = state.get_equity_curve()
    returns = _compute_returns(curve)
    bars_per_year = _detect_bars_per_year(curve)

    sharpe = _compute_sharpe(returns, bars_per_year)

    assert sharpe is not None
    assert sharpe > 0, "Upward-trending equity should have positive Sharpe"
    assert math.isfinite(sharpe), "Sharpe should be finite"


def test_sortino_ratio_calculation(state):
    """Sortino should only penalize downside volatility."""
    # Mix of up and down returns
    equities = [0.0, 0.02, 0.01, 0.03, 0.025, 0.04, 0.035, 0.05]
    _inject_snapshots(state, equities, interval_hours=4.0)

    curve = state.get_equity_curve()
    returns = _compute_returns(curve)
    bpy = _detect_bars_per_year(curve)

    sortino = _compute_sortino(returns, bpy)
    sharpe = _compute_sharpe(returns, bpy)

    assert sortino is not None
    assert sharpe is not None
    # Sortino should be >= Sharpe when there's positive drift with few downside moves
    # (downside std <= total std, so Sortino >= Sharpe)
    assert sortino >= sharpe


def test_max_drawdown_calculation(state):
    """Inject equity curve with known peak/trough and verify max DD."""
    # Peak at 0.10, trough at 0.03 → DD = -0.07
    equities = [0.0, 0.05, 0.10, 0.08, 0.03, 0.06, 0.09]
    _inject_snapshots(state, equities)

    curve = state.get_equity_curve()
    max_dd = _compute_max_drawdown(curve)

    assert abs(max_dd - (-0.07)) < 1e-10


def test_win_rate_and_profit_factor(state):
    """Inject 3 wins + 2 losses and verify trade stats."""
    # 3 winning trades
    _inject_trade(state, "A|B", "LONG_SPREAD", 100, 50, 110, 50, pnl=0.05)
    _inject_trade(state, "A|B", "LONG_SPREAD", 100, 50, 112, 50, pnl=0.06)
    _inject_trade(state, "C|D", "SHORT_SPREAD", 100, 50, 90, 55, pnl=0.10)

    # 2 losing trades
    _inject_trade(state, "A|B", "LONG_SPREAD", 100, 50, 95, 50, pnl=-0.025)
    _inject_trade(state, "C|D", "SHORT_SPREAD", 100, 50, 105, 45, pnl=-0.05)

    report = generate_report(state, min_sharpe=1.0, surviving_pairs_path="/nonexistent/path.json")

    assert report.total_trades == 5
    assert abs(report.win_rate - 0.6) < 1e-10  # 3/5

    # Profit factor = gross_profit / gross_loss = 0.21 / 0.075
    assert report.profit_factor is not None
    assert abs(report.profit_factor - (0.21 / 0.075)) < 1e-4


def test_per_pair_breakdown(state):
    """Two pairs with different PnL should be separated correctly."""
    _inject_trade(state, "A|B", "LONG_SPREAD", 100, 50, 110, 50, pnl=0.05)
    _inject_trade(state, "A|B", "LONG_SPREAD", 100, 50, 108, 50, pnl=0.04)
    _inject_trade(state, "C|D", "SHORT_SPREAD", 200, 100, 180, 110, pnl=0.15)

    report = generate_report(state, min_sharpe=1.0, surviving_pairs_path="/nonexistent/path.json")

    assert len(report.per_pair) == 2

    ab = [p for p in report.per_pair if p.pair_label == "A|B"][0]
    cd = [p for p in report.per_pair if p.pair_label == "C|D"][0]

    assert ab.trade_count == 2
    assert cd.trade_count == 1
    assert abs(ab.realized_pnl - 0.09) < 1e-10
    assert abs(cd.realized_pnl - 0.15) < 1e-10
    assert ab.win_rate == 1.0
    assert cd.win_rate == 1.0


def test_state_ledger_snapshot_counts_current_schema(state):
    """Report should surface basic state-ledger counts and latest reconciliation status."""
    spread_id = state.open_position(
        "X|Y", "X", "Y", "LONG_SPREAD", 100.0, 50.0, 0.6, 0.4, -2.0, 21
    )
    state.close_position("X|Y", 101.0, 50.0)

    state.write_command("/pause")
    commands = state.claim_pending_commands()
    state.mark_command_executed(commands[0]["id"])

    state.write_command("/stop_all")
    commands = state.claim_pending_commands()
    state.mark_command_failed(commands[0]["id"], "exchange unavailable")

    state.write_command("/resume")

    run_id = state.start_reconciliation_run(
        exchange_snapshot={"positions": []},
        local_open_positions=state.get_open_positions(),
    )
    state.record_reconciliation_delta(
        run_id=run_id,
        delta_type="LOCAL_ONLY_POSITION",
        spread_id=spread_id,
        payload={"reason": "closed before exchange check"},
    )
    state.finish_reconciliation_run(run_id, status="DELTA_FOUND")

    report = generate_report(state, min_sharpe=1.0, surviving_pairs_path="/nonexistent/path.json")

    assert report.state_ledger.total_order_events == 2
    assert report.state_ledger.leg_targets_by_status_role == {
        "TARGET_RECORDED": {
            "CLOSE": 2,
            "OPEN": 2,
        }
    }
    assert report.state_ledger.user_commands_by_status == {
        "EXECUTED": 1,
        "FAILED": 1,
        "PENDING": 1,
    }
    assert report.state_ledger.latest_reconciliation_run_status == "DELTA_FOUND"
    assert report.state_ledger.reconciliation_delta_count == 1


def test_state_ledger_terminal_renderer_outputs_counts(state, capsys):
    """Terminal reports should expose state-ledger status for operators."""
    state.open_position(
        "X|Y", "X", "Y", "LONG_SPREAD", 100.0, 50.0, 0.6, 0.4, -2.0, 21
    )
    state.write_command("/pause")

    report = generate_report(state, min_sharpe=1.0, surviving_pairs_path="/nonexistent/path.json")

    render_state_ledger(report)
    output = capsys.readouterr().out

    assert "STATE LEDGER" in output
    assert "Order Events" in output
    assert "TARGET_RECORDED" in output
    assert "OPEN: 2" in output
    assert "PENDING" in output


def test_status_healthy_when_positive(state):
    """Positive equity with recent data → HEALTHY."""
    # Use recent timestamps so the staleness check doesn't trigger DEGRADED
    now = datetime.now(timezone.utc)
    for i, eq in enumerate([0.0, 0.01, 0.02]):
        ts = (now - timedelta(hours=(2 - i) * 4)).isoformat()
        state.conn.execute(
            """INSERT INTO equity_snapshots
               (timestamp, total_equity_pct, open_positions, realized_pnl_pct, unrealized_pnl_pct, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ts, eq, 0, eq, 0.0, ""),
        )
    state.conn.commit()

    report = generate_report(state, min_sharpe=1.0, surviving_pairs_path="/nonexistent/path.json")
    assert report.status == "HEALTHY"


def test_status_failing_on_large_drawdown(state):
    """Max DD exceeding 50% → FAILING."""
    # Peak at 0.10, trough at -0.50 → DD = -0.60
    equities = [0.0, 0.10, -0.20, -0.50]
    _inject_snapshots(state, equities)

    report = generate_report(state, min_sharpe=1.0, surviving_pairs_path="/nonexistent/path.json")
    assert report.status == "FAILING"


def test_bars_per_year_auto_detect_4h():
    """4H interval snapshots should detect ~2190 bars/year."""
    curve = []
    base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    for i in range(10):
        ts = (base + timedelta(hours=i * 4)).isoformat()
        curve.append({"timestamp": ts, "total_equity_pct": 0.0})

    bpy = _detect_bars_per_year(curve)
    assert abs(bpy - 2190.0) < 1.0


def test_bars_per_year_auto_detect_1m():
    """1-minute interval snapshots should detect ~525600 bars/year."""
    curve = []
    base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    for i in range(10):
        ts = (base + timedelta(minutes=i)).isoformat()
        curve.append({"timestamp": ts, "total_equity_pct": 0.0})

    bpy = _detect_bars_per_year(curve)
    # 24*60 = 1440 bars/day × 365 = 525,600
    assert abs(bpy - 525600.0) < 100.0


def test_bars_per_year_fallback_insufficient_data():
    """With <2 snapshots, should fall back to 4H assumption."""
    bpy = _detect_bars_per_year([{"timestamp": "2026-01-01T00:00:00+00:00", "total_equity_pct": 0.0}])
    assert abs(bpy - 2190.0) < 1.0

    bpy_empty = _detect_bars_per_year([])
    assert abs(bpy_empty - 2190.0) < 1.0
