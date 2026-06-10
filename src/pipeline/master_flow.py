import sys
import subprocess
from datetime import datetime, timezone
from prefect import flow, task, get_run_logger

from src.core.config import settings
from src.exchange.config.venue import CcxtExchangeConfig, ExchangeVenueConfig
from src.exchange.data.ccxt_adapter import CcxtMarketDataAdapter
from src.data.sync.config import load_ohlcv_backfill_config
from src.data.storage.local_parquet import LocalOHLCVParquetStore
from src.data.sync import (
    OHLCVBackfillRequest,
    OHLCVBackfillService,
    OHLCVMarketMetadata,
)
from src.engine.trader.config import (
    BacktestConfig,
    PipelineConfig,
    RiskConfig,
    StrategyConfig,
    UniverseConfig,
)
from src.universe.discovery import DiscoveryEngine
from src.engine.trader.runtime.artifacts import candidate_pair_artifact_path
from src.engine.trader.runtime.trader_runner import run_trader_loop
from src.research.pair_stress_filter import PairStressFilter
from src.universe.selection import select_symbols_for_backfill
from src.utils.timeframe_math import last_closed_candle_open_ms

# --- RESEARCH TASKS ---

@task(name="Ingest CCXT Historicals")
async def task_mine_data(
    pipeline_cfg: PipelineConfig,
    venue_cfg: ExchangeVenueConfig,
    exchange_config: CcxtExchangeConfig,
    universe_cfg: UniverseConfig,
):
    exchange_id = venue_cfg.exchange_id
    credential_tier = venue_cfg.credential_tier
    if credential_tier == "live":
        api_key = settings.exchange_live_api_key or ""
        api_secret = settings.exchange_live_api_secret or ""
    else:
        api_key = settings.exchange_readonly_api_key or ""
        api_secret = settings.exchange_readonly_api_secret or ""

    storage = LocalOHLCVParquetStore(
        base_dir=pipeline_cfg.execution.market_data_base_dir
    )
    backfill_policy = load_ohlcv_backfill_config(
        pipeline_cfg.data.backfill_policy_config
    ).to_fetch_policy()
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    end_ts = last_closed_candle_open_ms(pipeline_cfg.timeframe, now_ms=now_ms)
    pre_download = universe_cfg.filters.pre_download
    pre_download_timeframes = {
        pre_download.daily_liquidity.timeframe,
        pre_download.intraday_liquidity.timeframe,
        pre_download.mega_caps.timeframe,
    }
    pre_download_end_ts_by_timeframe = {
        timeframe: last_closed_candle_open_ms(timeframe, now_ms=now_ms)
        for timeframe in pre_download_timeframes
    }
    start_ts = end_ts - pipeline_cfg.historical_days * 86_400_000

    async with CcxtMarketDataAdapter(
        exchange_id,
        api_key,
        api_secret,
        exchange_config,
    ) as market_data:
        service = OHLCVBackfillService(
            market_data=market_data,
            store=storage,
            policy=backfill_policy,
        )
        selection = await select_symbols_for_backfill(
            market_data=market_data,
            universe_cfg=universe_cfg,
            pre_download_end_ts_by_timeframe=pre_download_end_ts_by_timeframe,
            prefilter_pause_seconds=backfill_policy.request_pause_seconds,
        )
        if not selection.symbols:
            raise ValueError("Universe selection returned no symbols for OHLCV backfill")
        await service.run(
            OHLCVBackfillRequest(
                exchange_id=exchange_id,
                timeframe=pipeline_cfg.timeframe,
                start_ts=start_ts,
                end_ts=end_ts,
                symbols=selection.symbols,
                market=OHLCVMarketMetadata(
                    market_type=exchange_config.market_contract.default_type,
                    market_sub_type=exchange_config.market_contract.default_sub_type,
                    settle=exchange_config.market_contract.default_settle,
                ),
            )
        )
    return True

@task(name="Alpha Cointegration Taxonomy")
def task_discover_alpha(
    pipeline_cfg: PipelineConfig,
    venue_cfg: ExchangeVenueConfig,
    universe_cfg: UniverseConfig,
    strategy_cfg: StrategyConfig,
):
    storage = LocalOHLCVParquetStore(
        base_dir=pipeline_cfg.execution.market_data_base_dir
    )
    engine = DiscoveryEngine(storage)
    engine.run(
        timeframe=pipeline_cfg.timeframe,
        exchange=venue_cfg.exchange_id,
        universe_cfg=universe_cfg,
        strategy_cfg=strategy_cfg,
        artifact_base_dir=pipeline_cfg.execution.artifact_base_dir,
    )
    return True

@task(name="Pair Stress Filter")
def task_vector_stress(
    pipeline_cfg: PipelineConfig,
    venue_cfg: ExchangeVenueConfig,
    backtest_cfg: BacktestConfig,
    strategy_cfg: StrategyConfig,
):
    storage = LocalOHLCVParquetStore(
        base_dir=pipeline_cfg.execution.market_data_base_dir
    )
    stress_filter = PairStressFilter(storage)
    stress_filter.run(
        timeframe=pipeline_cfg.timeframe,
        exchange=venue_cfg.exchange_id,
        input_pairs_path=candidate_pair_artifact_path(
            pipeline_cfg.timeframe,
            pipeline_cfg.execution.artifact_base_dir,
        ),
        output_artifact_base_dir=pipeline_cfg.execution.artifact_base_dir,
        backtest_cfg=backtest_cfg,
        strategy_cfg=strategy_cfg,
    )
    return True

# --- EXECUTION TASKS ---

@task(name="Launch Telegram Daemon")
def task_execute_telegram(telegram_path: str):
    logger = get_run_logger()
    logger.info("─── Spawning Telegram Daemon Background Process ───")
    # Using subprocess.Popen here so it completely detaches and runs infinitely in the background
    cmd = [sys.executable, "-m", "src.interfaces.telegram.daemon", "--config", telegram_path]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    logger.info("Telegram Bot daemon spawned successfully.")
    return True

@task(name="Launch Live Trader")
async def task_execute_trader(
    pipeline_cfg: PipelineConfig,
    venue_cfg: ExchangeVenueConfig,
    exchange_config: CcxtExchangeConfig,
    strategy_cfg: StrategyConfig,
    risk_cfg: RiskConfig,
):
    await run_trader_loop(
        pipeline_cfg=pipeline_cfg,
        venue_cfg=venue_cfg,
        exchange_config=exchange_config,
        strategy_cfg=strategy_cfg,
        risk_cfg=risk_cfg,
    )
    return True

# --- FLOWS ---

@flow(name="Research Orchestrator Pipeline", retries=0)
async def research_flow(
    pipeline_cfg: PipelineConfig,
    venue_cfg: ExchangeVenueConfig,
    exchange_config: CcxtExchangeConfig,
    universe_cfg: UniverseConfig,
    backtest_cfg: BacktestConfig,
    strategy_cfg: StrategyConfig,
    skip_fetch: bool = False,
):
    logger = get_run_logger()
    timeframe = pipeline_cfg.timeframe
    
    logger.info(f"Starting E2E Research Validation (Timeframe: {timeframe})")
    
    if skip_fetch:
        logger.warning("DIRTY RUN ENABLED: Skipping historical API Fetch...")
    else:
        await task_mine_data(pipeline_cfg, venue_cfg, exchange_config, universe_cfg)
        
    task_discover_alpha(pipeline_cfg, venue_cfg, universe_cfg, strategy_cfg)
    task_vector_stress(pipeline_cfg, venue_cfg, backtest_cfg, strategy_cfg)

@flow(name="Live Execution Orchestrator", retries=0)
async def execute_flow(
    pipeline_cfg: PipelineConfig,
    venue_cfg: ExchangeVenueConfig,
    exchange_config: CcxtExchangeConfig,
    strategy_cfg: StrategyConfig,
    risk_cfg: RiskConfig,
    telegram_path: str | None = None,
):
    logger = get_run_logger()
    timeframe = pipeline_cfg.timeframe
        
    logger.info(f"Starting LIVE Execution (Timeframe: {timeframe})")
    
    if telegram_path:
        task_execute_telegram(telegram_path=telegram_path)
    
    await task_execute_trader(
        pipeline_cfg,
        venue_cfg,
        exchange_config,
        strategy_cfg,
        risk_cfg,
    )
