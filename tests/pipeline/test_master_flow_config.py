from types import SimpleNamespace

import pytest

from src.engine.trader.config import (
    load_pipeline_config,
    load_risk_config,
    load_strategy_config,
    load_universe_config,
)
from src.exchange.config.venue import (
    load_ccxt_exchange_config,
    load_exchange_venue_config,
)
from src.pipeline import master_flow
from src.utils.timeframe_math import get_timeframe_ms


def _venue_cfg():
    return load_exchange_venue_config("configs/exchange/venues/dev.yml")


def _exchange_config():
    return load_ccxt_exchange_config(
        "configs/exchange/market_profiles/linear_usdt_swap.yml"
    )


@pytest.mark.asyncio
async def test_task_mine_data_uses_typed_pipeline_and_universe_config(monkeypatch):
    captured = {}

    class FakeMarketDataAdapter:
        def __init__(self, exchange_id, api_key, api_secret, exchange_config):
            captured["adapter_exchange_id"] = exchange_id
            captured["adapter_api_key"] = api_key
            captured["adapter_api_secret"] = api_secret
            captured["exchange_config"] = exchange_config

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc_info):
            return None

    async def fake_run(self, request):
        captured["request"] = request
        captured["market_data"] = self.market_data
        captured["store"] = self.store
        captured["policy"] = self.policy

    async def fake_select_symbols_for_backfill(**kwargs):
        captured["selection_kwargs"] = kwargs
        return SimpleNamespace(symbols=["BTC/USDT:USDT", "ETH/USDT:USDT"])

    monkeypatch.setattr(master_flow, "CcxtMarketDataAdapter", FakeMarketDataAdapter)
    monkeypatch.setattr(master_flow.OHLCVBackfillService, "run", fake_run)
    monkeypatch.setattr(
        master_flow,
        "select_symbols_for_backfill",
        fake_select_symbols_for_backfill,
    )

    pipeline_cfg = load_pipeline_config("configs/pipelines/dev.yml")
    venue_cfg = _venue_cfg()
    exchange_config = _exchange_config()
    universe_cfg = load_universe_config("configs/universe/dev.yml")

    result = await master_flow.task_mine_data.fn(
        pipeline_cfg,
        venue_cfg,
        exchange_config,
        universe_cfg,
    )

    assert result is True
    request = captured["request"]
    assert captured["adapter_exchange_id"] == venue_cfg.exchange_id
    assert captured["exchange_config"].name == "linear_usdt_swap"
    assert request.exchange_id == venue_cfg.exchange_id
    assert request.timeframe == pipeline_cfg.timeframe
    assert request.symbols == ["BTC/USDT:USDT", "ETH/USDT:USDT"]
    assert request.end_ts - request.start_ts == pipeline_cfg.historical_days * 86_400_000
    assert request.end_ts % get_timeframe_ms(pipeline_cfg.timeframe) == 0
    prefilter_end_ts = captured["selection_kwargs"]["prefilter_end_ts"]
    prefilter_timeframe = universe_cfg.filters.prefilter_liquidity.timeframe
    assert prefilter_end_ts % get_timeframe_ms(prefilter_timeframe) == 0
    assert captured["selection_kwargs"]["universe_cfg"] == universe_cfg
    assert captured["policy"].fetch_limit == 1000


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
    venue_cfg = _venue_cfg()
    universe_cfg = load_universe_config("configs/universe/dev.yml")
    strategy_cfg = load_strategy_config("configs/strategy/dev.yml")

    result = master_flow.task_discover_alpha.fn(
        pipeline_cfg,
        venue_cfg,
        universe_cfg,
        strategy_cfg,
    )

    assert result is True
    assert captured["timeframe"] == pipeline_cfg.timeframe
    assert captured["exchange"] == venue_cfg.exchange_id
    assert captured["universe_cfg"] == universe_cfg
    assert captured["strategy_cfg"] == strategy_cfg
    assert captured["artifact_base_dir"] == pipeline_cfg.execution.artifact_base_dir


def test_task_vector_stress_passes_typed_research_config_and_artifact_paths(monkeypatch):
    captured = {}

    def fake_run(self, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(master_flow.PairStressFilter, "run", fake_run)

    pipeline_cfg = load_pipeline_config("configs/pipelines/dev.yml")
    venue_cfg = _venue_cfg()
    strategy_cfg = load_strategy_config("configs/strategy/dev.yml")
    backtest_cfg = master_flow.BacktestConfig.model_validate({
        "name": "test",
        "grid_search": {"entry_z_scores": [2.0], "lookback_bars": [60]},
        "friction": {
            "maker_fee": 0.0002,
            "taker_fee": 0.0006,
            "annual_fund_rate": 0.01,
        },
    })

    result = master_flow.task_vector_stress.fn(
        pipeline_cfg,
        venue_cfg,
        backtest_cfg,
        strategy_cfg,
    )

    assert result is True
    assert captured["timeframe"] == pipeline_cfg.timeframe
    assert captured["exchange"] == venue_cfg.exchange_id
    assert str(captured["input_pairs_path"]).endswith("candidate_surviving_pairs.json")
    assert captured["output_artifact_base_dir"] == pipeline_cfg.execution.artifact_base_dir
    assert captured["backtest_cfg"] == backtest_cfg
    assert captured["strategy_cfg"] == strategy_cfg


def test_execute_flow_allows_telegram_to_be_absent():
    pipeline_cfg = load_pipeline_config("configs/pipelines/dev.yml")
    strategy_cfg = load_strategy_config("configs/strategy/dev.yml")
    risk_cfg = load_risk_config("configs/risk/alpha_v1.yml")

    parameters = master_flow.execute_flow.validate_parameters(
        {
            "pipeline_cfg": pipeline_cfg,
            "venue_cfg": _venue_cfg(),
            "exchange_config": _exchange_config(),
            "strategy_cfg": strategy_cfg,
            "risk_cfg": risk_cfg,
            "telegram_path": None,
        }
    )

    assert parameters["telegram_path"] is None


@pytest.mark.asyncio
async def test_task_execute_trader_passes_typed_risk_config(monkeypatch):
    captured = {}

    async def fake_run_trader_loop(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(master_flow, "run_trader_loop", fake_run_trader_loop)

    pipeline_cfg = load_pipeline_config("configs/pipelines/dev.yml")
    venue_cfg = _venue_cfg()
    exchange_config = _exchange_config()
    strategy_cfg = load_strategy_config("configs/strategy/dev.yml")
    risk_cfg = load_risk_config("configs/risk/alpha_v1.yml")

    result = await master_flow.task_execute_trader.fn(
        pipeline_cfg,
        venue_cfg,
        exchange_config,
        strategy_cfg,
        risk_cfg,
    )

    assert result is True
    assert captured["pipeline_cfg"] == pipeline_cfg
    assert captured["venue_cfg"] == venue_cfg
    assert captured["exchange_config"] == exchange_config
    assert captured["strategy_cfg"] == strategy_cfg
    assert captured["risk_cfg"] == risk_cfg
