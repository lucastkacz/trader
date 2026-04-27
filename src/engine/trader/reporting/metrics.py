"""Portfolio-level report metric calculations."""

import math
from datetime import datetime, timezone
from typing import Any, Optional

from src.core.logger import logger


def _detect_bars_per_year(equity_curve: list[dict[str, Any]]) -> float:
    """Auto-detect annualization factor from equity snapshot intervals."""
    if len(equity_curve) < 2:
        return 6.0 * 365.0

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

    intervals.sort()
    median_hours = intervals[len(intervals) // 2]

    if median_hours <= 0:
        return 6.0 * 365.0

    bars_per_day = 24.0 / median_hours
    bars_per_year = bars_per_day * 365.0

    logger.debug(
        f"Auto-detected bar interval: {median_hours:.1f}h -> "
        f"{bars_per_day:.1f} bars/day -> {bars_per_year:.0f} bars/year"
    )
    return bars_per_year


def _compute_returns(equity_curve: list[dict[str, Any]]) -> list[float]:
    """Extract per-tick returns from the equity curve."""
    if len(equity_curve) < 2:
        return []
    returns = []
    for i in range(1, len(equity_curve)):
        returns.append(
            equity_curve[i]["total_equity_pct"] - equity_curve[i - 1]["total_equity_pct"]
        )
    return returns


def _compute_sharpe(returns: list[float], bars_per_year: float) -> Optional[float]:
    """Compute annualized Sharpe ratio."""
    if len(returns) < 2:
        return None
    mean_r = sum(returns) / len(returns)
    var_r = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
    std_r = math.sqrt(var_r) if var_r > 0 else 0.0
    if std_r == 0:
        return None
    return (mean_r / std_r) * math.sqrt(bars_per_year)


def _compute_sortino(returns: list[float], bars_per_year: float) -> Optional[float]:
    """Compute annualized Sortino ratio."""
    if len(returns) < 2:
        return None
    mean_r = sum(returns) / len(returns)
    neg_returns = [r for r in returns if r < 0]
    if len(neg_returns) < 1:
        return None
    down_var = sum(r ** 2 for r in neg_returns) / len(neg_returns)
    down_std = math.sqrt(down_var) if down_var > 0 else 0.0
    if down_std == 0:
        return None
    return (mean_r / down_std) * math.sqrt(bars_per_year)


def _compute_max_drawdown(equity_curve: list[dict[str, Any]]) -> float:
    """Max peak-to-trough decline in the equity curve."""
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]["total_equity_pct"]
    max_dd = 0.0
    for snap in equity_curve:
        eq = snap["total_equity_pct"]
        if eq > peak:
            peak = eq
        dd = eq - peak
        if dd < max_dd:
            max_dd = dd
    return max_dd


def _compute_calmar(
    equity_curve: list[dict[str, Any]],
    max_dd: float,
    bars_per_year: float,
) -> Optional[float]:
    """Compute Calmar ratio."""
    if not equity_curve or len(equity_curve) < 2 or max_dd == 0.0:
        return None
    total_return = equity_curve[-1]["total_equity_pct"] - equity_curve[0]["total_equity_pct"]
    n_bars = len(equity_curve) - 1
    if n_bars == 0:
        return None
    annualized_return = total_return * (bars_per_year / n_bars)
    return annualized_return / abs(max_dd)


def _compute_trade_stats(closed_trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute win rate, profit factor, expectancy from closed trades."""
    if not closed_trades:
        return {
            "win_rate": 0.0,
            "profit_factor": None,
            "expectancy": 0.0,
            "avg_holding_bars": 0.0,
        }

    wins = [t for t in closed_trades if (t.get("realized_pnl_pct") or 0.0) > 0]
    losses = [t for t in closed_trades if (t.get("realized_pnl_pct") or 0.0) <= 0]

    win_rate = len(wins) / len(closed_trades) if closed_trades else 0.0
    loss_rate = 1.0 - win_rate

    gross_profit = sum(t["realized_pnl_pct"] for t in wins) if wins else 0.0
    gross_loss = abs(sum(t["realized_pnl_pct"] for t in losses)) if losses else 0.0

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


def _compute_uptime_hours(equity_curve: list[dict[str, Any]]) -> float:
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
    equity_curve: list[dict[str, Any]],
) -> str:
    """Determine system health status."""
    _ = uptime_hours
    if max_dd < -0.50:
        return "FAILING"

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
