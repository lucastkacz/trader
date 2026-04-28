import sys
import subprocess
from prefect import flow, task, get_run_logger

from src.core.config import settings
from src.data.storage.local_parquet import ParquetStorage
from src.data.fetcher.historical_miner import HistoricalMiner
from src.engine.trader.config import (
    BacktestConfig,
    PipelineConfig,
    RiskConfig,
    StrategyConfig,
    UniverseConfig,
)
from src.screener.discovery_engine import DiscoveryEngine
from src.simulation.stress_orchestrator import StressTestOrchestrator
from src.engine.trader.live_trader import LiveTrader

# --- RESEARCH TASKS ---

@task(name="Ingest CCXT Historicals")
async def task_mine_data(pipeline_cfg: PipelineConfig, universe_cfg: UniverseConfig):
    exchange_id = pipeline_cfg.execution.exchange
    credential_tier = pipeline_cfg.execution.credential_tier
    if credential_tier == "live":
        api_key = settings.exchange_live_api_key or ""
        api_secret = settings.exchange_live_api_secret or ""
    else:
        api_key = settings.exchange_readonly_api_key or ""
        api_secret = settings.exchange_readonly_api_secret or ""

    storage = ParquetStorage(base_dir="data/parquet")
    miner = HistoricalMiner(storage)
    await miner.run(
        exchange_id=exchange_id,
        api_key=api_key,
        api_secret=api_secret,
        timeframe=pipeline_cfg.timeframe,
        historical_days=pipeline_cfg.historical_days,
        min_volume=universe_cfg.filters.min_volume_liquidity,
        limit_symbols=pipeline_cfg.max_symbols,
    )
    return True

@task(name="Alpha Cointegration Taxonomy")
def task_discover_alpha(
    timeframe: str,
    exchange: str,
    universe_cfg: UniverseConfig,
    strategy_cfg: StrategyConfig,
):
    storage = ParquetStorage(base_dir="data/parquet")
    engine = DiscoveryEngine(storage)
    engine.run(timeframe, exchange, universe_cfg, strategy_cfg)
    return True

@task(name="Vectorized Arena Filter")
def task_vector_stress(
    timeframe: str,
    exchange: str,
    backtest_cfg: BacktestConfig,
    strategy_cfg: StrategyConfig,
):
    storage = ParquetStorage(base_dir="data/parquet")
    orchestrator = StressTestOrchestrator(storage)
    orchestrator.run(timeframe, exchange, backtest_cfg.model_dump(), strategy_cfg.model_dump())
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
    strategy_cfg: StrategyConfig,
    risk_cfg: RiskConfig,
):
    trader = LiveTrader()
    await trader.run(pipeline_cfg=pipeline_cfg, strategy_cfg=strategy_cfg, risk_cfg=risk_cfg)
    return True

# --- FLOWS ---

@flow(name="Research Orchestrator Pipeline", retries=0)
async def research_flow(
    pipeline_cfg: PipelineConfig,
    universe_cfg: UniverseConfig,
    backtest_cfg: BacktestConfig,
    strategy_cfg: StrategyConfig,
    skip_fetch: bool = False,
):
    logger = get_run_logger()
    timeframe = pipeline_cfg.timeframe
    exchange = pipeline_cfg.execution.exchange
    
    logger.info(f"Starting E2E Research Validation (Timeframe: {timeframe})")
    
    if skip_fetch:
        logger.warning("DIRTY RUN ENABLED: Skipping historical API Fetch...")
    else:
        await task_mine_data(pipeline_cfg, universe_cfg)
        
    task_discover_alpha(timeframe, exchange, universe_cfg, strategy_cfg)
    task_vector_stress(timeframe, exchange, backtest_cfg, strategy_cfg)

@flow(name="Live Execution Orchestrator", retries=0)
async def execute_flow(
    pipeline_cfg: PipelineConfig,
    strategy_cfg: StrategyConfig,
    risk_cfg: RiskConfig,
    telegram_path: str = None,
):
    logger = get_run_logger()
    timeframe = pipeline_cfg.timeframe
        
    logger.info(f"Starting LIVE Execution (Timeframe: {timeframe})")
    
    if telegram_path:
        task_execute_telegram(telegram_path=telegram_path)
    
    await task_execute_trader(pipeline_cfg, strategy_cfg, risk_cfg)
