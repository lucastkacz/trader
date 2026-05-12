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
    assert captured["universe_cfg"].name == "DEV 1M Broader Liquid Universe"
    assert captured["backtest_cfg"].name == "DEV 1M Vector Stress Engine"
    assert captured["strategy_cfg"].name == "Institutional Mean Reversion V1"
    assert captured["skip_fetch"] is True
