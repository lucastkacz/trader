# Strict Config, Boot Safety & Default Eradication Plan

## Purpose

This document is the next roadmap after:

```text
PLAN/6_ROAD_TO_PRODUCTION/14_trader_modularization_and_production_hardening.md
```

The trader modularization pass created clear homes for state, runtime, execution,
commands, signals, and reporting. The next production risk is not file size. It is
configuration ambiguity.

The platform is intended to be a single config-driven system across:

```text
dev
uat
prod
backtest
```

Therefore operational values must come from explicit YAML or typed secrets, not from
hidden Python defaults. If a required value is missing, the system should fail on
boot with a precise validation error. Silent defaults are dangerous because they can
make a real-capital environment inherit a development assumption without anyone
noticing.

This plan covers:

```text
strict typed config models
removal of config-origin default values
boot-time validation
read-only boot reconciliation
order lifecycle hardening before live execution
auditor scaffolding
```

It does **not** authorize new alpha logic, live exchange order submission, or
automatic reconciliation actions. Those remain future steps after the safety layer
is explicit and green.

---

## Non-Negotiable Rules

### 1. No Ghost Compatibility

The Ghost-to-Trader refactor is canonical. Do not restore:

```text
ghost names
ghost tables
ghost script entrypoints
ghost paths
```

Canonical names remain:

```text
trader
LiveTrader
TradeStateManager
TradeReport
spread_positions
src.engine.trader.*
```

### 2. No Config-Origin Defaults

If a value changes trading, research, exchange access, sizing, filtering, reporting
paths, execution cadence, or backtest realism, it must be explicitly supplied by
YAML or environment secret.

Forbidden patterns for config-origin values:

```python
cfg.get("key", default)
pipeline_cfg.get("min_volume", 20_000_000)
def __init__(self, max_leverage: float = 10.0)
def __init__(self, maker_fee: float = 0.0002)
```

Allowed patterns:

```python
optional_value: str | None
def helper(verbose: bool = False)  # genuinely optional behavior
row.get("field")                  # row/dict projection data, not config
```

### 3. Null Is Explicit, Missing Is Invalid

Optional config fields must still be present in YAML if they affect runtime shape.

Example:

```yaml
execution:
  max_ticks: null
```

This is acceptable because the operator explicitly chose "no loop limit." The code
should not silently invent `None` if `max_ticks` is missing.

### 4. Typed Config Is The Boundary

Raw YAML dictionaries should be parsed once into typed models near the application
entrypoint. Deeper modules should receive typed config objects or explicit primitive
arguments, not free-form dictionaries.

### 5. Behavior Preservation During Config Hardening

This work should initially preserve behavior by moving existing values into YAML and
typed models. It should not change thresholds, filters, fees, sizing limits, or
execution cadence unless a slice explicitly says so and tests are updated.

---

## Current Known Default/Hardcoded Value Debt

This list is not exhaustive. It is the first backlog from a quick scan and should be
expanded with `rg` before implementation.

### `src/pipeline/master_flow.py`

Current issue:

```python
min_volume=pipeline_cfg.get("min_volume", 20_000_000)
limit_symbols=pipeline_cfg.get("max_symbols")
```

Problem:

```text
20,000,000 is an operational universe liquidity filter hidden in orchestration code.
max_symbols silently becomes None if omitted.
```

Likely target:

```text
min_volume should come from universe.filters.min_volume_liquidity
max_symbols should be a required pipeline field or a required nullable field
```

The function signature may need to accept `universe_cfg` in `task_mine_data`, or a
typed research config object that already merges the relevant fields.

### `src/risk/position_sizer.py`

Current issue:

```python
def __init__(self, max_cluster_exposure: float = 0.10, max_leverage: float = 10.0)
```

Problem:

```text
max_cluster_exposure and max_leverage are real capital risk controls.
They must never be inherited from Python defaults.
```

Likely target:

```yaml
risk:
  max_cluster_exposure: 0.10
  max_leverage: 10.0
```

Open design choice:

```text
Either create configs/risk/alpha_v1.yml, or place risk under configs/strategy/alpha_v1.yml.
For production clarity, a separate configs/risk/ directory is preferable.
```

### `src/simulation/friction_model.py`

Current issue:

```python
def __init__(
    self,
    maker_fee: float = 0.0002,
    taker_fee: float = 0.0006,
    annual_fund_rate: float = 0.10,
)
```

Problem:

```text
Backtest realism depends on fees and funding assumptions.
These already exist in configs/backtest/stress_test.yml and should be required.
```

Likely target:

```python
FrictionEngine(
    maker_fee=backtest_cfg.friction.maker_fee,
    taker_fee=backtest_cfg.friction.taker_fee,
    annual_fund_rate=backtest_cfg.friction.annual_fund_rate,
)
```

### `src/engine/analysis/cointegration.py`

Current issue:

```python
def __init__(
    self,
    p_value_threshold: float = 0.05,
    max_half_life: float = 14.0,
    ewma_span: int = 48,
)
```

Problem:

```text
These are research/alpha acceptance criteria.
They should come from universe/strategy config.
```

Existing config:

```yaml
universe:
  cointegration:
    p_value_threshold: 0.05
    max_half_life_bars: 84

strategy:
  execution:
    ew_ols_lookback_bars: 540
```

Open design choice:

```text
Rename max_half_life -> max_half_life_bars in code for bars-first consistency.
Decide whether ewma_span belongs under universe.cointegration or strategy.execution.
```

### `src/screener/filters/data_maturity.py`

Current issue:

```python
def __init__(self, min_days: int = 180)
```

Problem:

```text
The platform has moved from days to bars.
This class still encodes a days-based default and name.
```

Likely target:

```python
DataMaturityFilter(min_bars=universe_cfg.filters.min_data_maturity_bars)
```

Also consider renaming the class internals from `min_days` to `min_bars`.

### `src/screener/clustering/graph_louvain.py`

Current issue:

```python
def __init__(self, correlation_threshold: float = 0.5)
```

Existing config:

```yaml
universe:
  clustering:
    louvain_correlation_threshold: 0.5
```

Target:

```python
LouvainTaxonomist(
    correlation_threshold=universe_cfg.clustering.louvain_correlation_threshold
)
```

### `src/screener/clustering/returns_matrix.py`

Current issue:

```python
def __init__(self, clip_percentile: float = 0.01)
```

Existing config:

```yaml
universe:
  clustering:
    returns_clip_percentile: 0.01
```

Target:

```python
MatrixBuilder(clip_percentile=universe_cfg.clustering.returns_clip_percentile)
```

### `src/interfaces/telegram/daemon.py`

Current issues from scan:

```python
cfg = data.get("telegram", data)
if not cfg.get("db_path"):
TELEGRAM_ENVIRONMENT = cfg.get("environment", "UNKNOWN")
p.get("holding_bars", 0) * 4
```

Problem:

```text
Telegram DB path and environment metadata are operational config.
The 4-hour holding duration assumption is timeframe-specific.
```

Likely target:

```text
Typed TelegramConfig with required db_path and environment.
Timeframe or bars-to-duration display policy should be explicit if shown in UI.
```

### `src/engine/trader/runtime/trader.py`

Current issue:

```python
max_ticks = execution_cfg.get("max_ticks", None)
```

Problem:

```text
max_ticks is an execution control. It may be nullable, but must be explicitly present.
```

Target:

```python
max_ticks = pipeline_cfg.execution.max_ticks
```

### `src/engine/trader/runtime/pairs.py`

Current issue:

```python
p.get("Performance", {}).get("sharpe_ratio", 0)
```

Problem:

```text
surviving_pairs.json rows are generated data, not YAML config, but silently treating
missing performance as Sharpe 0 can hide corrupted research output.
```

Target:

```text
Parse surviving pair rows into typed/generated-data models or strict dict access.
Missing Performance.sharpe_ratio should fail reportably.
```

### Reporting Defaults

Current issue:

```python
generate_report(..., surviving_pairs_path: str = "data/universes/surviving_pairs.json")
```

Problem:

```text
Report comparison paths should come from config or CLI, especially because current
universe outputs are timeframe-specific.
```

Target:

```text
Make surviving_pairs_path required for programmatic calls, or derive it from typed
timeframe/pipeline config in a single place.
```

---

## Values That Are Probably Acceptable Internal Constants

Do not blindly remove every literal. Some values are domain math constants or local
sentinel values.

Likely acceptable:

```text
0.0 for empty metrics
1.0 in ratios, inverse volatility, or percentages
2.0 in formulas such as two-legged transaction cost
365.0 and 24.0 when converting annual rates to hourly rates, if named clearly
SQLite PRAGMA busy_timeout=5000 if treated as a database implementation constant
test fixture literals
```

Still worth reviewing:

```text
CANDLE_BUFFER_SECONDS = 30
poll sleep min(10.0, ...)
report stale threshold of 48 hours
default 4H annualization fallback in reporting
```

These may be acceptable as internal policies, but if operators need to tune them per
environment, they belong in typed config.

---

## Target Config Shape

Recommended package:

```text
src/engine/trader/config/
  __init__.py
  models.py
  loader.py
  validation.py
```

This package can later move upward to `src/config/` if research/backtest/trader
config sharing becomes too broad. For now, keep it close to the trader production
hardening work.

Recommended model groups:

```text
PipelineConfig
PipelineExecutionConfig
UniverseConfig
UniverseFiltersConfig
UniverseClusteringConfig
UniverseCointegrationConfig
StrategyConfig
StrategyExecutionConfig
BacktestConfig
BacktestGridConfig
BacktestFrictionConfig
RiskConfig
TelegramConfig
```

Recommended loader functions:

```python
load_pipeline_config(path: str) -> PipelineConfig
load_universe_config(path: str) -> UniverseConfig
load_strategy_config(path: str) -> StrategyConfig
load_backtest_config(path: str) -> BacktestConfig
load_risk_config(path: str) -> RiskConfig
load_telegram_config(path: str) -> TelegramConfig
```

All loaders should:

```text
read YAML
require the expected top-level key
validate required fields
reject missing operational fields
return typed models
```

Do not use typed models as a place to hide defaults. Required fields should be
required. Optional fields should be explicitly nullable in YAML when they alter
runtime behavior.

---

## Proposed YAML Additions

### Pipeline

Current pipeline YAML has:

```yaml
pipeline:
  historical_days: 365
  max_symbols: 100
```

Need to decide whether ingestion volume belongs here or in universe. Recommended:

```yaml
pipeline:
  historical_days: 365
  max_symbols: 100
```

```yaml
universe:
  filters:
    min_volume_liquidity: 20000000
```

Then `task_mine_data` should receive both typed pipeline and typed universe config.

### Risk

Add:

```text
configs/risk/alpha_v1.yml
```

Example:

```yaml
risk:
  name: "Alpha V1 Risk Limits"
  max_cluster_exposure: 0.10
  max_leverage: 10.0
```

Then update `main.py` and orchestration to accept `--risk` for flows that need
position sizing or live execution risk limits.

### Telegram

Telegram config should explicitly include:

```yaml
telegram:
  environment: "dev"
  db_path: "data/dev/trades_1m.db"
```

Secrets remain in `.env`:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

---

## Implementation Phases

### Phase 1: Build Typed Config Models

Goal:

```text
Introduce typed config parsing without changing runtime behavior.
```

Tasks:

```text
create config models and loaders
add tests for required fields
add tests that missing operational fields fail loudly
add tests that explicit null is accepted only where intended
```

Initial tests:

```text
valid dev/uat/prod pipeline configs parse
valid universe/strategy/backtest/telegram configs parse
missing pipeline.execution.exchange fails
missing pipeline.execution.max_ticks fails
missing universe.filters.min_volume_liquidity fails
missing strategy.execution.volatility_lookback_bars fails
missing backtest.friction.taker_fee fails
```

Review gate:

```bash
PYTHONPATH=. .venv/bin/pytest tests -m "not live" --tb=short
.venv/bin/ruff check src tests
```

### Phase 2: Replace Config-Origin `.get()` In Orchestration

Goal:

```text
Remove silent fallback behavior from pipeline and runtime orchestration.
```

Tasks:

```text
update main.py to parse YAML into typed config models
update master_flow.py to consume typed config or strict dicts
remove pipeline_cfg.get("min_volume", 20_000_000)
remove pipeline_cfg.get("max_symbols")
remove execution_cfg.get("max_ticks", None)
route min_volume_liquidity from universe config into mining
```

Behavior:

```text
existing YAML values preserve current behavior
missing keys now fail on boot
```

### Phase 3: Risk Config And Position Sizer

Goal:

```text
Make real-capital risk limits explicit config, never Python defaults.
```

Tasks:

```text
create configs/risk/alpha_v1.yml
add RiskConfig model
remove defaults from VaultSizer.__init__
update call sites/tests to pass risk values explicitly
decide how risk config is passed to execute flow
```

Required code direction:

```python
class VaultSizer:
    def __init__(self, max_cluster_exposure: float, max_leverage: float):
        ...
```

### Phase 4: Backtest Friction Config

Goal:

```text
Make simulation fees/funding explicit in all backtest execution.
```

Tasks:

```text
remove defaults from FrictionEngine.__init__
ensure StressTestOrchestrator passes backtest_cfg.friction explicitly
add tests for missing friction fields
```

### Phase 5: Research/Universe Defaults

Goal:

```text
Move screener and analysis thresholds fully behind universe/strategy config.
```

Tasks:

```text
remove defaults from CointegrationEngine.__init__
rename max_half_life to max_half_life_bars where appropriate
decide ewma_span source and name
remove defaults from DataMaturityFilter
rename DataMaturityFilter min_days to min_bars
remove defaults from LouvainTaxonomist
remove defaults from MatrixBuilder
update DiscoveryEngine to pass typed config values explicitly
```

### Phase 6: Telegram Config Strictness

Goal:

```text
Telegram daemon should boot only with explicit, typed config.
```

Tasks:

```text
replace cfg.get("telegram", data) with typed loader behavior
require telegram.db_path
require telegram.environment
remove environment fallback UNKNOWN
remove hardcoded holding_bars * 4 display assumption or make timeframe explicit
```

### Phase 7: Report Path Strictness

Goal:

```text
Reporting should not infer comparison data paths silently.
```

Tasks:

```text
make surviving_pairs_path required in generate_report, or derive via typed config
update report_generator CLI to require comparison path or pipeline/timeframe config
update tests to pass explicit path
```

### Phase 8: Generated Data Validation

Goal:

```text
Generated artifacts should fail loudly when malformed.
```

Tasks:

```text
validate surviving_pairs.json row shape
replace p.get("Performance", {}).get("sharpe_ratio", 0)
add tests for malformed surviving pair rows
consider typed SurvivingPair model
```

### Phase 9: Boot Reconciliation In Read-Only Mode

Goal:

```text
Use the new reconciliation state tables for safe boot diagnostics.
```

Scope:

```text
read exchange/account snapshot if credentials permit
read local open positions
record reconciliation run
record deltas
send Telegram/report warning
do not open, close, cancel, or submit orders
```

Deltas to classify:

```text
LOCAL_ONLY_POSITION
EXCHANGE_ONLY_POSITION
QTY_MISMATCH
SIDE_MISMATCH
SYMBOL_MISMATCH
MATCHED
```

Review gate:

```text
unit tests mocked, no network calls
integration path disabled unless explicit live marker/config
```

### Phase 10: Order Lifecycle State Expansion

Goal:

```text
Prepare state for real order execution without submitting real orders yet.
```

Add or support statuses:

```text
TARGET_RECORDED
SUBMIT_REQUESTED
ACKNOWLEDGED
PARTIALLY_FILLED
FILLED
CANCEL_REQUESTED
CANCELLED
FAILED
REJECTED
```

Tasks:

```text
explicit state transition helpers
leg fill update paths
idempotency rules
tests for invalid transitions
reporting updates for new statuses
```

### Phase 11: Auditor Skeleton

Goal:

```text
Add auditor behavior in read-only/reporting mode before automatic action.
```

Scope:

```text
scheduled or manually callable auditor
records reconciliation runs
surfaces unresolved deltas
never submits orders
never mutates positions except reconciliation tables
```

### Phase 12: Future Live Order Execution

Only after prior phases:

```text
strict config is complete
boot reconciliation is read-only and green
order lifecycle states are explicit
auditor skeleton reports accurately
all offline tests are green
live tests are isolated behind markers
```

Then consider:

```text
exchange precision
submit order requests
ack/fill polling
partial fill handling
cancel/retry policy
emergency liquidation against actual exchange state
```

---

## Suggested Slice Order

Recommended next coding sequence:

```text
1. Add typed config models/loaders and tests.
2. Update main.py/master_flow.py to use typed config for pipeline/universe/strategy/backtest.
3. Remove master_flow.py min_volume/max_symbols fallbacks.
4. Add RiskConfig and remove VaultSizer defaults.
5. Remove FrictionEngine defaults and wire backtest friction config explicitly.
6. Remove screener/analysis defaults and pass universe/strategy values explicitly.
7. Harden TelegramConfig and daemon boot.
8. Make report comparison path explicit.
9. Validate surviving_pairs generated artifact shape.
10. Add read-only boot reconciliation service.
11. Expand order lifecycle statuses.
12. Add auditor skeleton.
```

Each slice should end with:

```bash
PYTHONPATH=. .venv/bin/pytest tests -m "not live" --tb=short
.venv/bin/ruff check src tests
```

---

## Review Gates

Every slice must answer:

```text
Moved code only: yes/no
Behavior changed: yes/no
Schema changed: yes/no
Config keys added/removed: list
Defaults removed: list
Tests added/updated: list
```

Every slice must keep:

```text
offline tests green
ruff green
no new ghost names
no live network calls in unit tests
no config-origin .get("key", default)
no hidden default values for operational controls
```

---

## Definition Of Done

This hardening track is complete when:

```text
all YAML files parse into typed config models
missing operational YAML fields fail before work starts
all risk limits are explicit config values
all backtest friction assumptions are explicit config values
all research thresholds are explicit config values
telegram daemon has typed required config
report comparison paths are explicit
generated surviving pair rows are validated
boot reconciliation records read-only diagnostics
order lifecycle states are ready for live execution work
offline tests and ruff are green
```

