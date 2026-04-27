"""Position lifecycle service for trader state."""

import sqlite3
from datetime import datetime, timezone

from src.core.logger import LogContext, logger
from src.engine.trader.state.events import EventRepository
from src.engine.trader.state.legs import LegRepository
from src.engine.trader.state.positions import PositionRepository


class PositionLifecycleService:
    """Coordinate multi-table spread position lifecycle transitions."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        positions: PositionRepository,
        events: EventRepository,
        legs: LegRepository,
    ):
        self.conn = conn
        self.positions = positions
        self.events = events
        self.legs = legs

    def open_position(
        self,
        pair_label: str,
        asset_x: str,
        asset_y: str,
        side: str,
        entry_price_a: float,
        entry_price_b: float,
        weight_a: float,
        weight_b: float,
        entry_z: float,
        lookback_bars: int,
    ) -> int:
        """Insert a new spread position and its audit rows."""
        now = datetime.now(timezone.utc).isoformat()
        with self.conn:
            spread_id = self.positions.insert_open(
                pair_label=pair_label,
                asset_x=asset_x,
                asset_y=asset_y,
                side=side,
                entry_price_a=entry_price_a,
                entry_price_b=entry_price_b,
                weight_a=weight_a,
                weight_b=weight_b,
                entry_z=entry_z,
                lookback_bars=lookback_bars,
                opened_at=now,
            )
            self.events.append(
                spread_id=spread_id,
                event_type="SIGNAL_ENTRY",
                payload={
                    "pair_label": pair_label,
                    "asset_x": asset_x,
                    "asset_y": asset_y,
                    "side": side,
                    "entry_price_a": entry_price_a,
                    "entry_price_b": entry_price_b,
                    "weight_a": weight_a,
                    "weight_b": weight_b,
                    "entry_z": entry_z,
                    "lookback_bars": lookback_bars,
                },
                created_at=now,
                idempotency_key=f"spread:{spread_id}:SIGNAL_ENTRY:{now}",
            )
            self.legs.record_targets(
                spread_id=spread_id,
                leg_role="OPEN",
                asset_x=asset_x,
                asset_y=asset_y,
                side=side,
                weight_a=weight_a,
                weight_b=weight_b,
                created_at=now,
            )

        ctx = LogContext(pair=pair_label, signal=side)
        logger.bind(**ctx.model_dump(exclude_none=True)).info(
            f"ENTRY | {side} @ A={entry_price_a:.6f} B={entry_price_b:.6f} | "
            f"Weights: A={weight_a:.4f} B={weight_b:.4f} | Z={entry_z:.4f}"
        )
        return spread_id

    def close_position(
        self,
        pair_label: str,
        exit_price_a: float,
        exit_price_b: float,
        exit_z: float | None = None,
        close_reason: str = "SIGNAL_EXIT",
    ) -> float | None:
        """
        Close the open order for a pair. Calculates realized PnL.
        Returns the PnL percentage, or None if no open position found.
        """
        row = self.positions.get_open_for_pair_row(pair_label)

        if row is None:
            return None

        pnl = self._calculate_realized_pnl(row, exit_price_a, exit_price_b)
        now = datetime.now(timezone.utc).isoformat()
        holding_bars = compute_holding_bars(row["opened_at"], now)

        with self.conn:
            self.positions.close(
                spread_id=row["id"],
                closed_at=now,
                exit_price_a=exit_price_a,
                exit_price_b=exit_price_b,
                realized_pnl_pct=pnl,
                exit_z=exit_z,
                holding_bars=holding_bars,
                close_reason=close_reason,
            )
            self.events.append(
                spread_id=row["id"],
                event_type=close_reason,
                payload={
                    "pair_label": pair_label,
                    "exit_price_a": exit_price_a,
                    "exit_price_b": exit_price_b,
                    "exit_z": exit_z,
                    "realized_pnl_pct": pnl,
                    "holding_bars": holding_bars,
                },
                created_at=now,
                idempotency_key=f"spread:{row['id']}:{close_reason}:{now}",
            )
            self.legs.record_targets(
                spread_id=row["id"],
                leg_role="CLOSE",
                asset_x=row["asset_x"],
                asset_y=row["asset_y"],
                side=row["side"],
                weight_a=row["weight_a"],
                weight_b=row["weight_b"],
                created_at=now,
            )

        ctx = LogContext(pair=pair_label, signal="EXIT")
        logger.bind(**ctx.model_dump(exclude_none=True)).info(
            f"EXIT | PnL: {pnl*100:.4f}% | "
            f"Exit A={exit_price_a:.6f} B={exit_price_b:.6f} | "
            f"Z={exit_z:.4f} | Bars={holding_bars}"
            if exit_z is not None else
            f"EXIT | PnL: {pnl*100:.4f}% | "
            f"Exit A={exit_price_a:.6f} B={exit_price_b:.6f}"
        )
        return pnl

    @staticmethod
    def _calculate_realized_pnl(
        row: sqlite3.Row,
        exit_price_a: float,
        exit_price_b: float,
    ) -> float:
        """Calculate realized PnL using volatility-parity spread weights."""
        ret_a = (exit_price_a - row["entry_price_a"]) / row["entry_price_a"]
        ret_b = (exit_price_b - row["entry_price_b"]) / row["entry_price_b"]

        if row["side"] == "LONG_SPREAD":
            return row["weight_a"] * ret_a - row["weight_b"] * ret_b
        return -row["weight_a"] * ret_a + row["weight_b"] * ret_b


def compute_holding_bars(open_ts: str, close_ts: str) -> int:
    """
    Compute holding duration in 4H bars from ISO timestamps.
    Uses actual time delta, so it works for any candle interval.
    Minimum 1 bar (even if closed within the same tick).
    """
    try:
        t_open = datetime.fromisoformat(open_ts.replace("Z", "+00:00"))
        t_close = datetime.fromisoformat(close_ts.replace("Z", "+00:00"))
        delta_hours = (t_close - t_open).total_seconds() / 3600.0
        return max(1, int(round(delta_hours / 4.0)))
    except (ValueError, TypeError):
        return 1
