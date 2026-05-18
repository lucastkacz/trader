"""Shared Telegram formatting helpers."""

from datetime import datetime, timezone


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


def format_age_minutes(value: float | None) -> str:
    """Format an age in minutes for operator messages."""
    if value is None:
        return "N/A"
    if value < 60:
        return f"{value:.1f}m"
    return f"{value / 60.0:.1f}h"


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
