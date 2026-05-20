"""Telegram-ready plot generation for operator diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
import os
from pathlib import Path
import tempfile
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.engine.trader.execution.pnl import calculate_position_pnl
from src.engine.trader.state.manager import TradeStateManager
from src.interfaces.telegram.renderers import format_pct, format_z


class PlotError(ValueError):
    """Base class for operator plot build failures."""


class PlotDependencyError(RuntimeError):
    """Raised when the local environment cannot render plots."""


@dataclass(frozen=True)
class PositionZScorePlot:
    position: dict[str, Any]
    signals: list[dict[str, Any]]
    timestamps: list[datetime]
    pnl_values: list[float]

    @property
    def latest_signal(self) -> dict[str, Any]:
        return self.signals[-1]

    @property
    def is_closed(self) -> bool:
        return self.position["status"] == "CLOSED"


def build_position_plot_keyboard(position_id: int) -> InlineKeyboardMarkup:
    """Build a one-tap refresh button for a plot message."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=f"Refresh Plot #{position_id}",
                    callback_data=f"plot_position:{position_id}",
                )
            ]
        ]
    )


def build_position_zscore_plot(
    state: TradeStateManager,
    identifier: str,
) -> PositionZScorePlot:
    """Return filtered z-score and PnL data for one position."""
    position = _find_position(state.get_all_orders(), identifier)
    if position is None:
        raise PlotError(f"No position found for {identifier}. Use /positions for open IDs.")

    signals = _position_signals(
        state.get_tick_signals(position["pair_label"]),
        position,
    )
    if not signals:
        raise PlotError(
            f"No tick signal history found for position #{position['id']}."
        )

    return PositionZScorePlot(
        position=position,
        signals=signals,
        timestamps=[_parse_timestamp(signal["timestamp"]) for signal in signals],
        pnl_values=[
            calculate_position_pnl(
                position=position,
                current_a=signal["price_a"],
                current_b=signal["price_b"],
            )
            for signal in signals
        ],
    )


def render_position_zscore_plot_png(plot: PositionZScorePlot) -> bytes:
    """Render a position z-score plot as PNG bytes."""
    _configure_matplotlib_cache()
    try:
        import matplotlib

        matplotlib.use("Agg", force=True)
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise PlotDependencyError(
            "Plotting requires matplotlib. Install project requirements and retry."
        ) from exc

    position = plot.position
    z_scores = [signal["z_score"] for signal in plot.signals]
    entry_time = _parse_timestamp(position["opened_at"])

    fig, axes = plt.subplots(
        2,
        1,
        figsize=(10, 6),
        sharex=True,
        gridspec_kw={"height_ratios": [2.2, 1.0]},
        constrained_layout=True,
    )
    fig.patch.set_facecolor("white")
    z_axis, pnl_axis = axes

    z_axis.plot(
        plot.timestamps,
        z_scores,
        color="#2563eb",
        linewidth=2.0,
        marker="o",
        markersize=3.0,
        label="Z-score",
    )
    z_axis.axhline(
        0.0,
        color="#16a34a",
        linestyle="--",
        linewidth=1.2,
        label="Mean / exit guide",
    )
    z_axis.axhline(
        position["entry_z"],
        color="#dc2626",
        linestyle=":",
        linewidth=1.2,
        label=f"Entry Z {position['entry_z']:.2f}",
    )
    z_axis.scatter(
        [entry_time],
        [position["entry_z"]],
        color="#dc2626",
        s=70,
        zorder=5,
        label="Entry",
    )
    if position.get("closed_at") and position.get("exit_z") is not None:
        z_axis.scatter(
            [_parse_timestamp(position["closed_at"])],
            [position["exit_z"]],
            color="#111827",
            marker="X",
            s=90,
            zorder=6,
            label="Exit",
        )

    z_axis.set_title(
        f"Position #{position['id']} {position['pair_label']} ({position['side']})",
        fontsize=12,
        fontweight="bold",
    )
    z_axis.set_ylabel("Z-score")
    z_axis.grid(True, alpha=0.25)
    z_axis.legend(loc="best", fontsize=8)

    pnl_axis.plot(
        plot.timestamps,
        [value * 100.0 for value in plot.pnl_values],
        color="#0f766e",
        linewidth=1.8,
        marker="o",
        markersize=2.8,
    )
    pnl_axis.axhline(0.0, color="#6b7280", linestyle="--", linewidth=1.0)
    pnl_axis.set_ylabel("PnL %")
    pnl_axis.grid(True, alpha=0.25)
    pnl_axis.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    pnl_axis.set_xlabel("UTC time")

    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    return buffer.getvalue()


def render_position_plot_caption(plot: PositionZScorePlot) -> str:
    """Render compact HTML caption for a z-score plot."""
    position = plot.position
    latest = plot.latest_signal
    latest_pnl = plot.pnl_values[-1]
    pnl_label = "Realized" if plot.is_closed else "Unrealized"
    return (
        f"<b>Z-SCORE PLOT #{position['id']}</b>\n"
        f"Pair: <b>{position['pair_label']}</b>\n"
        f"Status: {position['status']} {position['side']}\n"
        f"Signals: {len(plot.signals)}\n"
        f"Entry Z: {format_z(position['entry_z'])} | "
        f"Latest Z: {format_z(latest['z_score'])}\n"
        f"{pnl_label}: {format_pct(latest_pnl)}\n"
        f"Latest Signal: {latest['timestamp']}"
    )


def _find_position(
    positions: list[dict[str, Any]],
    identifier: str,
) -> dict[str, Any] | None:
    normalized = identifier.strip().upper()
    if not normalized:
        return None

    for position in positions:
        if str(position["id"]) == normalized:
            return position

    pair_matches = [
        position for position in positions
        if position["pair_label"].upper() == normalized
    ]
    if not pair_matches:
        return None

    open_matches = [
        position for position in pair_matches
        if position["status"] == "OPEN"
    ]
    if len(open_matches) == 1:
        return open_matches[0]

    return sorted(pair_matches, key=lambda item: item["opened_at"])[-1]


def _position_signals(
    signals: list[dict[str, Any]],
    position: dict[str, Any],
) -> list[dict[str, Any]]:
    opened_at = _parse_timestamp(position["opened_at"])
    closed_at = (
        _parse_timestamp(position["closed_at"])
        if position.get("closed_at")
        else None
    )
    filtered = []
    for signal in signals:
        timestamp = _parse_timestamp(signal["timestamp"])
        if timestamp < opened_at:
            continue
        if closed_at is not None and timestamp > closed_at:
            continue
        filtered.append(signal)
    return filtered


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _configure_matplotlib_cache() -> None:
    if "MPLCONFIGDIR" in os.environ:
        return
    cache_dir = Path(tempfile.gettempdir()) / "quant-matplotlib"
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(cache_dir)
