"""
Ghost Report Engine
====================
Pure computation module for institutional-grade reporting.
Reads the SQLite database via GhostStateManager → returns a GhostReport dataclass
with all metrics pre-computed. No terminal printing, no file I/O formatting.

ARCHITECTURAL RULE: This module does math. Formatting belongs in scripts/ghost_report.py.
"""

import json
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from src.core.logger import logger


# ─── Data Classes ────────────────────────────────────────────────

@dataclass
class PairMetrics:
    """Per-pair performance breakdown."""
    pair_label: str
    asset_x: str
    asset_y: str
    realized_pnl: float
    unrealized_pnl: float
    trade_count: int
    win_rate: float
    avg_pnl_per_trade: float
    avg_holding_bars: float
    current_status: str                # FLAT / LONG_SPREAD / SHORT_SPREAD
    current_z_score: Optional[float]
    backtest_sharpe: Optional[float]
    backtest_pnl: Optional[float]
    live_vs_backtest: str              # ALIGNED / DIVERGING / INSUFFICIENT_DATA


@dataclass
class SignalQuality:
    """Signal predictive accuracy metrics."""
    signal_accuracy: float             # % entries → positive PnL
    avg_entry_z: float
    avg_exit_z: Optional[float]
    false_signal_rate: float
    total_signals_recorded: int


@dataclass
class RiskSnapshot:
    """Current risk state of the portfolio."""
    portfolio_heat: float              # sum of abs unrealized exposure
    largest_single_loss: float
    days_since_last_trade: float
    consecutive_losses: int
    data_freshness: str                # timestamp of latest snapshot


@dataclass
class GhostReport:
    """Complete report output — every metric the system can produce."""
    # Executive Summary
    total_equity_pct: float
    realized_pnl_pct: float
    unrealized_pnl_pct: float
    active_pairs: int
    total_trades: int
    uptime_hours: float
    status: str                        # HEALTHY / DEGRADED / FAILING

    # Portfolio Metrics
    sharpe_ratio: Optional[float]
    sortino_ratio: Optional[float]
    max_drawdown_pct: float
    calmar_ratio: Optional[float]
    win_rate: float
    profit_factor: Optional[float]
    expectancy: float
    avg_holding_bars: float
    trades_per_week: float

    # Breakdowns
    per_pair: List[PairMetrics]
    signal_quality: SignalQuality
    risk: RiskSnapshot

    # Backtest comparison
    backtest_avg_sharpe: Optional[float]
    backtest_avg_pnl: Optional[float]

    # Trade log
    trade_log: List[Dict[str, Any]]

    # Equity curve data
    equity_curve: List[Dict[str, Any]]

    # Meta
    report_timestamp: str
    db_path: str
    bars_per_year: float               # Auto-detected annualization factor

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-safe dictionary."""
        d = asdict(self)
        return d


# ─── Annualization Detection ─────────────────────────────────────

def _detect_bars_per_year(equity_curve: List[Dict[str, Any]]) -> float:
    """
    Auto-detect the annualization factor from equity snapshot intervals.
    Instead of hardcoding 4H (6 bars/day × 365), we measure the median
    inter-snapshot interval and derive bars_per_year dynamically.

    Fallback: 6 × 365 = 2190 (assumes 4H bars).
    """
    if len(equity_curve) < 2:
        return 6.0 * 365.0  # Default 4H assumption

    intervals = []
    for i in range(1, len(equity_curve)):
        try:
            t0 = datetime.fromisoformat(
                equity_curve[i - 1]["timestamp"].replace("Z", "+00:00")
            )
            t1 = datetime.fromisoformat(
                equity_curve[i]["timestamp"].replace("Z", "+00:00")
            )
            delta_hours = (t1 - t0).total_seconds() / 3600.0
            if delta_hours > 0:
                intervals.append(delta_hours)
        except (ValueError, KeyError):
            continue

    if not intervals:
        return 6.0 * 365.0

    # Use median to be robust against outliers (e.g. downtime gaps)
    intervals.sort()
    median_hours = intervals[len(intervals) // 2]

    # bars_per_day = 24 / median_hours, bars_per_year = bars_per_day * 365
    if median_hours <= 0:
        return 6.0 * 365.0

    bars_per_day = 24.0 / median_hours
    bars_per_year = bars_per_day * 365.0

    logger.debug(
        f"Auto-detected bar interval: {median_hours:.1f}h → "
        f"{bars_per_day:.1f} bars/day → {bars_per_year:.0f} bars/year"
    )
    return bars_per_year


# ─── Core Metric Computations ────────────────────────────────────

def _compute_returns(equity_curve: List[Dict[str, Any]]) -> List[float]:
    """Extract per-tick returns from the equity curve (first-difference)."""
    if len(equity_curve) < 2:
        return []
    returns = []
    for i in range(1, len(equity_curve)):
        r = equity_curve[i]["total_equity_pct"] - equity_curve[i - 1]["total_equity_pct"]
        returns.append(r)
    return returns


def _compute_sharpe(returns: List[float], bars_per_year: float) -> Optional[float]:
    """Annualized Sharpe Ratio = mean(r) / std(r) × sqrt(bars_per_year)."""
    if len(returns) < 2:
        return None
    mean_r = sum(returns) / len(returns)
    var_r = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
    std_r = math.sqrt(var_r) if var_r > 0 else 0.0
    if std_r == 0:
        return None
    return (mean_r / std_r) * math.sqrt(bars_per_year)


def _compute_sortino(returns: List[float], bars_per_year: float) -> Optional[float]:
    """Annualized Sortino Ratio = mean(r) / downside_std(r) × sqrt(bars_per_year)."""
    if len(returns) < 2:
        return None
    mean_r = sum(returns) / len(returns)
    neg_returns = [r for r in returns if r < 0]
    if len(neg_returns) < 1:
        return None  # No downside — infinite Sortino is not meaningful
    down_var = sum(r ** 2 for r in neg_returns) / len(neg_returns)
    down_std = math.sqrt(down_var) if down_var > 0 else 0.0
    if down_std == 0:
        return None
    return (mean_r / down_std) * math.sqrt(bars_per_year)


def _compute_max_drawdown(equity_curve: List[Dict[str, Any]]) -> float:
    """Max peak-to-trough decline in the equity curve (as a percentage)."""
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]["total_equity_pct"]
    max_dd = 0.0
    for snap in equity_curve:
        eq = snap["total_equity_pct"]
        if eq > peak:
            peak = eq
        dd = eq - peak  # Will be negative or zero
        if dd < max_dd:
            max_dd = dd
    return max_dd


def _compute_calmar(
    equity_curve: List[Dict[str, Any]],
    max_dd: float,
    bars_per_year: float,
) -> Optional[float]:
    """Calmar Ratio = Annualized Return / |Max Drawdown|."""
    if not equity_curve or len(equity_curve) < 2 or max_dd == 0.0:
        return None
    total_return = equity_curve[-1]["total_equity_pct"] - equity_curve[0]["total_equity_pct"]
    n_bars = len(equity_curve) - 1
    if n_bars == 0:
        return None
    annualized_return = total_return * (bars_per_year / n_bars)
    return annualized_return / abs(max_dd)


def _compute_trade_stats(closed_trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute win rate, profit factor, expectancy from closed trades."""
    if not closed_trades:
        return {
            "win_rate": 0.0,
            "profit_factor": None,
            "expectancy": 0.0,
            "avg_holding_bars": 0.0,
        }

    wins = [t for t in closed_trades if (t.get("pnl_pct") or 0.0) > 0]
    losses = [t for t in closed_trades if (t.get("pnl_pct") or 0.0) <= 0]

    win_rate = len(wins) / len(closed_trades) if closed_trades else 0.0
    loss_rate = 1.0 - win_rate

    gross_profit = sum(t["pnl_pct"] for t in wins) if wins else 0.0
    gross_loss = abs(sum(t["pnl_pct"] for t in losses)) if losses else 0.0

    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None

    avg_win = (gross_profit / len(wins)) if wins else 0.0
    avg_loss = (gross_loss / len(losses)) if losses else 0.0
    expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)

    holding_bars = [t.get("holding_bars") or 0 for t in closed_trades]
    avg_holding = sum(holding_bars) / len(holding_bars) if holding_bars else 0.0

    return {
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "avg_holding_bars": avg_holding,
    }


def _compute_uptime_hours(equity_curve: List[Dict[str, Any]]) -> float:
    """Total hours from first snapshot to last."""
    if len(equity_curve) < 2:
        return 0.0
    try:
        t0 = datetime.fromisoformat(equity_curve[0]["timestamp"].replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(equity_curve[-1]["timestamp"].replace("Z", "+00:00"))
        return (t1 - t0).total_seconds() / 3600.0
    except (ValueError, KeyError):
        return 0.0


def _compute_trades_per_week(total_trades: int, uptime_hours: float) -> float:
    """Trades per week based on uptime."""
    if uptime_hours <= 0:
        return 0.0
    weeks = uptime_hours / (24.0 * 7.0)
    return total_trades / weeks if weeks > 0 else 0.0


def _determine_status(
    total_equity_pct: float,
    max_dd: float,
    uptime_hours: float,
    equity_curve: List[Dict[str, Any]],
) -> str:
    """
    Determine system health status.
    HEALTHY: positive equity, no anomalies
    DEGRADED: negative equity or stale data (>48h gap to now)
    FAILING: max DD exceeds 50%
    """
    if max_dd < -0.50:
        return "FAILING"

    # Check data freshness — is the latest snapshot more than 48h old?
    if equity_curve:
        try:
            latest = datetime.fromisoformat(
                equity_curve[-1]["timestamp"].replace("Z", "+00:00")
            )
            now = datetime.now(timezone.utc)
            hours_stale = (now - latest).total_seconds() / 3600.0
            if hours_stale > 48:
                return "DEGRADED"
        except (ValueError, KeyError):
            pass

    if total_equity_pct < 0:
        return "DEGRADED"

    return "HEALTHY"


# ─── Per-Pair Breakdown ──────────────────────────────────────────

def _compute_per_pair(
    all_orders: List[Dict[str, Any]],
    open_positions: List[Dict[str, Any]],
    tick_signals: List[Dict[str, Any]],
    backtest_lookup: Dict[str, Dict[str, Any]],
) -> List[PairMetrics]:
    """Build per-pair metrics from orders, positions, and backtest data."""
    # Group closed trades by pair
    pair_trades = {}  # type: Dict[str, List[Dict[str, Any]]]
    for order in all_orders:
        label = order["pair_label"]
        if label not in pair_trades:
            pair_trades[label] = []
        if order["status"] == "CLOSED":
            pair_trades[label].append(order)

    # Also track all unique pairs (including those with no closed trades yet)
    all_labels = set(pair_trades.keys())
    for pos in open_positions:
        all_labels.add(pos["pair_label"])
    for order in all_orders:
        all_labels.add(order["pair_label"])

    # Build latest z_score per pair from tick_signals
    latest_z = {}  # type: Dict[str, float]
    for sig in tick_signals:
        latest_z[sig["pair_label"]] = sig["z_score"]

    # Open position lookup
    open_lookup = {}  # type: Dict[str, Dict[str, Any]]
    for pos in open_positions:
        open_lookup[pos["pair_label"]] = pos

    results = []
    for label in sorted(all_labels):
        closed = pair_trades.get(label, [])
        wins = [t for t in closed if (t.get("pnl_pct") or 0.0) > 0]
        trade_count = len(closed)
        realized = sum(t.get("pnl_pct") or 0.0 for t in closed)

        # Current position state
        open_pos = open_lookup.get(label)
        current_status = open_pos["side"] if open_pos else "FLAT"

        # Unrealized PnL — we don't have current prices here, so use 0 if FLAT
        unrealized = 0.0  # Will be populated from equity snapshot per_pair_pnl if available

        # Win rate
        wr = len(wins) / trade_count if trade_count > 0 else 0.0

        # Avg PnL
        avg_pnl = realized / trade_count if trade_count > 0 else 0.0

        # Avg holding bars
        bars_list = [t.get("holding_bars") or 0 for t in closed if t.get("holding_bars")]
        avg_bars = sum(bars_list) / len(bars_list) if bars_list else 0.0

        # Z-score
        z = latest_z.get(label)

        # Backtest comparison
        bt = backtest_lookup.get(label)
        bt_sharpe = bt["Performance"]["sharpe_ratio"] if bt else None
        bt_pnl = bt["Performance"]["final_pnl_pct"] if bt else None

        # Live vs backtest alignment
        if trade_count < 3:
            alignment = "INSUFFICIENT_DATA"
        elif bt_pnl is not None:
            # If live PnL direction matches backtest, ALIGNED
            if (realized >= 0 and bt_pnl >= 0) or (realized < 0 and bt_pnl < 0):
                alignment = "ALIGNED"
            else:
                alignment = "DIVERGING"
        else:
            alignment = "INSUFFICIENT_DATA"

        # Extract asset names from label or first order
        asset_x = ""
        asset_y = ""
        for order in all_orders:
            if order["pair_label"] == label:
                asset_x = order.get("asset_x", "")
                asset_y = order.get("asset_y", "")
                break

        results.append(PairMetrics(
            pair_label=label,
            asset_x=asset_x,
            asset_y=asset_y,
            realized_pnl=realized,
            unrealized_pnl=unrealized,
            trade_count=trade_count,
            win_rate=wr,
            avg_pnl_per_trade=avg_pnl,
            avg_holding_bars=avg_bars,
            current_status=current_status,
            current_z_score=z,
            backtest_sharpe=bt_sharpe,
            backtest_pnl=bt_pnl,
            live_vs_backtest=alignment,
        ))

    return results


# ─── Signal Quality ──────────────────────────────────────────────

def _compute_signal_quality(
    closed_trades: List[Dict[str, Any]],
    tick_signals: List[Dict[str, Any]],
) -> SignalQuality:
    """Compute signal predictive accuracy metrics."""
    total_signals = len(tick_signals)

    if not closed_trades:
        return SignalQuality(
            signal_accuracy=0.0,
            avg_entry_z=0.0,
            avg_exit_z=None,
            false_signal_rate=0.0,
            total_signals_recorded=total_signals,
        )

    wins = [t for t in closed_trades if (t.get("pnl_pct") or 0.0) > 0]
    signal_accuracy = len(wins) / len(closed_trades) if closed_trades else 0.0

    # Average entry Z-score (absolute)
    entry_zs = [abs(t.get("entry_z") or 0.0) for t in closed_trades]
    avg_entry_z = sum(entry_zs) / len(entry_zs) if entry_zs else 0.0

    # Average exit Z-score (absolute) — may be None for pre-migration trades
    exit_zs = [abs(t["exit_z"]) for t in closed_trades if t.get("exit_z") is not None]
    avg_exit_z = sum(exit_zs) / len(exit_zs) if exit_zs else None

    # False signal rate: entries where PnL was negative (spread diverged further)
    false_signals = len(closed_trades) - len(wins)
    false_signal_rate = false_signals / len(closed_trades) if closed_trades else 0.0

    return SignalQuality(
        signal_accuracy=signal_accuracy,
        avg_entry_z=avg_entry_z,
        avg_exit_z=avg_exit_z,
        false_signal_rate=false_signal_rate,
        total_signals_recorded=total_signals,
    )


# ─── Risk Snapshot ───────────────────────────────────────────────

def _compute_risk(
    open_positions: List[Dict[str, Any]],
    closed_trades: List[Dict[str, Any]],
    equity_curve: List[Dict[str, Any]],
) -> RiskSnapshot:
    """Compute current risk state."""
    # Portfolio heat: sum of absolute unrealized exposure from latest snapshot
    portfolio_heat = 0.0
    if equity_curve:
        latest = equity_curve[-1]
        per_pair_raw = latest.get("per_pair_pnl")
        if per_pair_raw:
            try:
                per_pair = json.loads(per_pair_raw)
                portfolio_heat = sum(abs(v) for v in per_pair.values())
            except (json.JSONDecodeError, TypeError):
                pass

    # Largest single unrealized loss
    largest_loss = 0.0
    if equity_curve:
        latest = equity_curve[-1]
        per_pair_raw = latest.get("per_pair_pnl")
        if per_pair_raw:
            try:
                per_pair = json.loads(per_pair_raw)
                if per_pair:
                    largest_loss = min(per_pair.values())
            except (json.JSONDecodeError, TypeError):
                pass

    # Days since last trade
    days_since = 0.0
    if closed_trades:
        try:
            last_close = datetime.fromisoformat(
                closed_trades[-1]["timestamp_close"].replace("Z", "+00:00")
            )
            days_since = (datetime.now(timezone.utc) - last_close).total_seconds() / 86400.0
        except (ValueError, KeyError, TypeError, AttributeError):
            pass

    # Consecutive losses (trailing streak)
    consecutive_losses = 0
    for trade in reversed(closed_trades):
        if (trade.get("pnl_pct") or 0.0) <= 0:
            consecutive_losses += 1
        else:
            break

    # Data freshness
    freshness = "N/A"
    if equity_curve:
        freshness = equity_curve[-1].get("timestamp", "N/A")

    return RiskSnapshot(
        portfolio_heat=portfolio_heat,
        largest_single_loss=largest_loss,
        days_since_last_trade=days_since,
        consecutive_losses=consecutive_losses,
        data_freshness=freshness,
    )


# ─── Backtest Lookup ─────────────────────────────────────────────

def _load_backtest_lookup(surviving_pairs_path: str) -> Dict[str, Dict[str, Any]]:
    """
    Load surviving_pairs.json and build a lookup dict keyed by pair_label.
    Pair label format: "ASSET_X|ASSET_Y" (e.g. "MET/USDT|LTC/USDT").
    """
    try:
        with open(surviving_pairs_path, "r") as f:
            pairs = json.load(f)
    except FileNotFoundError:
        logger.warning(f"Backtest file not found: {surviving_pairs_path}")
        return {}

    lookup = {}
    for p in pairs:
        label = f"{p['Asset_X']}|{p['Asset_Y']}"
        lookup[label] = p
    return lookup


# ─── Main Entry Point ────────────────────────────────────────────

def generate_report(
    state: "GhostStateManager",
    surviving_pairs_path: str = "data/universes/surviving_pairs.json",
) -> GhostReport:
    """
    Generate a complete report from the current database state.

    Parameters
    ----------
    state : GhostStateManager — connected to the target database
    surviving_pairs_path : str — path to backtest results for comparison

    Returns
    -------
    GhostReport dataclass with all metrics computed.
    """
    # Gather raw data
    all_orders = state.get_all_orders()
    closed_trades = state.get_all_closed()
    open_positions = state.get_open_positions()
    equity_curve = state.get_equity_curve()
    tick_signals = state.get_tick_signals()
    backtest_lookup = _load_backtest_lookup(surviving_pairs_path)

    # Auto-detect annualization factor
    bars_per_year = _detect_bars_per_year(equity_curve)

    # Equity
    realized = sum(t.get("pnl_pct") or 0.0 for t in closed_trades)
    unrealized = 0.0
    if equity_curve:
        unrealized = equity_curve[-1].get("unrealized_pnl_pct", 0.0)
    total_equity = realized + unrealized

    # Returns and ratio metrics
    returns = _compute_returns(equity_curve)
    sharpe = _compute_sharpe(returns, bars_per_year)
    sortino = _compute_sortino(returns, bars_per_year)
    max_dd = _compute_max_drawdown(equity_curve)
    calmar = _compute_calmar(equity_curve, max_dd, bars_per_year)

    # Trade stats
    trade_stats = _compute_trade_stats(closed_trades)
    uptime = _compute_uptime_hours(equity_curve)
    tpw = _compute_trades_per_week(len(closed_trades), uptime)

    # Status
    status = _determine_status(total_equity, max_dd, uptime, equity_curve)

    # Per-pair
    per_pair = _compute_per_pair(all_orders, open_positions, tick_signals, backtest_lookup)

    # Signal quality
    sig_quality = _compute_signal_quality(closed_trades, tick_signals)

    # Risk
    risk = _compute_risk(open_positions, closed_trades, equity_curve)

    # Backtest averages (Tier 1 only)
    from src.core.config import settings as cfg
    tier1_bt = [
        v for v in backtest_lookup.values()
        if v["Performance"]["sharpe_ratio"] >= cfg.ghost_min_sharpe
    ]
    bt_avg_sharpe = (
        sum(p["Performance"]["sharpe_ratio"] for p in tier1_bt) / len(tier1_bt)
        if tier1_bt else None
    )
    bt_avg_pnl = (
        sum(p["Performance"]["final_pnl_pct"] for p in tier1_bt) / len(tier1_bt)
        if tier1_bt else None
    )

    return GhostReport(
        # Executive Summary
        total_equity_pct=total_equity,
        realized_pnl_pct=realized,
        unrealized_pnl_pct=unrealized,
        active_pairs=len(open_positions),
        total_trades=len(closed_trades),
        uptime_hours=uptime,
        status=status,
        # Portfolio Metrics
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        max_drawdown_pct=max_dd,
        calmar_ratio=calmar,
        win_rate=trade_stats["win_rate"],
        profit_factor=trade_stats["profit_factor"],
        expectancy=trade_stats["expectancy"],
        avg_holding_bars=trade_stats["avg_holding_bars"],
        trades_per_week=tpw,
        # Breakdowns
        per_pair=per_pair,
        signal_quality=sig_quality,
        risk=risk,
        # Backtest
        backtest_avg_sharpe=bt_avg_sharpe,
        backtest_avg_pnl=bt_avg_pnl,
        # Trade log
        trade_log=[dict(t) for t in closed_trades],
        # Equity curve
        equity_curve=[dict(s) for s in equity_curve],
        # Meta
        report_timestamp=datetime.now(timezone.utc).isoformat(),
        db_path=state.db_path,
        bars_per_year=bars_per_year,
    )
