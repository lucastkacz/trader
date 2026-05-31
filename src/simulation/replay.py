"""Deterministic offline replay foundation for shared trader signal policy."""

from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal, Protocol

import pandas as pd

from src.engine.trader.config import StrategyConfig
from src.engine.trader.runtime.signal_transition import determine_action
from src.engine.trader.signals.evaluator import evaluate_signal
from src.utils.timeframe_math import get_timeframe_minutes


@dataclass(frozen=True)
class ReplayWindow:
    """Inclusive replay range with an explicit deterministic candle cadence."""

    start: datetime
    end: datetime
    timeframe: str

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("replay window timestamps must be timezone-aware")
        if self.end < self.start:
            raise ValueError("replay window end must not be before start")
        if get_timeframe_minutes(self.timeframe) <= 0:
            raise ValueError("replay window timeframe must be positive")


@dataclass(frozen=True)
class ReplayPair:
    """Typed promoted-pair inputs required by shared signal evaluation."""

    asset_x: str
    asset_y: str
    hedge_ratio: float
    entry_z: float
    lookback_bars: int

    def __post_init__(self) -> None:
        if not self.asset_x or not self.asset_y:
            raise ValueError("replay pair assets must be non-empty")
        if self.entry_z <= 0:
            raise ValueError("replay pair entry_z must be positive")
        if self.lookback_bars <= 0:
            raise ValueError("replay pair lookback_bars must be positive")

    @property
    def label(self) -> str:
        """Return the canonical runtime pair label."""
        return f"{self.asset_x}|{self.asset_y}"

    @classmethod
    def from_promoted_pair(cls, pair: Mapping[str, Any]) -> "ReplayPair":
        """Build replay inputs from one validated promoted-artifact row."""
        best_params = pair["Best_Params"]
        return cls(
            asset_x=str(pair["Asset_X"]),
            asset_y=str(pair["Asset_Y"]),
            hedge_ratio=float(pair["Hedge_Ratio"]),
            entry_z=float(best_params["entry_z"]),
            lookback_bars=int(best_params["lookback_bars"]),
        )


@dataclass(frozen=True)
class SignalReplayConfig:
    """Typed inputs for a signal-policy-only offline replay."""

    window: ReplayWindow
    pairs: tuple[ReplayPair, ...]

    def __post_init__(self) -> None:
        if not self.pairs:
            raise ValueError("signal replay requires at least one pair")
        labels = [pair.label for pair in self.pairs]
        if len(set(labels)) != len(labels):
            raise ValueError("signal replay pair labels must be unique")


class ReplayClock:
    """Yield each deterministic replay timestamp in an inclusive window."""

    def __init__(self, window: ReplayWindow):
        self.window = window

    def __iter__(self) -> Iterator[datetime]:
        step = timedelta(minutes=get_timeframe_minutes(self.window.timeframe))
        current = self.window.start
        while current <= self.window.end:
            yield current
            current += step


class HistoricalCandleProvider(Protocol):
    """Historical as-of candle seam for offline replay."""

    def candles_through(
        self,
        symbol: str,
        *,
        timeframe: str,
        through: datetime,
        limit: int,
    ) -> pd.DataFrame:
        """Return at most limit candles for symbol with timestamp <= through."""


class InMemoryHistoricalCandleProvider:
    """DataFrame-backed historical candle adapter for offline replay and tests."""

    def __init__(self, candles_by_symbol: Mapping[str, pd.DataFrame]):
        self._candles_by_symbol = {
            symbol: _normalize_candles(symbol, candles)
            for symbol, candles in candles_by_symbol.items()
        }

    def candles_through(
        self,
        symbol: str,
        *,
        timeframe: str,
        through: datetime,
        limit: int,
    ) -> pd.DataFrame:
        del timeframe
        if limit <= 0:
            raise ValueError("historical candle limit must be positive")
        try:
            candles = self._candles_by_symbol[symbol]
        except KeyError as exc:
            raise KeyError(f"Historical candles missing for {symbol}") from exc
        through_timestamp = pd.Timestamp(through)
        result = candles[candles["timestamp"] <= through_timestamp].tail(limit).copy()
        result.attrs["symbol"] = symbol
        return result


@dataclass(frozen=True)
class ReplaySignalObservation:
    """Auditable shared signal-policy output for one pair at one replay tick."""

    replay_at: datetime
    pair_label: str
    signal: str
    action: str
    z_score: float
    weight_a: float
    weight_b: float
    price_a: float
    price_b: float
    candle_count_a: int
    candle_count_b: int


@dataclass(frozen=True)
class SignalReplayResult:
    """Auditable summary for a deterministic signal-policy-only replay."""

    scope: Literal["signal_evaluation_only"]
    window: ReplayWindow
    pair_labels: tuple[str, ...]
    completed_ticks: int
    observations: tuple[ReplaySignalObservation, ...]
    action_counts: dict[str, int]
    final_signal_sides: dict[str, str | None]


def run_signal_replay(
    *,
    config: SignalReplayConfig,
    strategy_cfg: StrategyConfig,
    candle_provider: HistoricalCandleProvider,
) -> SignalReplayResult:
    """Replay shared trader signal policy without mutating runtime state."""
    current_sides: dict[str, str | None] = {pair.label: None for pair in config.pairs}
    observations: list[ReplaySignalObservation] = []
    completed_ticks = 0

    for replay_at in ReplayClock(config.window):
        completed_ticks += 1
        for pair in config.pairs:
            bars_needed = max(
                pair.lookback_bars + 1,
                strategy_cfg.execution.volatility_lookback_bars + 1,
            )
            candles_a = _candles_for_tick(
                candle_provider,
                symbol=pair.asset_x,
                timeframe=config.window.timeframe,
                replay_at=replay_at,
                bars_needed=bars_needed,
            )
            candles_b = _candles_for_tick(
                candle_provider,
                symbol=pair.asset_y,
                timeframe=config.window.timeframe,
                replay_at=replay_at,
                bars_needed=bars_needed,
            )
            current_side = current_sides[pair.label]
            result = evaluate_signal(
                df_a=candles_a,
                df_b=candles_b,
                entry_z=pair.entry_z,
                exit_z=strategy_cfg.execution.exit_z_score,
                lookback_bars=pair.lookback_bars,
                vol_lookback_bars=strategy_cfg.execution.volatility_lookback_bars,
                hedge_ratio=pair.hedge_ratio,
                current_side=current_side,
            )
            action = determine_action(current_side, result.signal)
            observations.append(
                ReplaySignalObservation(
                    replay_at=replay_at,
                    pair_label=pair.label,
                    signal=result.signal,
                    action=action,
                    z_score=result.z_score,
                    weight_a=result.weight_a,
                    weight_b=result.weight_b,
                    price_a=result.price_a,
                    price_b=result.price_b,
                    candle_count_a=len(candles_a),
                    candle_count_b=len(candles_b),
                )
            )
            current_sides[pair.label] = (
                None if result.signal == "FLAT" else result.signal
            )

    return SignalReplayResult(
        scope="signal_evaluation_only",
        window=config.window,
        pair_labels=tuple(pair.label for pair in config.pairs),
        completed_ticks=completed_ticks,
        observations=tuple(observations),
        action_counts=dict(Counter(observation.action for observation in observations)),
        final_signal_sides=current_sides,
    )


def _candles_for_tick(
    provider: HistoricalCandleProvider,
    *,
    symbol: str,
    timeframe: str,
    replay_at: datetime,
    bars_needed: int,
) -> pd.DataFrame:
    candles = _normalize_candles(
        symbol,
        provider.candles_through(
            symbol,
            timeframe=timeframe,
            through=replay_at,
            limit=bars_needed,
        ),
    )
    if len(candles) > bars_needed:
        raise ValueError(f"Historical candle provider exceeded limit for {symbol}")
    if not candles.empty and candles["timestamp"].iloc[-1] > pd.Timestamp(replay_at):
        raise ValueError(f"Historical candle provider returned future data for {symbol}")
    candles.attrs["symbol"] = symbol
    return candles


def _normalize_candles(symbol: str, candles: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"timestamp", "close"}
    missing_columns = required_columns - set(candles.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Historical candles for {symbol} missing columns: {missing}")
    normalized = candles.copy()
    normalized["timestamp"] = pd.to_datetime(normalized["timestamp"], utc=True)
    return normalized.sort_values("timestamp").reset_index(drop=True)
