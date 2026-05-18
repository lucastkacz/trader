"""Compatibility facade for Telegram message and keyboard renderers."""

from src.interfaces.telegram.rendering.formatting import (
    format_age_minutes,
    format_artifact_pct,
    format_duration,
    format_leg_statuses,
    format_pct,
    format_price,
    format_z,
    holding_duration_minutes,
)
from src.interfaces.telegram.rendering.menu import (
    build_menu_section_keyboard,
    build_operator_menu_keyboard,
    build_stop_all_confirmation_keyboard,
    render_menu_section,
    render_operator_menu,
)
from src.interfaces.telegram.rendering.pairs import (
    pair_label,
    render_promoted_pairs,
)
from src.interfaces.telegram.rendering.positions import (
    build_position_action_keyboard,
    build_position_select_keyboard,
    render_position_action_menu,
    render_position_inspection,
)
from src.interfaces.telegram.rendering.runtime import render_run_status

__all__ = [
    "build_menu_section_keyboard",
    "build_operator_menu_keyboard",
    "build_position_action_keyboard",
    "build_position_select_keyboard",
    "build_stop_all_confirmation_keyboard",
    "format_age_minutes",
    "format_artifact_pct",
    "format_duration",
    "format_leg_statuses",
    "format_pct",
    "format_price",
    "format_z",
    "holding_duration_minutes",
    "pair_label",
    "render_menu_section",
    "render_operator_menu",
    "render_position_action_menu",
    "render_position_inspection",
    "render_promoted_pairs",
    "render_run_status",
]
