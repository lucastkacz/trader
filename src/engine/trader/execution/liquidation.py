"""Emergency liquidation workflow for trader execution."""

from typing import Any

from src.core.logger import logger
from src.engine.trader.execution.market_data import fetch_recent_candles
from src.engine.trader.state_manager import TradeStateManager
from src.interfaces.telegram.notifier import TelegramNotifier


async def execute_emergency_liquidation(
    state: TradeStateManager,
    pairs: list[dict[str, Any]],
    notifier: TelegramNotifier,
    timeframe: str,
    exchange_id: str,
    api_key: str,
    api_secret: str,
    target: str | None = None,
) -> None:
    """Close open local positions at latest fetched prices."""
    open_positions = state.get_open_positions()

    if target:
        open_positions = [p for p in open_positions if p["pair_label"] == target]

    if not open_positions:
        if notifier:
            await notifier.send(f"⚠️ Liquidation requested but no positions found for <b>{target or 'ALL'}</b>.")
        return

    if notifier:
        await notifier.send(f"🚨 <b>EXECUTING EMERGENCY LIQUIDATION</b> for {len(open_positions)} pair(s)...")

    total_exit_pnl = 0.0
    for pos in open_positions:
        pair_label = pos["pair_label"]
        asset_x = pos["asset_x"]
        asset_y = pos["asset_y"]
        try:
            df_x = await fetch_recent_candles(
                symbol=asset_x,
                timeframe=timeframe,
                bars_needed=1,
                exchange_id=exchange_id,
                api_key=api_key,
                api_secret=api_secret,
            )
            df_y = await fetch_recent_candles(
                symbol=asset_y,
                timeframe=timeframe,
                bars_needed=1,
                exchange_id=exchange_id,
                api_key=api_key,
                api_secret=api_secret,
            )
            price_x = df_x["close"].iloc[-1]
            price_y = df_y["close"].iloc[-1]

            pnl = state.close_position(
                pair_label=pair_label,
                exit_price_a=price_x,
                exit_price_b=price_y,
                timeframe=timeframe,
                exit_z=None,
            )
            total_exit_pnl += pnl or 0.0
            if notifier:
                await notifier.send(f"✅ <b>EMERGENCY EXIT:</b> {pair_label}\nPNL: <b>{pnl*100:.2f}%</b>")
        except Exception as exc:
            logger.error(f"Liquidation failed for {pair_label}: {exc}")
            if notifier:
                await notifier.send(f"❌ LIQUIDATION FAILED for {pair_label}: {exc}")
