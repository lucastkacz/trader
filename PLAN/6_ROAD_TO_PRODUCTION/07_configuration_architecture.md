# Configuration Architecture: Decoupling Pipeline and Strategy

As the platform scales from local 1-minute turbo sandboxes to 4-hour live capital deployment, hardcoding logic into Python scripts creates fragile architecture. A true Orchestrator should act as a blank, mechanical engine that dynamically adapts its behavior based on decoupled blueprints.

To achieve this, we are fundamentally separating **how the system runs** (The Pipeline) from **what the system trades** (The Strategy). 

## The Dual-YAML Architecture

We will implement a Two-File composition system. Instead of a monolithic configuration, the Orchestrator will accept two distinct YAML files:
`python -m scripts.run_turbo_workflow --pipeline configs/pipelines/turbo_1m.yml --strategy configs/strategies/alpha_v1.yml`

This allows you to test the exact same mathematical Strategy (`alpha_v1`) across entirely different Pipelines (`turbo_1m` vs `prod_4h`) without copy-pasting parameters.

---

## 1. The Pipeline Blueprint (`configs/pipelines/*.yml`)

The Pipeline configuration is strictly responsible for **Infrastructure, APIs, and Orchestration**. It has zero knowledge of trading math.

### Example: `configs/pipelines/turbo_1m.yml`
```yaml
pipeline:
  name: "Turbo 1M Sandbox"
  timeframe: "1m"
  historical_days: 1
  max_symbols: 100       # Limits API ingestion size for quick testing
  turbo_mode: true       # Determines if ghost trader uses 60s micro-sleeps
  max_ticks: null        # Null = endless. Integer = auto-stop after N ticks
```

**Why this matters:** If you want to switch from 1m testing to 4h paper-trading, you simply point the orchestrator to `configs/pipelines/prod_4h.yml`. The Python code (`run_turbo_workflow.py`, `mine_data.py`) parses these limits and alters how much data it downloads and how long it sleeps, with zero code changes.

---

## 2. The Strategy Blueprint (`configs/strategies/*.yml`)

The Strategy configuration is strictly responsible for **Quantitative Mathematics, Filtering, and Risk**. I have thoroughly reviewed your `PLAN/3_QUANT_AND_TRADING_ENGINE` architecture and mapped out the exhaustive list of hyperparameters your engine requires.

### Example: `configs/strategies/alpha_v1.yml`
```yaml
strategy:
  name: "Institutional Alpha V1"
  
  # Phase 1: Universe Sieve (volume_liquidity.py & data_maturity.py)
  filters:
    exclude_top_n_mega_caps: 5
    volume_lookback_bars: 1440           # Replaces 30-day rigid rule. For 1m = 1 day of bars.
    min_volume_liquidity: 20000000       # $20M minimum volume over the lookback
    max_volume_liquidity: 2000000000     # $2B ceiling to filter mega-caps without hardcoding tickers
    min_data_maturity_bars: 1080         # e.g., 180 days for 4H, or 18 hours for 1m
  
  # Phase 3: Clustering (returns_matrix.py & graph_louvain.py)
  clustering:
    returns_clip_percentile: 0.01        # Winsorization clipping to prevent pump-and-dump skew
    louvain_correlation_threshold: 0.5   # Minimum Spearman rank correlation to form an edge
  
  # Phase 4: Cointegration (cointegration_mesh.py)
  cointegration:
    p_value_threshold: 0.05
    max_half_life_bars: 84               # Maximum mean-reversion speed. e.g., 14 days on 4H
  
  # Phase 5: Execution Engine (signal_engine.py & ghost_trader.py)
  execution:
    entry_z_score: 2.0                   # Standard entry. (Can dynamically adjust for fees later)
    exit_z_score: 0.0                    # Take-profit mean reversion
    stop_loss_z_score: 4.0               # Circuit breaker
    ew_ols_lookback_bars: 540            # Window for exponential OLS (e.g. 90 days for 4H)
```

**Why this matters:**
1. **Adaptive Filters:** By using `volume_lookback_bars` instead of a hardcoded "30 Days", the pipeline seamlessly scales. If you are on the 1m timeframe, you can set it to `1440` (1 day), and the volume liquidity filter mathematically checks the last day. If you are on 4H, you set it to `180` (30 days).
2. **Dynamic Trimming:** The clustering script no longer hardcodes `[:-5]` to drop Bitcoin and Ethereum. It reads `exclude_top_n_mega_caps` and dynamically slices the arrays.
3. **Hyperparameter Grids:** During Epoch 2 (Stress Testing), you can spawn `alpha_v2.yml`, `alpha_v3.yml` with different Z-Scores and Half-Lives to find the optimal combination, all without touching Python.

---

## 3. The Injection Mechanism

When you execute the master script:
`python -m scripts.run_turbo_workflow --pipeline configs/pipelines/turbo_1m.yml --strategy configs/strategies/alpha_v1.yml`

1. **Prefect Orchestrator** reads both files.
2. It passes the `pipeline.yml` to `mine_data.py` to dictate API fetching constraints.
3. It passes the `strategy.yml` to `discover_pairs.py`. The Taxonomy objects (`DataMaturityFilter`, `MatrixBuilder`, `LouvainTaxonomist`) are instantiated directly with these YAML variables (Dependency Injection).
4. The execution engine (`ghost_trader.py`) reads both files: the pipeline tells it to run in turbo mode with `max_ticks: null` (endlessly), and the strategy tells it to use an `entry_z_score` of 2.0.
