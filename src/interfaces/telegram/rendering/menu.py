"""Telegram menu renderers and keyboards."""

import html

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def render_operator_menu(environment: str | None) -> str:
    """Render the top-level Telegram operator menu."""
    return (
        "🤖 <b>STAT-ARB CONTROLLER</b>\n"
        f"Mode: {html.escape(environment or 'N/A')}\n\n"
        "Choose an operator area:"
    )


def build_operator_menu_keyboard() -> InlineKeyboardMarkup:
    """Build the main operator menu tree."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Runtime", callback_data="menu:runtime"),
                InlineKeyboardButton("Positions", callback_data="menu:positions"),
            ],
            [
                InlineKeyboardButton("Pairs", callback_data="menu:pairs"),
                InlineKeyboardButton("Reports", callback_data="menu:reports"),
            ],
            [InlineKeyboardButton("Controls", callback_data="menu:controls")],
        ]
    )


def render_menu_section(section: str) -> str:
    """Render one second-level menu section."""
    titles = {
        "runtime": "RUNTIME",
        "positions": "POSITIONS",
        "pairs": "PAIRS",
        "reports": "REPORTS",
        "controls": "CONTROLS",
    }
    title = titles.get(section, "MENU")
    return f"🧭 <b>{title}</b>\nChoose a view or action:"


def build_menu_section_keyboard(section: str) -> InlineKeyboardMarkup:
    """Build second-level menu buttons for one operator area."""
    rows_by_section = {
        "runtime": [
            [
                InlineKeyboardButton("Status", callback_data="menu:status"),
                InlineKeyboardButton("Health", callback_data="menu:health"),
            ],
            [InlineKeyboardButton("Run Status", callback_data="menu:run_status")],
        ],
        "positions": [
            [InlineKeyboardButton("Open Positions", callback_data="menu:positions_open")],
        ],
        "pairs": [
            [InlineKeyboardButton("Promoted Pairs", callback_data="menu:promoted_pairs")],
        ],
        "reports": [
            [InlineKeyboardButton("Run Status + JSON Check", callback_data="menu:run_status")],
        ],
        "controls": [
            [
                InlineKeyboardButton("Pause", callback_data="menu:pause"),
                InlineKeyboardButton("Resume", callback_data="menu:resume"),
            ],
            [InlineKeyboardButton("Stop All", callback_data="menu:stop_all_confirm")],
        ],
    }
    rows = rows_by_section.get(section, [])
    rows.append([InlineKeyboardButton("Back", callback_data="menu:main")])
    return InlineKeyboardMarkup(rows)


def build_stop_all_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Build a deliberate confirmation step for the broad stop command."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Confirm Stop All",
                    callback_data="menu:stop_all_execute",
                ),
            ],
            [InlineKeyboardButton("Back", callback_data="menu:controls")],
        ]
    )
