"""
Ghost Trader Report
====================
Diagnostic utility to inspect the state of the ghost trading database.
Run anytime to see open positions, trade log, and equity curve.
"""

import json
from src.core.config import settings
from src.engine.ghost.state_manager import GhostStateManager


def print_header(title: str):
    print(f"\n{'═' * 60}")
    print(f"  {title}")
    print(f"{'═' * 60}")


def run_report():
    state = GhostStateManager()

    # 1. Open Positions
    open_pos = state.get_open_positions()
    print_header(f"OPEN POSITIONS ({len(open_pos)})")

    if not open_pos:
        print("  No open ghost positions.")
    else:
        for pos in open_pos:
            print(
                f"  {pos['pair_label']:<30} | {pos['side']:<14} | "
                f"Entry A={pos['entry_price_a']:.6f} B={pos['entry_price_b']:.6f} | "
                f"Weights: {pos['weight_a']:.4f}/{pos['weight_b']:.4f} | "
                f"Opened: {pos['timestamp_open']}"
            )

    # 2. Trade Log
    closed = state.get_all_closed()
    print_header(f"COMPLETED TRADES ({len(closed)})")

    if not closed:
        print("  No completed trades yet.")
    else:
        total_pnl = 0.0
        wins = 0
        for trade in closed:
            pnl = trade["pnl_pct"] or 0.0
            total_pnl += pnl
            if pnl > 0:
                wins += 1
            marker = "✓" if pnl > 0 else "✗"
            print(
                f"  {marker} {trade['pair_label']:<30} | {trade['side']:<14} | "
                f"PnL: {pnl*100:>+8.4f}% | "
                f"{trade['timestamp_open'][:16]} → {(trade['timestamp_close'] or '?')[:16]}"
            )

        print(f"\n  Total Realized PnL: {total_pnl*100:+.4f}%")
        if closed:
            print(f"  Win Rate: {wins}/{len(closed)} ({wins/len(closed)*100:.1f}%)")

    # 3. Equity Curve
    snapshots = state.get_equity_curve()
    print_header(f"EQUITY CURVE ({len(snapshots)} snapshots)")

    if not snapshots:
        print("  No equity snapshots recorded yet.")
    else:
        # Show last 10 snapshots
        recent = snapshots[-10:]
        for snap in recent:
            print(
                f"  {snap['timestamp'][:19]} | "
                f"Equity: {snap['total_equity_pct']*100:>+8.4f}% | "
                f"Open: {snap['open_positions']} | "
                f"Real: {snap['realized_pnl_pct']*100:>+.4f}% | "
                f"Unreal: {snap['unrealized_pnl_pct']*100:>+.4f}%"
            )
        if len(snapshots) > 10:
            print(f"  ... ({len(snapshots) - 10} earlier snapshots omitted)")

    # 4. Backtest Comparison
    print_header("BACKTEST vs LIVE COMPARISON")
    try:
        with open("data/universes/surviving_pairs.json", "r") as f:
            backtest_pairs = json.load(f)

        min_sharpe = settings.ghost_min_sharpe
        tier1 = [p for p in backtest_pairs if p["Performance"]["sharpe_ratio"] >= min_sharpe]

        bt_avg_pnl = sum(p["Performance"]["final_pnl_pct"] for p in tier1) / len(tier1) if tier1 else 0
        bt_avg_sharpe = sum(p["Performance"]["sharpe_ratio"] for p in tier1) / len(tier1) if tier1 else 0

        live_pnl = sum(t["pnl_pct"] or 0.0 for t in closed) * 100 if closed else 0

        print(f"  Backtest Tier 1 Avg PnL (4yr):  {bt_avg_pnl:+.2f}%")
        print(f"  Backtest Tier 1 Avg Sharpe:     {bt_avg_sharpe:.2f}")
        print(f"  Live Ghost Realized PnL:        {live_pnl:+.4f}%")
        print(f"  Live Ghost Trade Count:         {len(closed)}")

        if snapshots:
            latest = snapshots[-1]
            print(f"  Latest Total Equity:            {latest['total_equity_pct']*100:+.4f}%")
    except FileNotFoundError:
        print("  surviving_pairs.json not found — cannot compare.")

    state.close()
    print()


if __name__ == "__main__":
    run_report()
