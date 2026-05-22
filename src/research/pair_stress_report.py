"""Traceable report artifacts for offline pair stress filtering."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.engine.trader.runtime.artifacts.lifecycle import pair_artifact_dir

PAIR_STRESS_REPORT_FILENAME = "pair_stress_report.json"


def pair_stress_report_path(timeframe: str, base_dir: str | Path) -> Path:
    """Return the research-written stress trace report path."""
    return pair_artifact_dir(timeframe, base_dir) / PAIR_STRESS_REPORT_FILENAME


def write_pair_stress_report(
    report_rows: list[dict[str, Any]],
    timeframe: str,
    exchange: str,
    base_dir: str | Path,
) -> Path:
    """Atomically write the latest pair stress trace report."""
    path = pair_stress_report_path(timeframe, base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    artifact = {
        "metadata": {
            "artifact_type": "pair_stress_report",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "timeframe": timeframe,
            "exchange": exchange,
            "pair_count": len(report_rows),
        },
        "pairs": report_rows,
    }
    tmp_path.write_text(json.dumps(artifact, indent=4), encoding="utf-8")
    os.replace(tmp_path, path)
    return path


def build_rejected_pair_report(
    pair: dict[str, Any],
    reason: str,
    source_window: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a stress report row for a rejected pair."""
    return {
        "pair": _pair_label(pair),
        "asset_x": pair["Asset_X"],
        "asset_y": pair["Asset_Y"],
        "hedge_ratio": pair["Hedge_Ratio"],
        "source_data_window": source_window,
        "status": "rejected",
        "rejection_reasons": [reason],
        "stress_params": [],
        "entries_exits": [],
        "summary": None,
    }


def build_surviving_pair_report(
    pair: dict[str, Any],
    source_window: dict[str, Any],
    stress_params: dict[str, Any],
    net_df: pd.DataFrame,
) -> dict[str, Any]:
    """Build a stress report row for the best surviving parameter set."""
    gross_return = float(net_df["gross_returns"].sum())
    net_return = float(net_df["net_returns"].sum())
    fee_drag = float(net_df["fee_drag"].sum()) if "fee_drag" in net_df.columns else 0.0
    funding_drag = float(net_df["funding_drag"].sum()) if "funding_drag" in net_df.columns else 0.0
    return {
        "pair": _pair_label(pair),
        "asset_x": pair["Asset_X"],
        "asset_y": pair["Asset_Y"],
        "hedge_ratio": pair["Hedge_Ratio"],
        "source_data_window": source_window,
        "status": "survived",
        "rejection_reasons": [],
        "stress_params": [stress_params],
        "entries_exits": extract_entries_exits(net_df),
        "summary": {
            "gross_return": gross_return,
            "net_return": net_return,
            "fee_drag": fee_drag,
            "funding_drag": funding_drag,
        },
    }


def extract_source_window(unified: pd.DataFrame) -> dict[str, Any]:
    """Summarize the aligned source data window used for a pair."""
    index = unified.index
    return {
        "start": _json_value(index.min()) if len(index) else None,
        "end": _json_value(index.max()) if len(index) else None,
        "bars": int(len(unified)),
    }


def extract_entries_exits(net_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Extract trade intervals from a simulated position series."""
    trades: list[dict[str, Any]] = []
    open_trade: dict[str, Any] | None = None
    previous_position = 0.0

    for row_index, row in net_df.reset_index(drop=True).iterrows():
        position = float(row["position"])
        if previous_position == 0.0 and position != 0.0:
            open_trade = _open_trade(row, position, row_index)
        elif previous_position != 0.0 and position == 0.0 and open_trade is not None:
            trades.append(_close_trade(open_trade, row, net_df.iloc[open_trade["_entry_index"]:row_index + 1]))
            open_trade = None
        elif previous_position != 0.0 and position != previous_position and open_trade is not None:
            trades.append(_close_trade(open_trade, row, net_df.iloc[open_trade["_entry_index"]:row_index + 1]))
            open_trade = _open_trade(row, position, row_index)
        previous_position = position

    if open_trade is not None and len(net_df) > 0:
        trades.append(_close_trade(open_trade, net_df.iloc[-1], net_df.iloc[open_trade["_entry_index"]:], forced=True))
    return trades


def _open_trade(row: pd.Series, position: float, row_index: int) -> dict[str, Any]:
    return {
        "_entry_index": row_index,
        "entry_timestamp": _json_value(row.get("timestamp")),
        "side": "LONG_SPREAD" if position > 0 else "SHORT_SPREAD",
        "entry_z_score": _finite_float(row.get("z_score")),
        "gross_return": 0.0,
        "net_return": 0.0,
        "fee_drag": 0.0,
    }


def _close_trade(
    open_trade: dict[str, Any],
    row: pd.Series,
    trade_slice: pd.DataFrame,
    forced: bool = False,
) -> dict[str, Any]:
    closed = {key: value for key, value in open_trade.items() if not key.startswith("_")}
    closed.update({
        "exit_timestamp": _json_value(row.get("timestamp")),
        "exit_z_score": _finite_float(row.get("z_score")),
        "gross_return": _finite_float(trade_slice["gross_returns"].sum()),
        "net_return": _finite_float(trade_slice["net_returns"].sum()),
        "fee_drag": _finite_float(trade_slice["fee_drag"].sum()) if "fee_drag" in trade_slice.columns else 0.0,
        "funding_drag": (
            _finite_float(trade_slice["funding_drag"].sum()) if "funding_drag" in trade_slice.columns else 0.0
        ),
        "forced_end_of_sample": forced,
    })
    return closed


def _pair_label(pair: dict[str, Any]) -> str:
    return f"{pair['Asset_X']}|{pair['Asset_Y']}"


def _finite_float(value: Any) -> float:
    if value is None or not np.isfinite(value):
        return 0.0
    return float(value)


def _json_value(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value
