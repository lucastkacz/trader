import sys
import subprocess
from prefect import flow, task, get_run_logger

from src.data.storage.local_parquet import ParquetStorage
from src.data.fetcher.historical_miner import HistoricalMiner
from src.screener.discovery_engine import DiscoveryEngine
from src.simulation.stress_orchestrator import StressTestOrchestrator
from src.engine.ghost.live_trader import LiveGhostTrader

# --- RESEARCH TASKS ---

@task(name="Ingest CCXT Historicals")
async def task_mine_data(timeframe: str, historical_days: int):
    storage = ParquetStorage()
    miner = HistoricalMiner(storage)
    await miner.run(timeframe=timeframe, historical_days=historical_days)
    return True

@task(name="Alpha Cointegration Taxonomy")
def task_discover_alpha(timeframe: str, universe_cfg: dict, strategy_cfg: dict):
    storage = ParquetStorage()
    engine = DiscoveryEngine(storage)
    engine.run(timeframe, universe_cfg, strategy_cfg)
    return True

@task(name="Vectorized Arena Filter")
def task_vector_stress(timeframe: str, backtest_cfg: dict, strategy_cfg: dict):
    storage = ParquetStorage()
    orchestrator = StressTestOrchestrator(storage)
    orchestrator.run(timeframe, backtest_cfg, strategy_cfg)
    return True

# --- EXECUTION TASKS ---

@task(name="Launch Telegram Daemon")
def task_execute_telegram(telegram_path: str):
    logger = get_run_logger()
    logger.info(f"─── Spawning Telegram Daemon Background Process ───")
    # Using subprocess.Popen here so it completely detaches and runs infinitely in the background
    cmd = [sys.executable, "-m", "src.core.telegram_daemon", "--config", telegram_path]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    logger.info(f"Telegram Bot daemon spawned successfully.")
    return True

@task(name="Launch Live Ghost Trader")
async def task_execute_ghost(pipeline_cfg: dict, strategy_cfg: dict):
    trader = LiveGhostTrader()
    await trader.run(pipeline_cfg=pipeline_cfg, strategy_cfg=strategy_cfg)
    return True

# --- FLOWS ---

@flow(name="Research Orchestrator Pipeline", retries=0)
async def research_flow(pipeline_cfg: dict, universe_cfg: dict, backtest_cfg: dict, strategy_cfg: dict, skip_fetch: bool = False):
    logger = get_run_logger()
    timeframe = pipeline_cfg["timeframe"]
    historical_days = pipeline_cfg["historical_days"]
    
    logger.info(f"Starting E2E Research Validation (Timeframe: {timeframe})")
    
    if skip_fetch:
        logger.warning("DIRTY RUN ENABLED: Skipping historical API Fetch...")
    else:
        await task_mine_data(timeframe, historical_days)
        
    task_discover_alpha(timeframe, universe_cfg, strategy_cfg)
    task_vector_stress(timeframe, backtest_cfg, strategy_cfg)

@flow(name="Live Execution Orchestrator", retries=0)
async def execute_flow(pipeline_cfg: dict, strategy_cfg: dict, telegram_path: str = None):
    logger = get_run_logger()
    timeframe = pipeline_cfg["timeframe"]
        
    logger.info(f"Starting LIVE Execution (Timeframe: {timeframe})")
    
    if telegram_path:
        task_execute_telegram(telegram_path=telegram_path)
    
    await task_execute_ghost(pipeline_cfg, strategy_cfg)
