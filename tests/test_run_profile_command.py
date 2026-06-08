import argparse
import json
import sys

import pytest

import main


@pytest.mark.asyncio
async def test_run_profile_command_loads_referenced_typed_configs(monkeypatch):
    captured = {}

    async def fake_research_flow(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(main, "research_flow", fake_research_flow)
    monkeypatch.setattr(
        sys,
        "argv",
        ["main.py", "run", "--config", "configs/runs/dev_1m_research.yml"],
    )

    await main.main()

    assert captured["pipeline_cfg"].name == "DEV 1M Sandbox"
    assert captured["venue_cfg"].exchange_id == "bybit"
    assert captured["exchange_config"].name == "linear_usdt_swap"
    assert captured["universe_cfg"].name == "DEV 1M Lenient Workflow Universe"
    assert captured["backtest_cfg"].name == "DEV 1M Lenient Workflow Stress Engine"
    assert captured["strategy_cfg"].name == "DEV Lenient Workflow Mean Reversion V1"
    assert captured["skip_fetch"] is False


@pytest.mark.asyncio
async def test_execute_command_applies_bounded_runtime_overrides(monkeypatch):
    captured = {}

    async def fake_execute_flow(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(main, "execute_flow", fake_execute_flow)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "main.py",
            "execute",
            "--pipeline",
            "configs/pipelines/dev.yml",
            "--venue",
            "configs/exchange/venues/dev.yml",
            "--market-profile",
            "configs/exchange/market_profiles/linear_usdt_swap.yml",
            "--strategy",
            "configs/strategy/dev.yml",
            "--risk",
            "configs/risk/alpha_v1.yml",
            "--max-ticks",
            "2",
            "--heartbeat-seconds",
            "1",
        ],
    )

    await main.main()

    pipeline_cfg = captured["pipeline_cfg"]
    assert pipeline_cfg.execution.max_ticks == 2
    assert pipeline_cfg.execution.heartbeat_seconds == 1
    assert pipeline_cfg.execution.order_execution.mode == "state_only"
    assert captured["venue_cfg"].exchange_id == "bybit"
    assert captured["exchange_config"].name == "linear_usdt_swap"
    assert captured["telegram_path"] is None


def test_execute_command_bounds_must_be_positive():
    with pytest.raises(argparse.ArgumentTypeError):
        main._positive_int("0")


@pytest.mark.asyncio
async def test_main_risk_kill_switch_command_inspects_state(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "trades.db"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "main.py",
            "risk-kill-switch",
            "--db-path",
            str(db_path),
            "--json",
            "inspect",
        ],
    )

    await main.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["action"] == "inspect"
    assert payload["db_path"] == str(db_path)
    assert payload["state"] == {
        "active": False,
        "reason": None,
        "activated_at": None,
    }
