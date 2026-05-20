from datetime import datetime, timezone

import pytest

from src.engine.trader.runtime.pair_queue import (
    OpenPositionExposure,
    PairQueueOpportunity,
    PairQueuePolicy,
    build_pair_queue_snapshot,
)
from src.engine.trader.runtime.pair_validity.models import PairValiditySnapshot


def _pair(asset_x: str, asset_y: str, sharpe: float = 1.0):
    return {
        "Asset_X": asset_x,
        "Asset_Y": asset_y,
        "Performance": {"sharpe_ratio": sharpe},
    }


def _validity(
    pair_label: str,
    *,
    recent_correlation: float = 0.8,
    recent_p_value: float = 0.03,
    hedge_ratio_drift_pct: float = 2.0,
    half_life_drift_pct: float = 10.0,
    bars_since_promotion: int = 120,
    operator_review_reasons: list[str] | None = None,
    open_position_review_reasons: list[str] | None = None,
):
    asset_x, asset_y = pair_label.split("|")
    return PairValiditySnapshot(
        pair_label=pair_label,
        asset_x=asset_x,
        asset_y=asset_y,
        artifact_generated_at="2026-01-01T00:00:00+00:00",
        artifact_promoted_at="2026-01-01T01:00:00+00:00",
        latest_data_at="2026-01-01T03:00:00+00:00",
        timeframe="1m",
        exchange="bybit",
        recent_window_bars=240,
        recent_observation_bars=240,
        wall_clock_age_minutes_since_artifact_generation=180.0,
        bars_since_artifact_generation=180,
        bars_since_promotion=bars_since_promotion,
        research_window_start=None,
        research_window_end=None,
        wall_clock_age_minutes_since_research_end=None,
        bars_since_research_end=None,
        research_hedge_ratio=1.0,
        recent_hedge_ratio=1.02,
        hedge_ratio_drift_pct=hedge_ratio_drift_pct,
        research_correlation=0.82,
        recent_correlation=recent_correlation,
        correlation_delta=recent_correlation - 0.82,
        research_p_value=0.02,
        recent_p_value=recent_p_value,
        p_value_delta=recent_p_value - 0.02,
        research_half_life_bars=80.0,
        recent_half_life_bars=88.0,
        half_life_drift_pct=half_life_drift_pct,
        research_spread_mean=None,
        recent_spread_mean=None,
        spread_mean_shift_sigma=None,
        research_spread_std=None,
        recent_spread_std=None,
        spread_std_drift_pct=None,
        open_position_id=None,
        open_position_holding_bars=None,
        open_position_half_life_multiple=None,
        observed_entries=0,
        observed_signal_exits=0,
        observed_forced_exits=0,
        observed_avg_holding_bars=None,
        operator_review_reasons=operator_review_reasons or [],
        open_position_review_reasons=open_position_review_reasons or [],
        notes=[],
    )


def test_pair_queue_reranks_promoted_pairs_from_current_scores():
    promoted_pairs = [
        _pair("AAA/USDT", "BBB/USDT", sharpe=2.5),
        _pair("CCC/USDT", "DDD/USDT", sharpe=1.2),
    ]
    opportunities = {
        "AAA/USDT|BBB/USDT": PairQueueOpportunity(
            pair_label="AAA/USDT|BBB/USDT",
            score=0.05,
            entry_signal=True,
        ),
        "CCC/USDT|DDD/USDT": PairQueueOpportunity(
            pair_label="CCC/USDT|DDD/USDT",
            score=1.0,
            entry_signal=True,
        ),
    }
    snapshot = build_pair_queue_snapshot(
        promoted_pairs=promoted_pairs,
        validity_snapshots=[
            _validity("AAA/USDT|BBB/USDT", recent_correlation=0.56),
            _validity("CCC/USDT|DDD/USDT", recent_correlation=0.90),
        ],
        opportunities=opportunities,
        policy=PairQueuePolicy(
            research_weight=0.20,
            validity_weight=0.40,
            opportunity_weight=0.40,
            min_recent_correlation=0.55,
            require_entry_signal=True,
        ),
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    assert [decision.pair_label for decision in snapshot.decisions] == [
        "CCC/USDT|DDD/USDT",
        "AAA/USDT|BBB/USDT",
    ]
    assert snapshot.decisions[0].research_rank == 2
    assert snapshot.decisions[0].current_rank == 1
    assert snapshot.decisions[0].entry_allowed is True


def test_pair_queue_blocks_invalid_pairs_for_new_entries_only():
    snapshot = build_pair_queue_snapshot(
        promoted_pairs=[_pair("AAA/USDT", "BBB/USDT", sharpe=2.0)],
        validity_snapshots=[
            _validity(
                "AAA/USDT|BBB/USDT",
                recent_correlation=0.40,
                recent_p_value=0.20,
                hedge_ratio_drift_pct=35.0,
                half_life_drift_pct=150.0,
            )
        ],
        opportunities={
            "AAA/USDT|BBB/USDT": PairQueueOpportunity(
                pair_label="AAA/USDT|BBB/USDT",
                score=1.0,
                entry_signal=True,
            ),
        },
        policy=PairQueuePolicy(
            min_recent_correlation=0.55,
            max_recent_p_value=0.10,
            max_abs_hedge_ratio_drift_pct=20.0,
            max_half_life_drift_pct=100.0,
            require_entry_signal=True,
        ),
    )

    decision = snapshot.decisions[0]
    assert decision.entry_allowed is False
    assert decision.block_reasons == [
        "recent_correlation_below_min",
        "recent_cointegration_p_value_above_max",
        "hedge_ratio_drift_above_max",
        "half_life_drift_above_max",
    ]


def test_pair_queue_respects_capital_slots_and_existing_exposure():
    snapshot = build_pair_queue_snapshot(
        promoted_pairs=[
            _pair("AAA/USDT", "BBB/USDT", sharpe=2.0),
            _pair("CCC/USDT", "AAA/USDT", sharpe=2.0),
        ],
        validity_snapshots=[
            _validity("AAA/USDT|BBB/USDT"),
            _validity("CCC/USDT|AAA/USDT"),
        ],
        open_positions=[
            OpenPositionExposure(
                pair_label="AAA/USDT|BBB/USDT",
                asset_x="AAA/USDT",
                asset_y="BBB/USDT",
                position_id=7,
            )
        ],
        policy=PairQueuePolicy(
            max_open_positions=2,
            max_positions_per_pair=1,
            max_positions_per_asset=1,
        ),
    )

    by_pair = {decision.pair_label: decision for decision in snapshot.decisions}
    assert by_pair["AAA/USDT|BBB/USDT"].block_reasons == [
        "pair_position_limit_reached",
        "asset_position_limit_reached",
    ]
    assert by_pair["AAA/USDT|BBB/USDT"].has_open_position is True
    assert by_pair["CCC/USDT|AAA/USDT"].block_reasons == [
        "asset_position_limit_reached"
    ]


def test_pair_queue_policy_rejects_invalid_weights():
    with pytest.raises(ValueError, match="at least one pair queue weight"):
        PairQueuePolicy(
            research_weight=0.0,
            validity_weight=0.0,
            opportunity_weight=0.0,
        )
