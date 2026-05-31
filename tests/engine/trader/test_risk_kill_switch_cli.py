import json

from src.engine.trader.cli import risk_kill_switch
from src.engine.trader.runtime.risk import get_risk_kill_switch_state
from src.engine.trader.runtime.risk.kill_switch import RISK_KILL_SWITCH_KEY
from src.engine.trader.state.manager import TradeStateManager


def test_risk_kill_switch_cli_activates_switch(tmp_path, capsys):
    db_path = tmp_path / "trades.db"

    exit_code = risk_kill_switch.main(
        [
            "--db-path",
            str(db_path),
            "activate",
            "--reason",
            "operator stop new exposure",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Active: True" in captured.out
    assert "operator stop new exposure" in captured.out

    state = TradeStateManager(db_path=str(db_path))
    try:
        switch_state = get_risk_kill_switch_state(state)
    finally:
        state.close()

    assert switch_state.active is True
    assert switch_state.reason == "operator stop new exposure"
    assert switch_state.activated_at is not None


def test_risk_kill_switch_cli_clears_switch(tmp_path, capsys):
    db_path = tmp_path / "trades.db"
    risk_kill_switch.main(
        [
            "--db-path",
            str(db_path),
            "activate",
            "--reason",
            "operator stop new exposure",
        ]
    )
    capsys.readouterr()

    exit_code = risk_kill_switch.main(["--db-path", str(db_path), "clear"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Action: clear" in captured.out
    assert "Active: False" in captured.out

    state = TradeStateManager(db_path=str(db_path))
    try:
        switch_state = get_risk_kill_switch_state(state)
    finally:
        state.close()

    assert switch_state.active is False
    assert switch_state.reason is None
    assert switch_state.activated_at is None


def test_risk_kill_switch_cli_inspects_current_state_as_json(tmp_path, capsys):
    db_path = tmp_path / "trades.db"
    risk_kill_switch.main(
        [
            "--db-path",
            str(db_path),
            "activate",
            "--reason",
            "manual review",
        ]
    )
    capsys.readouterr()

    exit_code = risk_kill_switch.main(
        ["--db-path", str(db_path), "--json", "inspect"]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["action"] == "inspect"
    assert payload["db_path"] == str(db_path)
    assert payload["state"]["active"] is True
    assert payload["state"]["reason"] == "manual review"


def test_risk_kill_switch_cli_treats_malformed_state_as_inactive(tmp_path, capsys):
    db_path = tmp_path / "trades.db"
    state = TradeStateManager(db_path=str(db_path))
    try:
        state.set_runtime_state(
            RISK_KILL_SWITCH_KEY,
            {"active": "yes", "reason": ["not", "typed"]},
        )
    finally:
        state.close()

    exit_code = risk_kill_switch.main(
        ["--db-path", str(db_path), "--json", "inspect"]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["state"] == {
        "active": False,
        "reason": None,
        "activated_at": None,
    }


def test_risk_kill_switch_cli_resolves_db_path_from_pipeline(tmp_path):
    db_path = tmp_path / "configured.db"
    pipeline_path = _write_pipeline_config(tmp_path, db_path)
    parser = risk_kill_switch.build_parser()
    args = parser.parse_args(
        [
            "--pipeline",
            str(pipeline_path),
            "activate",
            "--reason",
            "pipeline resolved",
        ]
    )

    result = risk_kill_switch.risk_kill_switch_from_args(args)

    assert result.db_path == db_path
    assert result.state.active is True
    assert result.state.reason == "pipeline resolved"


def _write_pipeline_config(tmp_path, db_path):
    path = tmp_path / "pipeline.yml"
    path.write_text(
        f"""
pipeline:
  name: test-pipeline
  timeframe: "1m"
  historical_days: 1
  max_symbols: null
  execution:
    exchange: "bybit"
    credential_tier: "readonly"
    market_data_base_dir: "{tmp_path / "market_data"}"
    artifact_base_dir: "{tmp_path / "universes"}"
    db_path: "{db_path}"
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
