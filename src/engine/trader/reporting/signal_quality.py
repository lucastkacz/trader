"""Signal quality report metrics."""

from typing import Any

from src.engine.trader.reporting.models import SignalQuality


def _compute_signal_quality(
    closed_trades: list[dict[str, Any]],
    tick_signals: list[dict[str, Any]],
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

    wins = [t for t in closed_trades if (t.get("realized_pnl_pct") or 0.0) > 0]
    signal_accuracy = len(wins) / len(closed_trades) if closed_trades else 0.0

    entry_zs = [abs(t.get("entry_z") or 0.0) for t in closed_trades]
    avg_entry_z = sum(entry_zs) / len(entry_zs) if entry_zs else 0.0

    exit_zs = [abs(t["exit_z"]) for t in closed_trades if t.get("exit_z") is not None]
    avg_exit_z = sum(exit_zs) / len(exit_zs) if exit_zs else None

    false_signals = len(closed_trades) - len(wins)
    false_signal_rate = false_signals / len(closed_trades) if closed_trades else 0.0

    return SignalQuality(
        signal_accuracy=signal_accuracy,
        avg_entry_z=avg_entry_z,
        avg_exit_z=avg_exit_z,
        false_signal_rate=false_signal_rate,
        total_signals_recorded=total_signals,
    )
