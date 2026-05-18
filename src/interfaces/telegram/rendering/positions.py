"""Telegram position inspection renderers and keyboards."""

import html

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.engine.trader.reporting.position_inspector import PositionInspection
from src.interfaces.telegram.rendering.formatting import (
    format_duration,
    format_leg_statuses,
    format_pct,
    format_price,
    format_z,
    holding_duration_minutes,
)


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


def build_position_select_keyboard(open_positions: list[dict]) -> InlineKeyboardMarkup:
    """Build first-step position selector buttons."""
    rows = [
        [
            InlineKeyboardButton(
                text=f"Position #{position['id']}",
                callback_data=f"position_menu:{position['id']}",
            )
        ]
        for position in open_positions
    ]
    return InlineKeyboardMarkup(rows)


def build_position_action_keyboard(position_id: int | str) -> InlineKeyboardMarkup:
    """Build second-step view choices for one selected position."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="Summary",
                    callback_data=f"inspect_position:{position_id}",
                ),
                InlineKeyboardButton(
                    text="Plot",
                    callback_data=f"plot_position:{position_id}",
                ),
            ]
        ]
    )


def render_position_action_menu(position: dict) -> str:
    """Render the second-step position action prompt."""
    return (
        f"📌 <b>POSITION #{position['id']}</b>\n"
        f"Pair: <b>{html.escape(position['pair_label'])}</b>\n"
        f"Side: {html.escape(position['side'])}\n\n"
        "Choose a view:"
    )
