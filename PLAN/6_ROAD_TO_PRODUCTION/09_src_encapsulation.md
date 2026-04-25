# Phase 3: SRC Encapsulation Architecture

The goal of this phase is to elevate the codebase from procedural scripts into an institutional-grade, object-oriented system. We are annihilating the `scripts/` directory and moving all orchestration logic into strictly defined classes inside `src/`.

## 1. Domain-Driven Configurations

The monolithic `strategy.yml` has been split to strictly separate the hypothetical constructs (backtesting) from live execution realities.

1. **`configs/universe/`**: Governs what we trade (liquidity filters, Louvain correlation thresholds).
2. **`configs/backtest/`**: Governs historical simulation (grid search Z-scores, maker/taker fees, funding rates).
3. **`configs/strategy/`**: Governs live execution (entry/exit Z-scores, stop losses).
4. **`configs/pipeline/`**: Governs the hardware environment (timeframe, sync boundaries, sleep heartbeats).
5. **`configs/telegram/`**: Governs alerting integrations.

## 2. Object Encapsulation

The chaotic 500-line procedural scripts have been encapsulated into their respective domain packages:

- **Historical Mining**: The logic to paginate Bybit klines is now `src.data.fetcher.historical_miner.HistoricalMiner`.
- **Discovery Engine**: The orchestration of `DataMaturityFilter`, `MatrixBuilder`, and `CointegrationEngine` is now encapsulated in `src.screener.discovery_engine.DiscoveryEngine`.
- **Stress Testing**: The Vectorized Simulator is now governed by `src.simulation.stress_orchestrator.StressTestOrchestrator`.
- **Live Trading**: The massive `ghost_trader` logic has been refactored into the elegant event loop of `src.engine.ghost.live_trader.LiveGhostTrader`.

## 3. The Unified CLI (`main.py`)

A single entrypoint at the root directory now governs the entire quant system, split into two distinct modes:

### Research Mode
Combines data mining, universe generation, and vector stress testing.
```bash
python main.py research --pipeline configs/pipelines/turbo_1m.yml \
                        --universe configs/universe/alpha_v1.yml \
                        --backtest configs/backtest/stress_test.yml
```

### Execute Mode
Combines live execution and telegram alerting, relying only on the validated `surviving_pairs.json`.
```bash
python main.py execute --pipeline configs/pipelines/turbo_1m.yml \
                       --strategy configs/strategy/alpha_v1.yml \
                       --telegram configs/telegram/dev.yml
```
