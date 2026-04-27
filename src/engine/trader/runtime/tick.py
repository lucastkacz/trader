"""Single-tick orchestration for the trader runtime."""

import json
from datetime import datetime, timezone
from typing import Any

from src.core.logger import logger
from src.engine.trader.execution.market_data import fetch_recent_candles
from src.engine.trader.execution.pnl import calculate_per_pair_pnl, calculate_unrealized_pnl
from src.engine.trader.runtime.actions import determine_action
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
) -> None:
    """Execute one full trader tick across all configured pairs."""
    if state.is_system_paused():
        logger.info("Tick skipped — System is PAUSED.")
        return

    tick_time = datetime.now(timezone.utc).isoformat()
    logger.info(f"═══ ENGINE TICK @ {tick_time} ═══")

    pair_prices = {}

    for pair in pairs:
        asset_x = pair["Asset_X"]
        asset_y = pair["Asset_Y"]
        pair_label = f"{asset_x}|{asset_y}"
        best_params = pair["Best_Params"]
        hedge_ratio = pair["Hedge_Ratio"]
        lookback_bars = best_params["lookback_bars"]
        entry_z = best_params["entry_z"]
        vol_lookback_bars = strategy_cfg["execution"]["volatility_lookback_bars"]

        bars_needed = lookback_bars + 50

        try:
            df_a = await fetch_recent_candles(
                asset_x,
                bars_needed,
                timeframe,
                exchange_id=exchange_id,
                api_key=api_key,
                api_secret=api_secret,
            )
            df_b = await fetch_recent_candles(
                asset_y,
                bars_needed,
                timeframe,
                exchange_id=exchange_id,
                api_key=api_key,
                api_secret=api_secret,
            )
        except Exception as exc:
            logger.warning(f"Failed fetching data for {pair_label}: {exc}")
            continue

        current_pos = state.get_position_for_pair(pair_label)
        current_side = current_pos["side"] if current_pos else None

        exit_z = strategy_cfg["execution"]["exit_z_score"]

        result = evaluate_signal(
            df_a=df_a,
            df_b=df_b,
            entry_z=entry_z,
            exit_z=exit_z,
            lookback_bars=lookback_bars,
            vol_lookback_bars=vol_lookback_bars,
            hedge_ratio=hedge_ratio,
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

        await _route_signal_transition(
            pair=pair,
            pair_label=pair_label,
            current_side=current_side,
            result=result,
            lookback_bars=lookback_bars,
            state=state,
            notifier=notifier,
        )

    per_pair_pnl = calculate_per_pair_pnl(state, pair_prices)
    per_pair_pnl_json = json.dumps(per_pair_pnl) if per_pair_pnl else None

    closed = state.get_all_closed()
    realized = sum(t["realized_pnl_pct"] or 0.0 for t in closed)
    unrealized = calculate_unrealized_pnl(state, pair_prices)
    open_count = len(state.get_open_positions())

    state.snapshot_equity(
        total_equity_pct=realized + unrealized,
        open_positions=open_count,
        realized_pnl_pct=realized,
        unrealized_pnl_pct=unrealized,
        per_pair_pnl=per_pair_pnl_json,
    )

    logger.info(
        f"Tick complete | Open: {open_count} | "
        f"Realized: {realized*100:.4f}% | Unrealized: {unrealized*100:.4f}% | "
        f"Total Equity: {(realized+unrealized)*100:.4f}%"
    )


async def _route_signal_transition(
    pair: dict[str, Any],
    pair_label: str,
    current_side: str | None,
    result: Any,
    lookback_bars: int,
    state: TradeStateManager,
    notifier: TelegramNotifier,
) -> None:
    asset_x = pair["Asset_X"]
    asset_y = pair["Asset_Y"]

    if current_side is None and result.signal != "FLAT":
        state.open_position(
            pair_label=pair_label,
            asset_x=asset_x,
            asset_y=asset_y,
            side=result.signal,
            entry_price_a=result.price_a,
            entry_price_b=result.price_b,
            weight_a=result.weight_a,
            weight_b=result.weight_b,
            entry_z=result.z_score,
            lookback_bars=lookback_bars,
        )
        await notifier.send(
            f"🚀 <b>ENTRY SIGNAL: {pair_label}</b>\n"
            f"• Z-Score: {result.z_score:.2f}\n"
            f"• Action: {result.signal}"
        )

    elif current_side is not None and result.signal == "FLAT":
        pnl = state.close_position(
            pair_label=pair_label,
            exit_price_a=result.price_a,
            exit_price_b=result.price_b,
            exit_z=result.z_score,
        )
        await notifier.send(
            f"🏁 <b>EXIT SIGNAL: {pair_label}</b>\n"
            f"• Z-Score: {result.z_score:.2f}\n"
            f"• PNL: <b>{pnl*100:.2f}%</b> if pnl else 'N/A'\n"
            f"• Action: CLOSE Spread"
        )

    elif current_side is not None and result.signal != "FLAT" and result.signal != current_side:
        pnl = state.close_position(
            pair_label=pair_label,
            exit_price_a=result.price_a,
            exit_price_b=result.price_b,
            exit_z=result.z_score,
        )
        state.open_position(
            pair_label=pair_label,
            asset_x=asset_x,
            asset_y=asset_y,
            side=result.signal,
            entry_price_a=result.price_a,
            entry_price_b=result.price_b,
            weight_a=result.weight_a,
            weight_b=result.weight_b,
            entry_z=result.z_score,
            lookback_bars=lookback_bars,
        )
        await notifier.send(
            f"🔄 <b>FLIP SIGNAL: {pair_label}</b>\n"
            f"• Old Side Closed | PNL: <b>{pnl*100:.2f}%</b> if pnl else 'N/A'\n"
            f"• New Side: {result.signal}\n"
            f"• Z-Score: {result.z_score:.2f}"
        )
