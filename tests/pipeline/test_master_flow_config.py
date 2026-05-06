import pytest

from src.engine.trader.config import (
    load_pipeline_config,
    load_risk_config,
    load_strategy_config,
    load_universe_config,
)
from src.pipeline import master_flow


@pytest.mark.asyncio
async def test_task_mine_data_uses_typed_pipeline_and_universe_config(monkeypatch):
    captured = {}

    async def fake_run(self, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(master_flow.HistoricalMiner, "run", fake_run)

    pipeline_cfg = load_pipeline_config("configs/pipelines/dev.yml")
    universe_cfg = load_universe_config("configs/universe/alpha_v1.yml")

    result = await master_flow.task_mine_data.fn(pipeline_cfg, universe_cfg)

    assert result is True
    assert captured["exchange_id"] == pipeline_cfg.execution.exchange
    assert captured["timeframe"] == pipeline_cfg.timeframe
    assert captured["historical_days"] == pipeline_cfg.historical_days
    assert captured["min_volume"] == universe_cfg.filters.min_volume_liquidity
    assert captured["limit_symbols"] == pipeline_cfg.max_symbols


def test_task_discover_alpha_passes_typed_research_config(monkeypatch):
    captured = {}

    def fake_run(self, timeframe, exchange, universe_cfg, strategy_cfg, artifact_base_dir):
        captured["timeframe"] = timeframe
        captured["exchange"] = exchange
        captured["universe_cfg"] = universe_cfg
        captured["strategy_cfg"] = strategy_cfg
        captured["artifact_base_dir"] = artifact_base_dir

    monkeypatch.setattr(master_flow.DiscoveryEngine, "run", fake_run)

    pipeline_cfg = load_pipeline_config("configs/pipelines/dev.yml")
    universe_cfg = load_universe_config("configs/universe/alpha_v1.yml")
    strategy_cfg = load_strategy_config("configs/strategy/alpha_v1.yml")

    result = master_flow.task_discover_alpha.fn(pipeline_cfg, universe_cfg, strategy_cfg)

    assert result is True
    assert captured["timeframe"] == pipeline_cfg.timeframe
    assert captured["exchange"] == pipeline_cfg.execution.exchange
    assert captured["universe_cfg"] == universe_cfg
    assert captured["strategy_cfg"] == strategy_cfg
    assert captured["artifact_base_dir"] == pipeline_cfg.execution.artifact_base_dir


def test_task_vector_stress_passes_typed_research_config_and_artifact_paths(monkeypatch):
    captured = {}

    def fake_run(self, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(master_flow.PairStressFilter, "run", fake_run)

    pipeline_cfg = load_pipeline_config("configs/pipelines/dev.yml")
    strategy_cfg = load_strategy_config("configs/strategy/alpha_v1.yml")
    backtest_cfg = master_flow.BacktestConfig.model_validate({
        "name": "test",
        "grid_search": {"entry_z_scores": [2.0], "lookback_bars": [60]},
        "friction": {
            "maker_fee": 0.0002,
            "taker_fee": 0.0006,
            "annual_fund_rate": 0.01,
        },
    })

    result = master_flow.task_vector_stress.fn(pipeline_cfg, backtest_cfg, strategy_cfg)

    assert result is True
    assert captured["timeframe"] == pipeline_cfg.timeframe
    assert captured["exchange"] == pipeline_cfg.execution.exchange
    assert str(captured["input_pairs_path"]).endswith("candidate_surviving_pairs.json")
    assert captured["output_artifact_base_dir"] == pipeline_cfg.execution.artifact_base_dir
    assert captured["backtest_cfg"] == backtest_cfg
    assert captured["strategy_cfg"] == strategy_cfg


@pytest.mark.asyncio
async def test_task_execute_trader_passes_typed_risk_config(monkeypatch):
    captured = {}

    async def fake_run(self, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(master_flow.LiveTrader, "run", fake_run)

    pipeline_cfg = load_pipeline_config("configs/pipelines/dev.yml")
    strategy_cfg = load_strategy_config("configs/strategy/alpha_v1.yml")
    risk_cfg = load_risk_config("configs/risk/alpha_v1.yml")

    result = await master_flow.task_execute_trader.fn(pipeline_cfg, strategy_cfg, risk_cfg)

    assert result is True
    assert captured["pipeline_cfg"] == pipeline_cfg
    assert captured["strategy_cfg"] == strategy_cfg
    assert captured["risk_cfg"] == risk_cfg
