"""Signal transition routing for one pair during a trader tick."""

from typing import Any

from src.engine.trader.config import OrderExecutionConfig
from src.engine.trader.execution.orders import (
    OrderExecutionAdapter,
    execute_spread_leg_orders,
)
from src.engine.trader.state_manager import TradeStateManager
from src.interfaces.telegram.notifier import TelegramNotifier


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
) -> None:
    """Apply the local state and explicit order transition for a signal result."""
    if current_side is None and result.signal != "FLAT":
        await _open_spread(pair, pair_label, result, lookback_bars, state, notifier, order_execution_cfg, order_execution_adapter)
    elif current_side is not None and result.signal == "FLAT":
        await _close_spread(pair_label, result, timeframe, state, notifier, order_execution_cfg, order_execution_adapter)
    elif current_side is not None and result.signal != current_side:
        await _flip_spread(pair, pair_label, result, lookback_bars, timeframe, state, notifier, order_execution_cfg, order_execution_adapter)


async def _open_spread(
    pair: dict[str, Any],
    pair_label: str,
    result: Any,
    lookback_bars: int,
    state: TradeStateManager,
    notifier: TelegramNotifier,
    order_execution_cfg: OrderExecutionConfig,
    order_execution_adapter: OrderExecutionAdapter | None,
) -> None:
    spread_id = state.open_position(
        pair_label=pair_label,
        asset_x=pair["Asset_X"],
        asset_y=pair["Asset_Y"],
        side=result.signal,
        entry_price_a=result.price_a,
        entry_price_b=result.price_b,
        weight_a=result.weight_a,
        weight_b=result.weight_b,
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
        f"• PNL: <b>{pnl*100:.2f}%</b> if pnl else 'N/A'\n"
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
        weight_a=result.weight_a,
        weight_b=result.weight_b,
        entry_z=result.z_score,
        lookback_bars=lookback_bars,
    )
    await _execute_leg_orders(state, new_spread_id, "OPEN", order_execution_cfg, order_execution_adapter)
    await notifier.send(
        f"🔄 <b>FLIP SIGNAL: {pair_label}</b>\n"
        f"• Old Side Closed | PNL: <b>{pnl*100:.2f}%</b> if pnl else 'N/A'\n"
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
