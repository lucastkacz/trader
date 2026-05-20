"""Top-level report assembly."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from src.engine.trader.reporting.backtest_lookup import (
    _load_backtest_lookup,
    _load_backtest_timeframe,
)
from src.engine.trader.reporting.metrics import (
    _compute_calmar,
    _compute_max_drawdown,
    _compute_returns,
    _compute_sharpe,
    _compute_sortino,
    _compute_trade_stats,
    _compute_trades_per_week,
    _compute_uptime_hours,
    _detect_bars_per_year,
    _determine_status,
)
from src.engine.trader.reporting.models import TradeReport
from src.engine.trader.reporting.per_pair import _compute_per_pair
from src.engine.trader.reporting.risk import _compute_risk
from src.engine.trader.reporting.signal_quality import _compute_signal_quality
from src.engine.trader.reporting.state_ledger import _compute_state_ledger
from src.engine.trader.runtime.pair_queue import (
    OpenPositionExposure,
    PairQueueOpportunity,
    PairQueuePolicy,
    PairQueueSnapshot,
    build_pair_queue_snapshot,
)
from src.engine.trader.runtime.pair_validity import build_pair_validity_report
from src.engine.trader.runtime.pair_validity.models import (
    PairValidityConfig,
    PairValidityReport,
)
from src.utils.timeframe_math import get_bars_per_year

if TYPE_CHECKING:
    from src.engine.trader.state.manager import TradeStateManager


def generate_report(
    state: "TradeStateManager",
    min_sharpe: float,
    surviving_pairs_path: str,
    market_data_base_dir: str | None = None,
    pair_validity_config: PairValidityConfig | None = None,
    pair_queue_policy: PairQueuePolicy | None = None,
    pair_queue_enabled: bool = True,
) -> TradeReport:
    """Generate a complete report from the current database state."""
    all_orders = state.get_all_orders()
    closed_trades = state.get_all_closed()
    open_positions = state.get_open_positions()
    equity_curve = state.get_equity_curve()
    tick_signals = state.get_tick_signals()
    order_events = state.get_order_events()
    leg_fills = state.get_leg_fills()
    user_commands = state.get_commands()
    reconciliation_runs = state.get_reconciliation_runs()
    reconciliation_deltas = state.get_reconciliation_deltas()
    backtest_lookup = _load_backtest_lookup(surviving_pairs_path)
    artifact_timeframe = _load_backtest_timeframe(surviving_pairs_path)

    if artifact_timeframe is not None:
        bars_per_year = float(get_bars_per_year(artifact_timeframe))
    else:
        bars_per_year = _detect_bars_per_year(equity_curve)

    realized = sum(t.get("realized_pnl_pct") or 0.0 for t in closed_trades)
    unrealized = 0.0
    if equity_curve:
        unrealized = equity_curve[-1].get("unrealized_pnl_pct", 0.0)
    total_equity = realized + unrealized

    returns = _compute_returns(equity_curve)
    sharpe = _compute_sharpe(returns, bars_per_year)
    sortino = _compute_sortino(returns, bars_per_year)
    max_dd = _compute_max_drawdown(equity_curve)
    calmar = _compute_calmar(equity_curve, max_dd, bars_per_year)

    trade_stats = _compute_trade_stats(closed_trades)
    uptime = _compute_uptime_hours(equity_curve)
    tpw = _compute_trades_per_week(len(closed_trades), uptime)

    status = _determine_status(total_equity, max_dd, uptime, equity_curve)
    per_pair = _compute_per_pair(all_orders, open_positions, tick_signals, backtest_lookup)
    sig_quality = _compute_signal_quality(closed_trades, tick_signals)
    risk = _compute_risk(open_positions, closed_trades, equity_curve)
    state_ledger = _compute_state_ledger(
        order_events=order_events,
        leg_fills=leg_fills,
        user_commands=user_commands,
        reconciliation_runs=reconciliation_runs,
        reconciliation_deltas=reconciliation_deltas,
    )
    pair_validity = _compute_pair_validity_report(
        state=state,
        surviving_pairs_path=surviving_pairs_path,
        market_data_base_dir=market_data_base_dir,
        pair_validity_config=pair_validity_config,
    )
    pair_queue = _compute_pair_queue_snapshot(
        promoted_pairs=list(backtest_lookup.values()),
        pair_validity=pair_validity,
        tick_signals=tick_signals,
        open_positions=open_positions,
        policy=pair_queue_policy,
        enabled=pair_queue_enabled,
    )

    bt_avg_sharpe, bt_avg_pnl = _compute_backtest_averages(
        backtest_lookup=backtest_lookup,
        min_sharpe=min_sharpe,
    )

    return TradeReport(
        total_equity_pct=total_equity,
        realized_pnl_pct=realized,
        unrealized_pnl_pct=unrealized,
        active_pairs=len(open_positions),
        total_trades=len(closed_trades),
        uptime_hours=uptime,
        status=status,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        max_drawdown_pct=max_dd,
        calmar_ratio=calmar,
        win_rate=trade_stats["win_rate"],
        profit_factor=trade_stats["profit_factor"],
        expectancy=trade_stats["expectancy"],
        avg_holding_bars=trade_stats["avg_holding_bars"],
        trades_per_week=tpw,
        per_pair=per_pair,
        signal_quality=sig_quality,
        risk=risk,
        state_ledger=state_ledger,
        pair_validity=pair_validity,
        pair_queue=pair_queue,
        backtest_avg_sharpe=bt_avg_sharpe,
        backtest_avg_pnl=bt_avg_pnl,
        trade_log=[dict(t) for t in closed_trades],
        equity_curve=[dict(s) for s in equity_curve],
        report_timestamp=datetime.now(timezone.utc).isoformat(),
        db_path=state.db_path,
        bars_per_year=bars_per_year,
    )


def _compute_backtest_averages(
    backtest_lookup: dict[str, dict[str, Any]],
    min_sharpe: float,
) -> tuple[float | None, float | None]:
    tier1_bt = [
        v for v in backtest_lookup.values()
        if v["Performance"]["sharpe_ratio"] >= min_sharpe
    ]
    bt_avg_sharpe = (
        sum(p["Performance"]["sharpe_ratio"] for p in tier1_bt) / len(tier1_bt)
        if tier1_bt else None
    )
    bt_avg_pnl = (
        sum(p["Performance"]["final_pnl_pct"] for p in tier1_bt) / len(tier1_bt)
        if tier1_bt else None
    )
    return bt_avg_sharpe, bt_avg_pnl


def _compute_pair_validity_report(
    *,
    state: "TradeStateManager",
    surviving_pairs_path: str,
    market_data_base_dir: str | None,
    pair_validity_config: PairValidityConfig | None,
) -> PairValidityReport | None:
    if market_data_base_dir is None or pair_validity_config is None:
        return None

    try:
        return build_pair_validity_report(
            surviving_pairs_path=surviving_pairs_path,
            market_data_base_dir=market_data_base_dir,
            state=state,
            config=pair_validity_config,
        )
    except Exception as exc:
        return PairValidityReport(
            artifact_path=surviving_pairs_path,
            timeframe="unknown",
            exchange="unknown",
            pair_count=0,
            snapshots=[],
            notes=[f"pair_validity_unavailable: {exc}"],
        )


def _compute_pair_queue_snapshot(
    *,
    promoted_pairs: list[dict[str, Any]],
    pair_validity: PairValidityReport | None,
    tick_signals: list[dict[str, Any]],
    open_positions: list[dict[str, Any]],
    policy: PairQueuePolicy | None,
    enabled: bool,
) -> PairQueueSnapshot | None:
    if not enabled or pair_validity is None or not promoted_pairs:
        return None
    return build_pair_queue_snapshot(
        promoted_pairs=promoted_pairs,
        validity_snapshots=pair_validity.snapshots,
        opportunities=_latest_opportunities(
            tick_signals=tick_signals,
            promoted_pairs=promoted_pairs,
        ),
        open_positions=[
            OpenPositionExposure(
                pair_label=str(position["pair_label"]),
                asset_x=str(position["asset_x"]),
                asset_y=str(position["asset_y"]),
                position_id=int(position["id"]) if position.get("id") is not None else None,
            )
            for position in open_positions
        ],
        policy=policy or PairQueuePolicy(),
    )


def _latest_opportunities(
    *,
    tick_signals: list[dict[str, Any]],
    promoted_pairs: list[dict[str, Any]],
) -> dict[str, PairQueueOpportunity]:
    entry_z_by_pair = {
        f"{pair['Asset_X']}|{pair['Asset_Y']}": float(pair["Best_Params"]["entry_z"])
        for pair in promoted_pairs
        if "Best_Params" in pair and "entry_z" in pair["Best_Params"]
    }
    latest_by_pair: dict[str, dict[str, Any]] = {}
    for signal in tick_signals:
        pair_label = str(signal["pair_label"])
        previous = latest_by_pair.get(pair_label)
        if previous is None or str(signal["timestamp"]) >= str(previous["timestamp"]):
            latest_by_pair[pair_label] = signal

    return {
        pair_label: _opportunity_from_signal(
            signal=signal,
            entry_z=entry_z_by_pair.get(pair_label),
        )
        for pair_label, signal in latest_by_pair.items()
    }


def _opportunity_from_signal(
    *,
    signal: dict[str, Any],
    entry_z: float | None,
) -> PairQueueOpportunity:
    action = str(signal["action"])
    z_score = float(signal["z_score"])
    entry_signal = action in {"ENTRY", "FLIP"}
    if entry_signal:
        score = 1.0
    elif entry_z is not None and entry_z > 0:
        score = min(1.0, abs(z_score) / entry_z)
    else:
        score = 0.0
    return PairQueueOpportunity(
        pair_label=str(signal["pair_label"]),
        score=score,
        entry_signal=entry_signal,
        notes=[f"latest_action:{action}", f"latest_z:{z_score:.4f}"],
    )
