"""Signal transition routing for one pair during a trader tick."""

from typing import Any

from src.engine.trader.config import OrderExecutionConfig
from src.engine.trader.execution.orders import (
    OrderExecutionAdapter,
    execute_spread_leg_orders,
)
from src.engine.trader.runtime.risk import (
    PreTradeLiquiditySnapshot,
    PreTradeRiskDecision,
    PreTradeRiskPolicy,
    evaluate_pre_trade_entry,
    get_risk_kill_switch_state,
)
from src.engine.trader.state.manager import TradeStateManager
from src.interfaces.telegram.notifier import TelegramNotifier


def determine_action(current_side: str | None, new_signal: str) -> str:
    """Determine state-transition action from current side and new signal."""
    if current_side is None:
        if new_signal == "FLAT":
            return "SKIP"
        return "ENTRY"

    if new_signal == "FLAT":
        return "EXIT"
    if new_signal == current_side:
        return "HOLD"
    return "FLIP"


def _format_pnl_percent(pnl: float | None) -> str:
    if pnl is None:
        return "N/A"
    return f"{pnl * 100:.2f}%"


async def route_signal_transition(
    pair: dict[str, Any],
    pair_label: str,
    current_side: str | None,
    result: Any,
    lookback_bars: int,
    timeframe: str,
    state: TradeStateManager,
    notifier: TelegramNotifier,
    order_execution_cfg: OrderExecutionConfig,
    order_execution_adapter: OrderExecutionAdapter | None,
    allow_new_entry: bool = True,
    entry_block_reasons: list[str] | None = None,
    pre_trade_risk_policy: PreTradeRiskPolicy | None = None,
    pre_trade_liquidity_snapshot: PreTradeLiquiditySnapshot | None = None,
) -> None:
    """Apply the local state and explicit order transition for a signal result."""
    if current_side is None and result.signal != "FLAT":
        if allow_new_entry:
            decision = _evaluate_pre_trade_risk(
                result=result,
                state=state,
                policy=pre_trade_risk_policy,
                liquidity=pre_trade_liquidity_snapshot,
            )
            if decision.entry_allowed:
                await _open_spread(
                    pair,
                    pair_label,
                    result,
                    lookback_bars,
                    state,
                    notifier,
                    order_execution_cfg,
                    order_execution_adapter,
                    pre_trade_decision=decision,
                )
            else:
                await _notify_pre_trade_risk_blocked(pair_label, notifier, decision)
        else:
            await _notify_entry_blocked(pair_label, notifier, entry_block_reasons)
    elif current_side is not None and result.signal == "FLAT":
        await _close_spread(pair_label, result, timeframe, state, notifier, order_execution_cfg, order_execution_adapter)
    elif current_side is not None and result.signal != current_side:
        if allow_new_entry:
            decision = _evaluate_pre_trade_risk(
                result=result,
                state=state,
                policy=pre_trade_risk_policy,
                replacing_pair_label=pair_label,
                liquidity=pre_trade_liquidity_snapshot,
            )
            if decision.entry_allowed:
                await _flip_spread(
                    pair,
                    pair_label,
                    result,
                    lookback_bars,
                    timeframe,
                    state,
                    notifier,
                    order_execution_cfg,
                    order_execution_adapter,
                    pre_trade_decision=decision,
                )
            else:
                await _close_spread(pair_label, result, timeframe, state, notifier, order_execution_cfg, order_execution_adapter)
                await _notify_pre_trade_risk_blocked(pair_label, notifier, decision)
        else:
            await _close_spread(pair_label, result, timeframe, state, notifier, order_execution_cfg, order_execution_adapter)
            await _notify_entry_blocked(pair_label, notifier, entry_block_reasons)


async def _open_spread(
    pair: dict[str, Any],
    pair_label: str,
    result: Any,
    lookback_bars: int,
    state: TradeStateManager,
    notifier: TelegramNotifier,
    order_execution_cfg: OrderExecutionConfig,
    order_execution_adapter: OrderExecutionAdapter | None,
    pre_trade_decision: PreTradeRiskDecision,
) -> None:
    spread_id = state.open_position(
        pair_label=pair_label,
        asset_x=pair["Asset_X"],
        asset_y=pair["Asset_Y"],
        side=result.signal,
        entry_price_a=result.price_a,
        entry_price_b=result.price_b,
        weight_a=pre_trade_decision.sized_weight_a,
        weight_b=pre_trade_decision.sized_weight_b,
        entry_z=result.z_score,
        lookback_bars=lookback_bars,
    )
    await _execute_leg_orders(state, spread_id, "OPEN", order_execution_cfg, order_execution_adapter)
    await notifier.send(
        f"🚀 <b>ENTRY SIGNAL: {pair_label}</b>\n"
        f"• Z-Score: {result.z_score:.2f}\n"
        f"• Action: {result.signal}"
    )


async def _close_spread(
    pair_label: str,
    result: Any,
    timeframe: str,
    state: TradeStateManager,
    notifier: TelegramNotifier,
    order_execution_cfg: OrderExecutionConfig,
    order_execution_adapter: OrderExecutionAdapter | None,
) -> None:
    spread_id = state.get_position_for_pair(pair_label)["id"]
    pnl = state.close_position(
        pair_label=pair_label,
        exit_price_a=result.price_a,
        exit_price_b=result.price_b,
        timeframe=timeframe,
        exit_z=result.z_score,
    )
    await _execute_leg_orders(state, spread_id, "CLOSE", order_execution_cfg, order_execution_adapter)
    await notifier.send(
        f"🏁 <b>EXIT SIGNAL: {pair_label}</b>\n"
        f"• Z-Score: {result.z_score:.2f}\n"
        f"• PNL: <b>{_format_pnl_percent(pnl)}</b>\n"
        f"• Action: CLOSE Spread"
    )


async def _flip_spread(
    pair: dict[str, Any],
    pair_label: str,
    result: Any,
    lookback_bars: int,
    timeframe: str,
    state: TradeStateManager,
    notifier: TelegramNotifier,
    order_execution_cfg: OrderExecutionConfig,
    order_execution_adapter: OrderExecutionAdapter | None,
    pre_trade_decision: PreTradeRiskDecision,
) -> None:
    closing_spread_id = state.get_position_for_pair(pair_label)["id"]
    pnl = state.close_position(
        pair_label=pair_label,
        exit_price_a=result.price_a,
        exit_price_b=result.price_b,
        timeframe=timeframe,
        exit_z=result.z_score,
    )
    await _execute_leg_orders(state, closing_spread_id, "CLOSE", order_execution_cfg, order_execution_adapter)
    new_spread_id = state.open_position(
        pair_label=pair_label,
        asset_x=pair["Asset_X"],
        asset_y=pair["Asset_Y"],
        side=result.signal,
        entry_price_a=result.price_a,
        entry_price_b=result.price_b,
        weight_a=pre_trade_decision.sized_weight_a,
        weight_b=pre_trade_decision.sized_weight_b,
        entry_z=result.z_score,
        lookback_bars=lookback_bars,
    )
    await _execute_leg_orders(state, new_spread_id, "OPEN", order_execution_cfg, order_execution_adapter)
    await notifier.send(
        f"🔄 <b>FLIP SIGNAL: {pair_label}</b>\n"
        f"• Old Side Closed | PNL: <b>{_format_pnl_percent(pnl)}</b>\n"
        f"• New Side: {result.signal}\n"
        f"• Z-Score: {result.z_score:.2f}"
    )


async def _execute_leg_orders(
    state: TradeStateManager,
    spread_id: int,
    leg_role: str,
    order_execution_cfg: OrderExecutionConfig,
    order_execution_adapter: OrderExecutionAdapter | None,
) -> None:
    await execute_spread_leg_orders(
        state=state,
        spread_id=spread_id,
        leg_role=leg_role,
        config=order_execution_cfg,
        adapter=order_execution_adapter,
    )


async def _notify_entry_blocked(
    pair_label: str,
    notifier: TelegramNotifier,
    block_reasons: list[str] | None,
) -> None:
    reasons = ", ".join(block_reasons or ["dynamic_pair_queue_blocked_entry"])
    await notifier.send(
        f"⛔ <b>ENTRY BLOCKED BY PAIR QUEUE:</b> {pair_label}\n"
        f"Reasons: {reasons}"
    )


def _evaluate_pre_trade_risk(
    *,
    result: Any,
    state: TradeStateManager,
    policy: PreTradeRiskPolicy | None,
    replacing_pair_label: str | None = None,
    liquidity: PreTradeLiquiditySnapshot | None = None,
) -> PreTradeRiskDecision:
    if policy is None:
        notional = abs(float(result.weight_a)) + abs(float(result.weight_b))
        kill_switch = get_risk_kill_switch_state(state)
        return PreTradeRiskDecision(
            entry_allowed=not kill_switch.active,
            block_reasons=["risk_kill_switch_active"] if kill_switch.active else [],
            sized_weight_a=float(result.weight_a),
            sized_weight_b=float(result.weight_b),
            proposed_notional_pct=notional,
            projected_portfolio_exposure=notional,
            projected_leverage=notional,
        )
    return evaluate_pre_trade_entry(
        result=result,
        open_positions=state.get_open_positions(),
        policy=policy,
        replacing_pair_label=replacing_pair_label,
        liquidity=liquidity,
        kill_switch=get_risk_kill_switch_state(state),
    )


async def _notify_pre_trade_risk_blocked(
    pair_label: str,
    notifier: TelegramNotifier,
    decision: PreTradeRiskDecision,
) -> None:
    reasons = ", ".join(decision.block_reasons or ["pre_trade_risk_blocked_entry"])
    await notifier.send(
        f"⛔ <b>ENTRY BLOCKED BY PRE-TRADE RISK:</b> {pair_label}\n"
        f"Reasons: {reasons}\n"
        f"Proposed Notional: {decision.proposed_notional_pct:.4f}\n"
        f"Projected Exposure: {decision.projected_portfolio_exposure:.4f}"
    )
