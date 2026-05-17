"""Telegram message and keyboard renderers for operator commands."""

import html
from datetime import datetime, timezone
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.engine.trader.reporting.position_inspector import PositionInspection
from src.engine.trader.runtime.pairs import validate_pair_artifact_file


def holding_duration_minutes(position: dict, holding_period_bar_minutes: float) -> float:
    """Return display duration in minutes using explicit Telegram bar policy."""
    holding_bars = position.get("holding_bars")
    if holding_bars:
        return holding_bars * holding_period_bar_minutes

    opened_at = position.get("opened_at")
    if not opened_at:
        return 0.0

    try:
        t_open = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return 0.0
    return max(0.0, (datetime.now(timezone.utc) - t_open).total_seconds() / 60.0)


def format_duration(minutes: float) -> str:
    """Format a holding duration for compact Telegram display."""
    if minutes < 60:
        return f"{minutes:.0f}m"
    return f"{minutes / 60.0:g}h"


def format_pct(value: float | None) -> str:
    """Format a decimal percentage for Telegram display."""
    if value is None:
        return "N/A"
    return f"{value * 100:+.2f}%"


def format_price(value: float | None) -> str:
    """Format an asset price for compact Telegram display."""
    if value is None:
        return "N/A"
    return f"{value:.6g}"


def format_z(value: float | None) -> str:
    """Format a z-score for compact Telegram display."""
    if value is None:
        return "N/A"
    return f"{value:.2f}"


def format_artifact_pct(value: float | None) -> str:
    """Format a generated artifact percent value without rescaling."""
    if value is None:
        return "N/A"
    return f"{value:+.2f}%"


def format_leg_statuses(status_counts: dict[str, dict[str, int]]) -> str:
    """Format leg lifecycle counts by role."""
    if not status_counts:
        return "none"
    parts = []
    for role, counts in status_counts.items():
        summary = ", ".join(f"{status} x{count}" for status, count in counts.items())
        parts.append(f"{role}: {summary}")
    return "\n".join(parts)


def render_position_inspection(
    inspection: PositionInspection,
    holding_period_bar_minutes: float,
) -> str:
    """Render one position inspection snapshot as a Telegram HTML message."""
    position = inspection.position
    latest = inspection.latest_signal or {}
    duration = format_duration(
        holding_duration_minutes(position, holding_period_bar_minutes)
    )
    mark_label = "Latest Recorded Mark" if inspection.latest_signal else "Latest Recorded Mark"
    current_price_a = latest.get("price_a")
    current_price_b = latest.get("price_b")

    return (
        f"🔎 <b>POSITION INSPECTOR #{position['id']}</b>\n"
        f"Pair: <b>{position['pair_label']}</b>\n"
        f"Side: {position['side']}\n"
        f"Opened: {position['opened_at']}\n"
        f"Duration: {duration}\n\n"
        f"<b>Entry</b>\n"
        f"{position['asset_x']}: {format_price(position['entry_price_a'])}\n"
        f"{position['asset_y']}: {format_price(position['entry_price_b'])}\n"
        f"Entry Z: {format_z(position['entry_z'])}\n"
        f"Weights: {position['weight_a']:.2f} / {position['weight_b']:.2f}\n"
        f"Lookback: {position['lookback_bars']} bars\n\n"
        f"<b>{mark_label}</b>\n"
        f"{position['asset_x']}: {format_price(current_price_a)}\n"
        f"{position['asset_y']}: {format_price(current_price_b)}\n"
        f"Z-Score: {format_z(latest.get('z_score'))}\n"
        f"Signal: {latest.get('signal', 'N/A')}\n"
        f"Action: {latest.get('action', 'N/A')}\n"
        f"Signal Time: {latest.get('timestamp', 'N/A')}\n\n"
        f"<b>PnL</b>\n"
        f"Unrealized: {format_pct(inspection.unrealized_pnl)}\n\n"
        f"<b>Execution State</b>\n"
        f"{format_leg_statuses(inspection.leg_status_counts)}\n"
        f"Exchange/client IDs present: {'YES' if inspection.has_exchange_identifiers else 'NO'}"
    )


def build_position_inspect_keyboard(open_positions: list[dict]) -> InlineKeyboardMarkup:
    """Build one-tap inspection buttons for the current open positions."""
    rows = [
        [
            InlineKeyboardButton(
                text=f"Inspect #{position['id']}",
                callback_data=f"inspect_position:{position['id']}",
            )
        ]
        for position in open_positions
    ]
    return InlineKeyboardMarkup(rows)


def pair_label(pair: dict) -> str:
    return f"{pair['Asset_X']}|{pair['Asset_Y']}"


def render_promoted_pairs(path: Path, environment: str | None) -> str:
    """Render the promoted pair artifact as a compact Telegram HTML message."""
    artifact = validate_pair_artifact_file(path)
    metadata = artifact.metadata

    if not artifact.pairs:
        return (
            "📭 <b>PROMOTED PAIRS</b>\n"
            f"Mode: {html.escape(environment or 'N/A')}\n"
            f"Artifact: <code>{html.escape(str(path))}</code>\n\n"
            "No promoted pairs found."
        )

    lines = [
        "🧾 <b>PROMOTED PAIRS</b>",
        f"Mode: {html.escape(environment or 'N/A')}",
        f"Artifact: <code>{html.escape(str(path))}</code>",
        (
            f"Scope: {html.escape(metadata.exchange)} "
            f"{html.escape(metadata.timeframe)} | Count: {metadata.pair_count}"
        ),
        f"Generated: {metadata.generated_at.isoformat()}",
        "",
    ]
    for index, pair in enumerate(artifact.pairs, start=1):
        best_params = pair["Best_Params"]
        performance = pair["Performance"]
        label = html.escape(pair_label(pair))
        sharpe = performance.get("sharpe_ratio")
        final_pnl_pct = performance.get("final_pnl_pct")
        lines.extend(
            [
                f"{index}. <b>{label}</b>",
                (
                    f"   Sharpe: {sharpe:.2f} | PnL: "
                    f"{format_artifact_pct(final_pnl_pct)}"
                ),
                (
                    f"   Entry Z: {best_params['entry_z']:.2f} | "
                    f"Lookback: {best_params['lookback_bars']} bars"
                ),
            ]
        )
    return "\n".join(lines)
