"""Telegram promoted-pair renderers."""

import html
from pathlib import Path

from src.engine.trader.runtime.pairs import validate_pair_artifact_file
from src.interfaces.telegram.rendering.formatting import (
    format_artifact_pct,
    format_z,
)


def pair_label(pair: dict) -> str:
    return f"{pair['Asset_X']}|{pair['Asset_Y']}"


def render_promoted_pairs(
    path: Path,
    environment: str | None,
    latest_signals_by_pair: dict[str, dict] | None = None,
) -> str:
    """Render the promoted pair artifact as a compact Telegram HTML message."""
    artifact = validate_pair_artifact_file(path)
    metadata = artifact.metadata
    latest_signals_by_pair = latest_signals_by_pair or {}

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
        latest_signal = latest_signals_by_pair.get(pair_label(pair))
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
                f"   {_render_pair_signal_status(latest_signal, best_params['entry_z'])}",
            ]
        )
    return "\n".join(lines)


def _render_pair_signal_status(
    latest_signal: dict | None,
    entry_z: float,
) -> str:
    if latest_signal is None:
        return "Latest Z: N/A"

    z_score = latest_signal["z_score"]
    threshold = abs(entry_z)
    gap = threshold - abs(z_score)
    if gap <= 0 and z_score <= -threshold:
        proximity = "Entry Zone: LONG"
    elif gap <= 0 and z_score >= threshold:
        proximity = "Entry Zone: SHORT"
    else:
        proximity = f"Entry Gap: {gap:.2f}"

    return (
        f"Latest Z: {format_z(z_score)} | {proximity} | "
        f"Action: {html.escape(latest_signal['action'])}"
    )
