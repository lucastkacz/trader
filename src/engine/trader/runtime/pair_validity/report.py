"""Public report builder for read-only promoted-pair validity diagnostics."""

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.data.storage.local_parquet import LocalOHLCVParquetStore
from src.engine.trader.runtime.pair_validity.artifact import (
    load_latest_promoted_at,
    research_window,
)
from src.engine.trader.runtime.pair_validity.market_data import (
    latest_timestamp,
    load_recent_market_data,
)
from src.engine.trader.runtime.pair_validity.models import (
    PairValidityConfig,
    PairValidityReport,
    PairValiditySnapshot,
)
from src.engine.trader.runtime.pair_validity.state import (
    open_position_holding_bars,
    summarize_pair_execution,
)
from src.engine.trader.runtime.pair_validity.statistics import (
    compute_recent_stats,
    delta,
    finite_optional,
    pct_drift,
    safe_ratio,
    spread_mean_shift_sigma,
)
from src.engine.trader.runtime.pair_validity.time import (
    age_minutes,
    as_utc,
    bars_between,
    parse_datetime,
)
from src.engine.trader.runtime.artifacts import validate_pair_artifact_file

if TYPE_CHECKING:
    from src.engine.trader.state.manager import TradeStateManager


def build_pair_validity_report(
    *,
    surviving_pairs_path: str | Path,
    market_data_base_dir: str | Path,
    state: "TradeStateManager",
    config: PairValidityConfig,
    now: datetime | None = None,
) -> PairValidityReport:
    """Compute read-only diagnostics for each pair in a promoted artifact."""
    artifact = validate_pair_artifact_file(surviving_pairs_path)
    storage = LocalOHLCVParquetStore(base_dir=str(market_data_base_dir))
    reference_time = as_utc(now or datetime.now(timezone.utc))
    promoted_at = load_latest_promoted_at(Path(surviving_pairs_path))
    all_positions = state.get_all_orders()

    snapshots = [
        _build_pair_snapshot(
            pair=pair,
            artifact_generated_at=as_utc(artifact.metadata.generated_at),
            artifact_promoted_at=promoted_at,
            timeframe=artifact.metadata.timeframe,
            exchange=artifact.metadata.exchange,
            storage=storage,
            state=state,
            all_positions=all_positions,
            config=config,
            now=reference_time,
        )
        for pair in artifact.pairs
    ]

    return PairValidityReport(
        artifact_path=str(surviving_pairs_path),
        timeframe=artifact.metadata.timeframe,
        exchange=artifact.metadata.exchange,
        pair_count=artifact.metadata.pair_count,
        snapshots=snapshots,
    )


def build_pair_validity_report_if_configured(
    *,
    surviving_pairs_path: str | Path,
    market_data_base_dir: str | Path | None,
    state: "TradeStateManager",
    config: PairValidityConfig | None,
    now: datetime | None = None,
) -> PairValidityReport | None:
    """Build diagnostics when configured, or an auditable unavailable report."""
    if market_data_base_dir is None or config is None:
        return None

    try:
        return build_pair_validity_report(
            surviving_pairs_path=surviving_pairs_path,
            market_data_base_dir=market_data_base_dir,
            state=state,
            config=config,
            now=now,
        )
    except Exception as exc:
        return PairValidityReport(
            artifact_path=str(surviving_pairs_path),
            timeframe="unknown",
            exchange="unknown",
            pair_count=0,
            snapshots=[],
            notes=[f"pair_validity_unavailable: {exc}"],
        )


def _build_pair_snapshot(
    *,
    pair: dict[str, Any],
    artifact_generated_at: datetime,
    artifact_promoted_at: datetime | None,
    timeframe: str,
    exchange: str,
    storage: LocalOHLCVParquetStore,
    state: "TradeStateManager",
    all_positions: list[dict[str, Any]],
    config: PairValidityConfig,
    now: datetime,
) -> PairValiditySnapshot:
    asset_x = pair["Asset_X"]
    asset_y = pair["Asset_Y"]
    label = f"{asset_x}|{asset_y}"
    notes: list[str] = []
    operator_review_reasons: list[str] = []
    open_position_review_reasons: list[str] = []

    market = load_recent_market_data(
        storage=storage,
        asset_x=asset_x,
        asset_y=asset_y,
        timeframe=timeframe,
        exchange=exchange,
    )
    if market is None:
        notes.append("missing_recent_market_data")
        operator_review_reasons.append("missing_recent_market_data")

    latest_data_at = None if market is None else latest_timestamp(market)
    latest_data_age_bars = bars_between(latest_data_at, now, timeframe)
    if (
        latest_data_age_bars is not None
        and config.max_latest_data_age_bars is not None
        and latest_data_age_bars > config.max_latest_data_age_bars
    ):
        operator_review_reasons.append("market_data_older_than_latest_age_limit")
    if latest_data_at is not None and latest_data_at < artifact_generated_at:
        operator_review_reasons.append("market_data_older_than_artifact_generation")
    if (
        latest_data_at is not None
        and artifact_promoted_at is not None
        and latest_data_at < artifact_promoted_at
    ):
        operator_review_reasons.append("market_data_older_than_promotion")
    window_bars = _recent_window_bars(pair, config)
    recent = market.tail(window_bars) if market is not None else None
    recent_observation_bars = 0 if recent is None else len(recent)
    if market is not None and recent_observation_bars < config.min_recent_bars:
        operator_review_reasons.append("insufficient_recent_bars")

    research_start, research_end = research_window(pair)
    _append_missing_artifact_notes(notes, research_start, research_end)

    baseline = _read_research_baseline(pair, notes)
    recent_stats = (
        compute_recent_stats(recent)
        if recent_observation_bars >= 3
        else {}
    )
    recent_values = _read_recent_values(recent_stats)
    if recent_observation_bars >= config.min_recent_bars and recent_values["p_value"] is None:
        operator_review_reasons.append("recent_cointegration_unavailable")

    open_position = state.get_position_for_pair(label)
    open_position_id = None if open_position is None else int(open_position["id"])
    holding_bars = open_position_holding_bars(
        open_position=open_position,
        latest_data_at=latest_data_at,
        now=now,
        timeframe=timeframe,
        notes=notes,
    )
    if (
        open_position is not None
        and latest_data_at is not None
        and open_position_opened_after_data(open_position, latest_data_at)
    ):
        open_position_review_reasons.append("market_data_older_than_open_position")
    half_life_multiple = safe_ratio(holding_bars, baseline["half_life"])
    if (
        half_life_multiple is not None
        and config.open_position_review_half_life_multiple is not None
        and half_life_multiple >= config.open_position_review_half_life_multiple
    ):
        open_position_review_reasons.append("open_position_exceeds_half_life_multiple")

    execution = summarize_pair_execution(label, all_positions)
    return PairValiditySnapshot(
        pair_label=label,
        asset_x=asset_x,
        asset_y=asset_y,
        artifact_generated_at=artifact_generated_at.isoformat(),
        artifact_promoted_at=(
            artifact_promoted_at.isoformat() if artifact_promoted_at is not None else None
        ),
        latest_data_at=latest_data_at.isoformat() if latest_data_at is not None else None,
        timeframe=timeframe,
        exchange=exchange,
        recent_window_bars=window_bars,
        recent_observation_bars=recent_observation_bars,
        wall_clock_age_minutes_since_artifact_generation=age_minutes(
            artifact_generated_at,
            now,
        ),
        bars_since_artifact_generation=bars_between(
            artifact_generated_at,
            latest_data_at,
            timeframe,
        ),
        bars_since_promotion=bars_between(artifact_promoted_at, latest_data_at, timeframe),
        research_window_start=research_start.isoformat() if research_start else None,
        research_window_end=research_end.isoformat() if research_end else None,
        wall_clock_age_minutes_since_research_end=age_minutes(research_end, now),
        bars_since_research_end=bars_between(research_end, latest_data_at, timeframe),
        research_hedge_ratio=baseline["hedge_ratio"],
        recent_hedge_ratio=recent_values["hedge_ratio"],
        hedge_ratio_drift_pct=pct_drift(
            baseline["hedge_ratio"],
            recent_values["hedge_ratio"],
        ),
        research_correlation=baseline["correlation"],
        recent_correlation=recent_values["correlation"],
        correlation_delta=delta(baseline["correlation"], recent_values["correlation"]),
        research_p_value=baseline["p_value"],
        recent_p_value=recent_values["p_value"],
        p_value_delta=delta(baseline["p_value"], recent_values["p_value"]),
        research_half_life_bars=baseline["half_life"],
        recent_half_life_bars=recent_values["half_life"],
        half_life_drift_pct=pct_drift(
            baseline["half_life"],
            recent_values["half_life"],
        ),
        research_spread_mean=baseline["spread_mean"],
        recent_spread_mean=recent_values["spread_mean"],
        spread_mean_shift_sigma=spread_mean_shift_sigma(
            baseline["spread_mean"],
            recent_values["spread_mean"],
            baseline["spread_std"],
        ),
        research_spread_std=baseline["spread_std"],
        recent_spread_std=recent_values["spread_std"],
        spread_std_drift_pct=pct_drift(
            baseline["spread_std"],
            recent_values["spread_std"],
        ),
        open_position_id=open_position_id,
        open_position_holding_bars=holding_bars,
        open_position_half_life_multiple=half_life_multiple,
        observed_entries=execution.observed_entries,
        observed_signal_exits=execution.observed_signal_exits,
        observed_forced_exits=execution.observed_forced_exits,
        observed_avg_holding_bars=execution.observed_avg_holding_bars,
        operator_review_reasons=operator_review_reasons,
        open_position_review_reasons=open_position_review_reasons,
        notes=notes,
    )


def _recent_window_bars(pair: dict[str, Any], config: PairValidityConfig) -> int:
    if config.recent_window_bars is not None:
        return config.recent_window_bars
    return int(pair["Best_Params"]["lookback_bars"])


def _read_research_baseline(pair: dict[str, Any], notes: list[str]) -> dict[str, float | None]:
    baseline = {
        "hedge_ratio": finite_optional(pair.get("Hedge_Ratio")),
        "p_value": finite_optional(pair.get("P_Value")),
        "half_life": finite_optional(pair.get("Half_Life")),
        "correlation": finite_optional(pair.get("Correlation")),
        "spread_mean": finite_optional(pair.get("Spread_Mean")),
        "spread_std": finite_optional(pair.get("Spread_Std")),
    }
    if baseline["correlation"] is None:
        notes.append("missing_research_correlation")
    if baseline["spread_mean"] is None:
        notes.append("missing_research_spread_mean")
    if baseline["spread_std"] is None:
        notes.append("missing_research_spread_std")
    return baseline


def _read_recent_values(stats: dict[str, float]) -> dict[str, float | None]:
    return {
        "hedge_ratio": finite_optional(stats.get("hedge_ratio")),
        "correlation": finite_optional(stats.get("correlation")),
        "p_value": finite_optional(stats.get("p_value")),
        "half_life": finite_optional(stats.get("half_life")),
        "spread_mean": finite_optional(stats.get("spread_mean")),
        "spread_std": finite_optional(stats.get("spread_std")),
    }


def _append_missing_artifact_notes(
    notes: list[str],
    research_start: datetime | None,
    research_end: datetime | None,
) -> None:
    if research_start is None:
        notes.append("missing_research_window_start")
    if research_end is None:
        notes.append("missing_research_window_end")


def open_position_opened_after_data(
    open_position: dict[str, Any],
    latest_data_at: datetime,
) -> bool:
    opened_at = parse_position_opened_at(open_position)
    return opened_at is not None and opened_at > latest_data_at


def parse_position_opened_at(open_position: dict[str, Any]) -> datetime | None:
    return parse_datetime(open_position["opened_at"])
