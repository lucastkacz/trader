import json
from datetime import datetime, timezone

import pytest

from src.engine.trader.cli import promote_pairs
from src.engine.trader.config import load_pipeline_config
from src.engine.trader.runtime import artifacts as pairs


def _valid_pair(sharpe_ratio=1.25):
    return {
        "Asset_X": "BTC/USDT",
        "Asset_Y": "ETH/USDT",
        "Hedge_Ratio": 1.7,
        "Best_Params": {
            "lookback_bars": 540,
            "entry_z": 2.0,
        },
        "Performance": {
            "sharpe_ratio": sharpe_ratio,
            "final_pnl_pct": 12.5,
        },
    }


def _artifact(pair_rows, timeframe="1m", exchange="bybit", generated_at=None):
    return pairs.build_pair_artifact(
        pair_rows=pair_rows,
        timeframe=timeframe,
        exchange=exchange,
        generated_at=generated_at,
    )


def _write_artifact(path, artifact):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact), encoding="utf-8")


def _write_pipeline_config(tmp_path, artifact_base_dir, timeframe="1m", exchange="bybit"):
    path = tmp_path / "pipeline.yml"
    path.write_text(
        f"""
pipeline:
  name: test-pipeline
  timeframe: "{timeframe}"
  historical_days: 1
  max_symbols: null
  execution:
    exchange: "{exchange}"
    credential_tier: "readonly"
    market_data_base_dir: "{tmp_path / "market_data"}"
    artifact_base_dir: "{artifact_base_dir}"
    db_path: "{tmp_path / "trades.db"}"
    min_sharpe: 1.0
    max_ticks: null
    heartbeat_seconds: 60
    sync_to_boundary: false
    market_data_fetch:
      request_timeout_seconds: 15.0
      max_attempts: 3
      retry_backoff_seconds: 2.0
    reconciliation:
      snapshot_provider: "ccxt_readonly"
      snapshot_timeout_seconds: 15.0
      stale_order_after_seconds: 120.0
    order_execution:
      mode: "state_only"
      fill_poll_attempts: 0
      fill_poll_interval_seconds: 0
      cancel_unfilled_after_poll: false
      client_order_prefix: "test"
    pair_refresh:
      mode: "manual"
      reload_policy: "on_boot"
      stale_open_position_policy: "natural_exit"
    pair_validity:
      recent_window_bars: 240
      min_recent_bars: 60
      max_latest_data_age_bars: 5
      open_position_review_half_life_multiple: 3.0
    pair_queue:
      enabled: true
      mode: "future_entries"
      require_entry_signal: false
      scoring:
        research_weight: 0.35
        validity_weight: 0.45
        opportunity_weight: 0.20
        research_sharpe_score_at: 3.0
      validity_thresholds:
        block_on_missing_validity: true
        block_on_operator_review_reasons: true
        max_bars_since_promotion: null
        min_recent_correlation: null
        max_recent_p_value: null
        max_abs_hedge_ratio_drift_pct: null
        max_half_life_drift_pct: null
      allocation:
        max_open_positions: null
        max_positions_per_pair: 1
        max_positions_per_asset: null
""",
        encoding="utf-8",
    )
    return path


def _load_pipeline(tmp_path, artifact_base_dir, timeframe="1m", exchange="bybit"):
    path = _write_pipeline_config(tmp_path, artifact_base_dir, timeframe, exchange)
    return load_pipeline_config(path)


def test_promote_pairs_cli_promotes_candidate_and_creates_audit_record(
    tmp_path,
    capsys,
):
    base_dir = tmp_path / "universes"
    pipeline_path = _write_pipeline_config(tmp_path, base_dir)
    candidate_path = pairs.candidate_pair_artifact_path("1m", base_dir)
    audit_path = tmp_path / "audit" / "promotion.jsonl"
    _write_artifact(candidate_path, _artifact([_valid_pair()]))

    exit_code = promote_pairs.main(
        [
            "--pipeline",
            str(pipeline_path),
            "--audit-path",
            str(audit_path),
            "--operator",
            "operator-1",
        ]
    )

    promoted_path = pairs.promoted_pair_artifact_path("1m", base_dir)
    captured = capsys.readouterr()
    assert exit_code == 0
    assert f"Promoted artifact: {promoted_path}" in captured.out
    assert promoted_path.exists()
    assert not candidate_path.exists()

    audit_record = json.loads(audit_path.read_text(encoding="utf-8").strip())
    assert audit_record["event_type"] == "pair_artifact_promoted"
    assert audit_record["operator"] == "operator-1"
    assert audit_record["pipeline_name"] == "test-pipeline"
    assert audit_record["timeframe"] == "1m"
    assert audit_record["exchange"] == "bybit"
    assert audit_record["candidate"]["path"] == str(candidate_path)
    assert audit_record["candidate"]["pair_count"] == 1
    assert audit_record["promoted"]["path"] == str(promoted_path)
    assert audit_record["pair_refresh"] == {
        "mode": "manual",
        "reload_policy": "on_boot",
        "stale_open_position_policy": "natural_exit",
    }


@pytest.mark.parametrize(
    ("candidate_artifact", "match"),
    [
        (["BTC|ETH"], "Legacy list-only"),
        (
            _artifact([_valid_pair()], generated_at="2026-01-01T00:00:00+00:00"),
            "stale",
        ),
        (
            _artifact(
                [_valid_pair()],
                exchange="kucoin",
                generated_at="2026-01-01T00:01:00+00:00",
            ),
            "exchange mismatch",
        ),
    ],
)
def test_promote_pairs_command_rejects_invalid_candidates_without_changing_promoted(
    tmp_path,
    candidate_artifact,
    match,
):
    base_dir = tmp_path / "universes"
    pipeline_cfg = _load_pipeline(tmp_path, base_dir)
    candidate_path = pairs.candidate_pair_artifact_path("1m", base_dir)
    promoted_path = pairs.promoted_pair_artifact_path("1m", base_dir)
    audit_path = tmp_path / "audit.jsonl"
    original_promoted = _artifact(
        [_valid_pair(sharpe_ratio=0.5)],
        generated_at="2026-01-01T00:00:00+00:00",
    )
    _write_artifact(promoted_path, original_promoted)
    _write_artifact(candidate_path, candidate_artifact)

    with pytest.raises(ValueError, match=match):
        promote_pairs.promote_pairs_from_pipeline_config(
            pipeline_cfg=pipeline_cfg,
            max_age_seconds=60,
            audit_path=audit_path,
            now=datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc),
        )

    assert candidate_path.exists()
    assert json.loads(promoted_path.read_text(encoding="utf-8")) == original_promoted
    assert not audit_path.exists()


def test_promote_pairs_command_records_traceable_candidate_metadata(tmp_path):
    base_dir = tmp_path / "universes"
    pipeline_cfg = _load_pipeline(tmp_path, base_dir)
    candidate_path = pairs.candidate_pair_artifact_path("1m", base_dir)
    audit_path = tmp_path / "promotion_audit.jsonl"
    _write_artifact(
        candidate_path,
        _artifact(
            [_valid_pair(), _valid_pair(sharpe_ratio=1.75)],
            generated_at="2026-01-01T00:01:00+00:00",
        ),
    )

    result = promote_pairs.promote_pairs_from_pipeline_config(
        pipeline_cfg=pipeline_cfg,
        max_age_seconds=3600,
        audit_path=audit_path,
        operator="operator-2",
        now=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc),
    )

    audit_record = json.loads(audit_path.read_text(encoding="utf-8").strip())
    assert result.audit_path == audit_path
    assert audit_record["promoted_at"] == "2026-01-01T00:05:00+00:00"
    assert audit_record["candidate"]["generated_at"] == "2026-01-01T00:01:00+00:00"
    assert audit_record["candidate"]["pair_count"] == 2
    assert audit_record["candidate"]["sha256"] == audit_record["promoted"]["sha256"]
    assert audit_record["validation"] == {"max_age_seconds": 3600}
