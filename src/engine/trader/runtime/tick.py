"""Single-tick orchestration for the trader runtime."""

import json
from datetime import datetime, timezone
from typing import Any

from src.core.logger import logger
from src.engine.trader.config import OrderExecutionConfig
from src.engine.trader.execution.market_data import fetch_recent_candles
from src.engine.trader.execution.orders import OrderExecutionAdapter
from src.engine.trader.execution.pnl import calculate_per_pair_pnl, calculate_unrealized_pnl
from src.engine.trader.runtime.actions import determine_action
from src.engine.trader.runtime.signal_transition import route_signal_transition
from src.engine.trader.signal_engine import evaluate_signal
from src.engine.trader.state_manager import TradeStateManager
from src.interfaces.telegram.notifier import TelegramNotifier


async def execute_tick(
    pairs: list[dict[str, Any]],
    state: TradeStateManager,
    notifier: TelegramNotifier,
    timeframe: str,
    strategy_cfg: dict[str, Any],
    exchange_id: str,
    api_key: str,
    api_secret: str,
    order_execution_cfg: OrderExecutionConfig,
    order_execution_adapter: OrderExecutionAdapter | None,
) -> None:
    """Execute one full trader tick across all configured pairs."""
    if state.is_system_paused():
        logger.info("Tick skipped because system is paused.")
        return

    logger.info(f"═══ ENGINE TICK @ {datetime.now(timezone.utc).isoformat()} ═══")
    pair_prices = {}
    for pair in pairs:
        await _process_pair_tick(
            pair=pair,
            pair_prices=pair_prices,
            state=state,
            notifier=notifier,
            timeframe=timeframe,
            strategy_cfg=strategy_cfg,
            exchange_id=exchange_id,
            api_key=api_key,
            api_secret=api_secret,
            order_execution_cfg=order_execution_cfg,
            order_execution_adapter=order_execution_adapter,
        )
    _snapshot_tick_equity(state, pair_prices)


async def _process_pair_tick(
    pair: dict[str, Any],
    pair_prices: dict[str, tuple[float, float]],
    state: TradeStateManager,
    notifier: TelegramNotifier,
    timeframe: str,
    strategy_cfg: dict[str, Any],
    exchange_id: str,
    api_key: str,
    api_secret: str,
    order_execution_cfg: OrderExecutionConfig,
    order_execution_adapter: OrderExecutionAdapter | None,
) -> None:
    pair_label = f"{pair['Asset_X']}|{pair['Asset_Y']}"
    df_a, df_b = await _fetch_pair_candles(pair, timeframe, exchange_id, api_key, api_secret)
    if df_a is None or df_b is None:
        return

    current_pos = state.get_position_for_pair(pair_label)
    current_side = current_pos["side"] if current_pos else None
    best_params = pair["Best_Params"]
    result = evaluate_signal(
        df_a=df_a,
        df_b=df_b,
        entry_z=best_params["entry_z"],
        exit_z=strategy_cfg["execution"]["exit_z_score"],
        lookback_bars=best_params["lookback_bars"],
        vol_lookback_bars=strategy_cfg["execution"]["volatility_lookback_bars"],
        hedge_ratio=pair["Hedge_Ratio"],
        current_side=current_side,
    )
    pair_prices[pair_label] = (result.price_a, result.price_b)
    action = determine_action(current_side, result.signal)
    state.record_tick_signal(
        pair_label=pair_label,
        z_score=result.z_score,
        weight_a=result.weight_a,
        weight_b=result.weight_b,
        signal=result.signal,
        action=action,
        price_a=result.price_a,
        price_b=result.price_b,
    )
    await route_signal_transition(
        pair=pair,
        pair_label=pair_label,
        current_side=current_side,
        result=result,
        lookback_bars=best_params["lookback_bars"],
        timeframe=timeframe,
        state=state,
        notifier=notifier,
        order_execution_cfg=order_execution_cfg,
        order_execution_adapter=order_execution_adapter,
    )


async def _fetch_pair_candles(
    pair: dict[str, Any],
    timeframe: str,
    exchange_id: str,
    api_key: str,
    api_secret: str,
) -> tuple[Any | None, Any | None]:
    bars_needed = pair["Best_Params"]["lookback_bars"] + 50
    try:
        df_a = await fetch_recent_candles(
            pair["Asset_X"],
            bars_needed,
            timeframe,
            exchange_id=exchange_id,
            api_key=api_key,
            api_secret=api_secret,
        )
        df_b = await fetch_recent_candles(
            pair["Asset_Y"],
            bars_needed,
            timeframe,
            exchange_id=exchange_id,
            api_key=api_key,
            api_secret=api_secret,
        )
    except Exception as exc:
        logger.warning(f"Failed fetching data for {pair['Asset_X']}|{pair['Asset_Y']}: {exc}")
        return None, None
    return df_a, df_b


def _snapshot_tick_equity(
    state: TradeStateManager,
    pair_prices: dict[str, tuple[float, float]],
) -> None:
    per_pair_pnl = calculate_per_pair_pnl(state, pair_prices)
    closed = state.get_all_closed()
    realized = sum(trade["realized_pnl_pct"] or 0.0 for trade in closed)
    unrealized = calculate_unrealized_pnl(state, pair_prices)
    open_count = len(state.get_open_positions())
    state.snapshot_equity(
        total_equity_pct=realized + unrealized,
        open_positions=open_count,
        realized_pnl_pct=realized,
        unrealized_pnl_pct=unrealized,
        per_pair_pnl=json.dumps(per_pair_pnl) if per_pair_pnl else None,
    )
    logger.info(
        f"Tick complete | Open: {open_count} | "
        f"Realized: {realized*100:.4f}% | Unrealized: {unrealized*100:.4f}% | "
        f"Total Equity: {(realized+unrealized)*100:.4f}%"
    )
