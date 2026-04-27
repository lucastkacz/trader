"""Risk snapshot report metrics."""

import json
from datetime import datetime, timezone
from typing import Any

from src.engine.trader.reporting.models import RiskSnapshot


def _compute_risk(
    open_positions: list[dict[str, Any]],
    closed_trades: list[dict[str, Any]],
    equity_curve: list[dict[str, Any]],
) -> RiskSnapshot:
    """Compute current risk state."""
    _ = open_positions
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

    days_since = 0.0
    if closed_trades:
        try:
            last_close = datetime.fromisoformat(
                closed_trades[-1]["closed_at"].replace("Z", "+00:00")
            )
            days_since = (datetime.now(timezone.utc) - last_close).total_seconds() / 86400.0
        except (ValueError, KeyError, TypeError, AttributeError):
            pass

    consecutive_losses = 0
    for trade in reversed(closed_trades):
        if (trade.get("realized_pnl_pct") or 0.0) <= 0:
            consecutive_losses += 1
        else:
            break

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
