# The Agnostic Orchestrator Architecture

As the pipeline matures, relying on hardcoded switches (such as `if TURBO_MODE:`) becomes an architectural liability. A truly robust system must be mathematically agnostic to the timeframe it trades on. The Orchestrator's role is to construct the entire trading infrastructure dynamically, delegating behavior entirely to declarative YAML blueprints.

## 1. Annihilating "Turbo Mode"

Previously, the `ghost_trader.py` engine had two hardcoded states:
- Production: Wait for strict 4-hour boundaries.
- Turbo: Sleep exactly 60 seconds and loop.

This rigidity prevented the system from easily adapting to new timeframes (like 3-hour or 15-minute candles). We have replaced this with a deterministic **Heartbeat Engine** defined directly in the Pipeline blueprint.

### Pipeline Configuration Example (`configs/pipelines/prod_4h.yml`)
```yaml
pipeline:
  name: "Production 4H Engine"
  timeframe: "4h"
  historical_days: 1460
  execution:
    sync_to_boundary: true     # Engine waits precisely for 00:00:05, 04:00:05, etc.
    heartbeat_seconds: null    # Not used when syncing to strict boundaries
```

### Pipeline Configuration Example (`configs/pipelines/turbo_1m.yml`)
```yaml
pipeline:
  name: "Turbo 1M Sandbox"
  timeframe: "1m"
  execution:
    sync_to_boundary: false    # Engine ignores standard exchange boundaries
    heartbeat_seconds: 60      # Engine sleeps exactly 60 seconds between loops
    max_ticks: null            # Can run endlessly (null) or stop after N ticks for testing
```

By reading these keys, `ghost_trader.py` can operate on *any* timeframe seamlessly.

## 2. Parameterizing the Vector Screener

The `vector_screener.py` acts as Epoch 2, validating cointegrated pairs across a parameter grid. Previously, the parameter grids (lookback windows, Z-score targets) and the simulation friction (fees, slippage) were hardcoded into Python arrays.

These have been cleanly offloaded to the Strategy blueprint, enabling dynamic, scriptless parameter sweeps.

### Strategy Configuration Example (`configs/strategies/alpha_v1.yml`)
```yaml
strategy:
  vector_screener:
    grid_search:
      entry_z_scores: [1.5, 2.0, 2.5]
      lookback_bars: [60, 120, 180] 
    friction:
      maker_fee: 0.0002
      taker_fee: 0.0006
      annual_fund_rate: 0.10
    volatility_lookback_bars: 60
```

## 3. End-to-End Orchestration (Telegram Integration)

The Orchestrator (`scripts/run_pipeline.py`) is no longer just a math pipeline—it is a full infrastructure spawner.

It now natively supports booting the **Telegram Daemon** as a background Prefect task before the Ghost Trader is launched. This is driven by environment-specific Telegram blueprints.

### Telegram Configuration Example (`configs/telegram/dev.yml`)
```yaml
telegram:
  environment: "DEV"
  bot_name: "@TurboBot"
  db_path: "data/db/dev_user_commands.db"
  # Authentication tokens should be securely ingested via .env, not hardcoded.
```

When executing `python -m scripts.run_pipeline --pipeline configs/pipelines/turbo_1m.yml --strategy configs/strategies/alpha_v1.yml --telegram configs/telegram/dev.yml`, the Orchestrator will:
1. Mine Data
2. Cluster & Discover Pairs
3. Run Vector Stress Tests
4. **Boot up `@TurboBot` Telegram interface**
5. Start the Agnostic Ghost Trader

This realizes the vision of a completely flexible, declarative, and robust pipeline architecture.
