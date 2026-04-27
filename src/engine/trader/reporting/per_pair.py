"""Per-pair report metrics."""

from typing import Any

from src.engine.trader.reporting.models import PairMetrics


def _compute_per_pair(
    all_orders: list[dict[str, Any]],
    open_positions: list[dict[str, Any]],
    tick_signals: list[dict[str, Any]],
    backtest_lookup: dict[str, dict[str, Any]],
) -> list[PairMetrics]:
    """Build per-pair metrics from orders, positions, and backtest data."""
    pair_trades: dict[str, list[dict[str, Any]]] = {}
    for order in all_orders:
        label = order["pair_label"]
        if label not in pair_trades:
            pair_trades[label] = []
        if order["status"] == "CLOSED":
            pair_trades[label].append(order)

    all_labels = set(pair_trades.keys())
    for pos in open_positions:
        all_labels.add(pos["pair_label"])
    for order in all_orders:
        all_labels.add(order["pair_label"])

    latest_z: dict[str, float] = {}
    for sig in tick_signals:
        latest_z[sig["pair_label"]] = sig["z_score"]

    open_lookup: dict[str, dict[str, Any]] = {}
    for pos in open_positions:
        open_lookup[pos["pair_label"]] = pos

    results = []
    for label in sorted(all_labels):
        closed = pair_trades.get(label, [])
        wins = [t for t in closed if (t.get("realized_pnl_pct") or 0.0) > 0]
        trade_count = len(closed)
        realized = sum(t.get("realized_pnl_pct") or 0.0 for t in closed)

        open_pos = open_lookup.get(label)
        current_status = open_pos["side"] if open_pos else "FLAT"
        unrealized = 0.0

        wr = len(wins) / trade_count if trade_count > 0 else 0.0
        avg_pnl = realized / trade_count if trade_count > 0 else 0.0

        bars_list = [t.get("holding_bars") or 0 for t in closed if t.get("holding_bars")]
        avg_bars = sum(bars_list) / len(bars_list) if bars_list else 0.0

        z = latest_z.get(label)

        bt = backtest_lookup.get(label)
        bt_sharpe = bt["Performance"]["sharpe_ratio"] if bt else None
        bt_pnl = bt["Performance"]["final_pnl_pct"] if bt else None

        if trade_count < 3:
            alignment = "INSUFFICIENT_DATA"
        elif bt_pnl is not None:
            if (realized >= 0 and bt_pnl >= 0) or (realized < 0 and bt_pnl < 0):
                alignment = "ALIGNED"
            else:
                alignment = "DIVERGING"
        else:
            alignment = "INSUFFICIENT_DATA"

        asset_x = ""
        asset_y = ""
        for order in all_orders:
            if order["pair_label"] == label:
                asset_x = order.get("asset_x", "")
                asset_y = order.get("asset_y", "")
                break

        results.append(PairMetrics(
            pair_label=label,
            asset_x=asset_x,
            asset_y=asset_y,
            realized_pnl=realized,
            unrealized_pnl=unrealized,
            trade_count=trade_count,
            win_rate=wr,
            avg_pnl_per_trade=avg_pnl,
            avg_holding_bars=avg_bars,
            current_status=current_status,
            current_z_score=z,
            backtest_sharpe=bt_sharpe,
            backtest_pnl=bt_pnl,
            live_vs_backtest=alignment,
        ))

    return results
