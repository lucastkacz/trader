"""Top-level report assembly."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from src.engine.trader.reporting.backtest_lookup import _load_backtest_lookup
from src.engine.trader.reporting.metrics import (
    _compute_calmar,
    _compute_max_drawdown,
    _compute_returns,
    _compute_sharpe,
    _compute_sortino,
    _compute_trade_stats,
    _compute_trades_per_week,
    _compute_uptime_hours,
    _detect_bars_per_year,
    _determine_status,
)
from src.engine.trader.reporting.models import TradeReport
from src.engine.trader.reporting.per_pair import _compute_per_pair
from src.engine.trader.reporting.risk import _compute_risk
from src.engine.trader.reporting.signal_quality import _compute_signal_quality
from src.engine.trader.reporting.state_ledger import _compute_state_ledger

if TYPE_CHECKING:
    from src.engine.trader.state_manager import TradeStateManager


def generate_report(
    state: "TradeStateManager",
    min_sharpe: float,
    surviving_pairs_path: str,
) -> TradeReport:
    """Generate a complete report from the current database state."""
    all_orders = state.get_all_orders()
    closed_trades = state.get_all_closed()
    open_positions = state.get_open_positions()
    equity_curve = state.get_equity_curve()
    tick_signals = state.get_tick_signals()
    order_events = state.get_order_events()
    leg_fills = state.get_leg_fills()
    user_commands = state.get_commands()
    reconciliation_runs = state.get_reconciliation_runs()
    reconciliation_deltas = state.get_reconciliation_deltas()
    backtest_lookup = _load_backtest_lookup(surviving_pairs_path)

    bars_per_year = _detect_bars_per_year(equity_curve)

    realized = sum(t.get("realized_pnl_pct") or 0.0 for t in closed_trades)
    unrealized = 0.0
    if equity_curve:
        unrealized = equity_curve[-1].get("unrealized_pnl_pct", 0.0)
    total_equity = realized + unrealized

    returns = _compute_returns(equity_curve)
    sharpe = _compute_sharpe(returns, bars_per_year)
    sortino = _compute_sortino(returns, bars_per_year)
    max_dd = _compute_max_drawdown(equity_curve)
    calmar = _compute_calmar(equity_curve, max_dd, bars_per_year)

    trade_stats = _compute_trade_stats(closed_trades)
    uptime = _compute_uptime_hours(equity_curve)
    tpw = _compute_trades_per_week(len(closed_trades), uptime)

    status = _determine_status(total_equity, max_dd, uptime, equity_curve)
    per_pair = _compute_per_pair(all_orders, open_positions, tick_signals, backtest_lookup)
    sig_quality = _compute_signal_quality(closed_trades, tick_signals)
    risk = _compute_risk(open_positions, closed_trades, equity_curve)
    state_ledger = _compute_state_ledger(
        order_events=order_events,
        leg_fills=leg_fills,
        user_commands=user_commands,
        reconciliation_runs=reconciliation_runs,
        reconciliation_deltas=reconciliation_deltas,
    )

    bt_avg_sharpe, bt_avg_pnl = _compute_backtest_averages(
        backtest_lookup=backtest_lookup,
        min_sharpe=min_sharpe,
    )

    return TradeReport(
        total_equity_pct=total_equity,
        realized_pnl_pct=realized,
        unrealized_pnl_pct=unrealized,
        active_pairs=len(open_positions),
        total_trades=len(closed_trades),
        uptime_hours=uptime,
        status=status,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        max_drawdown_pct=max_dd,
        calmar_ratio=calmar,
        win_rate=trade_stats["win_rate"],
        profit_factor=trade_stats["profit_factor"],
        expectancy=trade_stats["expectancy"],
        avg_holding_bars=trade_stats["avg_holding_bars"],
        trades_per_week=tpw,
        per_pair=per_pair,
        signal_quality=sig_quality,
        risk=risk,
        state_ledger=state_ledger,
        backtest_avg_sharpe=bt_avg_sharpe,
        backtest_avg_pnl=bt_avg_pnl,
        trade_log=[dict(t) for t in closed_trades],
        equity_curve=[dict(s) for s in equity_curve],
        report_timestamp=datetime.now(timezone.utc).isoformat(),
        db_path=state.db_path,
        bars_per_year=bars_per_year,
    )


def _compute_backtest_averages(
    backtest_lookup: dict[str, dict[str, Any]],
    min_sharpe: float,
) -> tuple[float | None, float | None]:
    tier1_bt = [
        v for v in backtest_lookup.values()
        if v["Performance"]["sharpe_ratio"] >= min_sharpe
    ]
    bt_avg_sharpe = (
        sum(p["Performance"]["sharpe_ratio"] for p in tier1_bt) / len(tier1_bt)
        if tier1_bt else None
    )
    bt_avg_pnl = (
        sum(p["Performance"]["final_pnl_pct"] for p in tier1_bt) / len(tier1_bt)
        if tier1_bt else None
    )
    return bt_avg_sharpe, bt_avg_pnl
