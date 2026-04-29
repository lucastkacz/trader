# Codebase Sanity, Config Consistency & File Size Audit

## Purpose

After strict config, reconciliation, lifecycle, auditor, and guarded execution work,
pause before more features. The engine is drifting toward large files and subtle
config naming/unit risk.

Main concerns:

```text
large modules becoming hard to review
config key/unit inconsistencies
runtime behavior hidden across too many paths
live execution safety depending on naming precision
```

Known example:

```text
holding_period_bar_hours -> holding_period_bar_minutes
```

We need a deliberate cleanup and sanity pass.

## Non-Negotiables

```text
no live network calls in unit tests
no exchange mutation while auditing
no ghost names/paths/tables
no config-origin defaults
no broad rewrites without tests
do not change trading behavior during file splits
```

## Phase 1: File Size Inventory

Run:

```bash
find src tests -name "*.py" -print0 | xargs -0 wc -l | sort -nr | head -50
```

Flag files:

```text
>300 lines: review
>500 lines: split unless clearly justified
```

Initial suspects:

```text
src/engine/trader/state/manager.py
src/engine/trader/runtime/trader.py
src/engine/trader/runtime/tick.py
src/engine/trader/execution/orders.py
src/engine/trader/reconciliation/service.py
src/engine/trader/state/services.py
```

## Phase 2: Config Key And Unit Audit

Search for suspicious unit/name drift:

```bash
rg "hours|hour|minutes|minute|bars|bar|period|interval|lookback|timeout|ttl|poll|heartbeat" configs src tests
```

Check every config model against YAML:

```text
configs/pipelines/*.yml
configs/telegram/*.yml
configs/risk/*.yml
configs/strategy/*.yml
configs/universe/*.yml
configs/backtest/*.yml
```

Required output:

```text
field name
unit
YAML path
model path
all call sites
test coverage
```

## Phase 3: Config Contract Tests

Add tests that prove:

```text
all YAML files parse
old renamed keys fail loudly
extra keys fail loudly
missing operational keys fail loudly
unit-bearing fields have unit suffixes
```

Explicit regression tests:

```text
holding_period_bar_hours rejected
holding_period_bar_minutes required
heartbeat_seconds required
fill_poll_interval_seconds required
historical_days required
lookback_bars remains bars, not minutes
```

## Phase 4: Split Large Files Safely

Only split when behavior can remain identical and the split reduces real review
risk. File size alone is not sufficient justification. Avoid modularity theater:
a larger cohesive module is better than small files that scatter a still-unclear
runtime policy.

Suggested homes:

```text
state/manager.py -> facade only
state/order_lifecycle_service.py -> leg transition coordination
runtime/trader.py -> boot.py, loop.py, trader.py facade
runtime/tick.py -> market_eval.py, signal_routing.py
execution/orders.py -> adapter.py, executor.py, models.py
reconciliation/service.py -> models.py, classifier.py, audit.py
```

Review rule:

```text
Moved code only: yes
Behavior changed: no
Schema changed: no
Config changed: no
```

Before any split, complete the runtime safety and live-execution gating review
below. The goal of this phase is not to force smaller files; it is to make sure
the engine has no hidden production assumptions.

## Phase 5: Runtime Safety Audit

Trace these flows end to end:

```text
boot
reconciliation
tick
entry
exit
flip
pause/resume
stop/stop_all
report generation
order_execution.mode state_only
order_execution.mode live
```

For each flow record:

```text
state writes
exchange reads
exchange writes
Telegram writes
failure handling
tests
```

## Phase 6: Verification

Always run:

```bash
PYTHONPATH=. .venv/bin/pytest tests -m "not live" --tb=short
.venv/bin/ruff check src tests main.py
```

Optional audit commands:

```bash
rg "get\\(.*," src/engine src/pipeline src/risk src/simulation
rg "holding_period_bar_hours|bar_hours|hours" configs src tests
rg "ghost" src tests configs
```

## Definition Of Done

```text
large-file inventory documented
config key/unit audit complete
renamed-key regressions tested
large modules split where useful
no behavior change from code moves
offline tests green
ruff green
Phase 12 remains gated and safe
```

## Phase 1 Findings: File Size Inventory

Command run:

```bash
find src tests -name "*.py" -print0 | xargs -0 wc -l | sort -nr | head -50
```

Flagged files:

```text
734 tests/engine/trader/state/test_manager.py
418 src/engine/trader/state/manager.py
361 src/engine/trader/execution/orders.py
358 tests/engine/trader/reporting/test_assembler.py
307 src/engine/trader/state/services.py
305 src/engine/trader/reconciliation/service.py
301 src/engine/trader/runtime/trader.py
```

Review notes:

```text
tests/engine/trader/state/test_manager.py
  >500 lines. Large but currently mirrors the state facade contract. Split later by
  lifecycle area only if production state modules are split first.

src/engine/trader/state/manager.py
  >300 lines. Already functions mostly as a compatibility facade over repositories
  and StateOperationService. Do not split first unless a facade-only cleanup is
  paired with unchanged import compatibility.

src/engine/trader/execution/orders.py
  >300 lines. Strongest first split candidate. It mixes request/result models,
  adapter protocol, CCXT live adapter, execution orchestration, exchange status
  normalization, and outcome helpers. Low-risk split target if orders.py remains
  an import-compatible facade.

tests/engine/trader/reporting/test_assembler.py
  >300 lines. Reporting tests are broad but not blocking production readability.
  Review after production splits, not before.

src/engine/trader/state/services.py
  >300 lines. Mostly one StateOperationService plus leg transition helpers. Could
  split leg lifecycle coordination later, but this is lower priority than orders.py.

src/engine/trader/reconciliation/service.py
  >300 lines. Contains models, classifier helpers, boot reconciliation, and
  read-only audit. Good second split candidate after orders.py.

src/engine/trader/runtime/trader.py
  >300 lines by one line. Runtime orchestration is readable but combines boot,
  reconciliation notification, loop scheduling, command polling, and tick routing.
  Defer until config contract tests and the execution split are stable.
```

Superseded initial split order recommendation:

```text
1. src/engine/trader/execution/orders.py
2. src/engine/trader/reconciliation/service.py
3. src/engine/trader/runtime/trader.py
4. src/engine/trader/state/services.py
5. src/engine/trader/state/manager.py
```

Status:

```text
Do not execute this split order yet. After reviewing the prior production plans,
the stronger conclusion is that live-execution gating, symbol semantics, scheduler
fail-fast behavior, and signal-data hardening are higher priority than splitting
files by line count.
```

## Revised Direction: Slop Audit Before Modularization

Additional context reviewed:

```text
PLAN/6_ROAD_TO_PRODUCTION/13_CONTEXT_HANDOFF_AND_STATE_ARCHITECTURE.md
PLAN/6_ROAD_TO_PRODUCTION/14_trader_modularization_and_production_hardening.md
PLAN/6_ROAD_TO_PRODUCTION/15_strict_config_boot_safety_and_default_eradication.md
```

Key conclusion:

```text
Phase 15 does not authorize production live exchange mutation. It explicitly
places real live order execution behind a future Phase 12 gate, after strict
config, read-only boot reconciliation, explicit order lifecycle, auditor
scaffolding, and green offline tests.
```

Current shipped config state:

```text
configs/pipelines/dev.yml   order_execution.mode: state_only
configs/pipelines/uat.yml   order_execution.mode: state_only
configs/pipelines/prod.yml  order_execution.mode: state_only
```

Therefore `src/engine/trader/execution/orders.py` should be treated as
provisional guarded execution infrastructure, not production-authorized live
trading behavior.

## Revised Change Plan

### 1. Preserve Phase 12 Gate With Tests

Goal:

```text
Prove all shipped pipeline YAMLs remain state_only and that live order execution
cannot be enabled accidentally by a missing or implicit config value.
```

Likely tests:

```text
tests/engine/trader/config/test_loader.py
  - every configs/pipelines/*.yml parses
  - every shipped pipeline has explicit order_execution.mode
  - every shipped pipeline currently uses state_only
  - missing order_execution.mode fails loudly
  - unsupported order_execution.mode fails loudly
```

No source behavior change should be needed unless tests reveal a gap.

### 2. Clarify CCXT Symbol Semantics Before Touching Orders

Observed issue:

```text
fetch_universe() currently filters CCXT symbols ending in :USDT and strips the
settlement suffix to store BTC/USDT-style symbols.

fetch_klines() and execution/orders.py later re-add :USDT to build
BTC/USDT:USDT derivative symbols.
```

Interpretation:

```text
BTC/USDT:USDT is CCXT's unified derivative symbol format:
base/quote:settlement. It is not an accidental duplicated USDT.
```

Problem:

```text
The trader/execution layer should not guess derivative settlement suffixes.
Symbol resolution belongs in the data/exchange adapter layer using
exchange.load_markets() metadata where possible.
```

Desired future shape:

```text
display_symbol: BTC/USDT
ccxt_symbol: BTC/USDT:USDT
market_type: swap
settle: USDT
```

Near-term action:

```text
Do not refactor symbol handling inside orders.py yet. First document the contract
and add tests around the current conversion helper if it remains. Then plan a
central exchange symbol resolver in src/data/fetcher/ before live execution is
enabled.
```

### 3. Make Scheduler Fail Fast

Current risk:

```text
src/engine/trader/runtime/scheduler.py returns 60.0 for unsupported timeframes.
That is a hidden operational default.
```

Target:

```text
unsupported or malformed timeframes raise ValueError
timeframe parsing uses centralized timeframe utilities where practical
1m and 4h behavior remains unchanged
```

Tests first:

```text
tests/engine/trader/runtime/test_scheduler.py
  - 1m returns a positive wait plus buffer
  - 4h returns a positive wait plus buffer
  - invalid timeframe raises ValueError
  - unsupported timeframe does not silently fall back to 60 seconds
```

### 4. Harden Signal Evaluation Against Bad Data

Current risk:

```text
Flat prices, NaN gaps, zero rolling standard deviation, or non-finite z-scores
can produce ambiguous signal results and polluted tick_signal rows.
```

Target:

```text
bad or non-finite current signal math returns FLAT with finite numeric fields
no trade entry/exit is triggered by NaN math
flat lines do not emit NaN z_score
weights remain finite and sum to one when possible
```

Tests first:

```text
tests/engine/trader/signals/test_evaluator.py
  - flat lines return FLAT with z_score 0.0
  - NaN close gaps do not produce non-finite SignalResult fields
  - zero volatility falls back to 0.5 / 0.5 weights
```

### 5. Review `/stop` And `/stop_all` Semantics

Current risk:

```text
execute_emergency_liquidation() closes local positions at fetched prices.
It does not submit close orders to the exchange.
```

This is acceptable in `order_execution.mode: state_only`. It is dangerous if
operators read `/stop` as real exchange liquidation in live mode.

Required decision before live mode:

```text
Option A: keep /stop and /stop_all local-state-only and explicitly block them
when order_execution.mode is live.

Option B: route them through real close-leg order execution after Phase 12 is
authorized and tested.
```

Near-term action:

```text
Document current behavior in tests and ensure shipped configs remain state_only.
Do not implement real exchange liquidation in this audit.
```

### 6. Review Live Order State Semantics

Current risk:

```text
runtime/tick.py records local open/close state before live leg execution completes.
If live execution fails or partially fills, local spread state may not represent
exchange reality.
```

This should be resolved by the future order lifecycle expansion:

```text
PENDING_OPEN
OPEN
PENDING_CLOSE
CLOSED
FAILED_OPEN
FAILED_CLOSE
ORPHANED_LEG
```

Near-term action:

```text
Do not broaden live behavior. Keep state_only as the shipped mode and add tests
that live mode remains explicit and gated.
```

### 7. Only Then Reconsider File Splits

After the above safety checks are green, revisit file size:

```text
split only if it clarifies an already-settled responsibility
preserve import-compatible trader facades
do not split provisional live execution code before its policy is clear
```

## Implementation Log

### Completed Slice 1: Config Gate And Runtime Math Safety

Files changed:

```text
tests/engine/trader/config/test_loader.py
tests/engine/trader/runtime/test_scheduler.py
src/engine/trader/runtime/scheduler.py
tests/engine/trader/signals/test_evaluator.py
src/engine/trader/signals/evaluator.py
```

Behavior changes:

```text
all shipped pipeline configs are now tested to remain order_execution.mode=state_only
unsupported order_execution.mode values fail typed config validation
scheduler no longer falls back to 60 seconds for malformed/unsupported timeframes
scheduler uses centralized timeframe parsing and UTC candle boundaries
signal evaluator drops invalid close rows before signal math
flat/invalid current signal math returns a finite FLAT SignalResult
```

Verification:

```bash
PYTHONPATH=. .venv/bin/pytest tests -m "not live" --tb=short
.venv/bin/ruff check src tests main.py
```

Result:

```text
137 passed, 3 deselected
ruff green
```

### Completed Slice 2: Stop Semantics And Symbol Contract

Files changed:

```text
tests/engine/trader/commands/test_processor.py
src/engine/trader/execution/liquidation.py
tests/engine/trader/execution/test_orders.py
```

Behavior changes:

```text
/stop and /stop_all local liquidation now records close_reason=FORCE_CLOSE_REQUESTED
Telegram messages now say LOCAL STATE EMERGENCY LIQUIDATION/EXIT
local emergency liquidation remains exchange-non-mutating
close leg targets remain TARGET_RECORDED until a future authorized execution layer acts
current CCXT derivative symbol helper is pinned by tests:
  BTC/USDT -> BTC/USDT:USDT
  BTC/USDT:USDT -> BTC/USDT:USDT
```

Notes:

```text
BTC/USDT:USDT is CCXT's unified derivative symbol format
base/quote:settlement. The current helper remains provisional; future work should
move symbol resolution to the data/exchange adapter layer using market metadata.
```

### Completed Slice 3: Central Symbol Normalization Contract

Files changed:

```text
src/data/fetcher/symbols.py
src/data/fetcher/exchange_client.py
src/engine/trader/execution/orders.py
tests/data/test_symbols.py
tests/data/test_exchange_client.py
tests/engine/trader/execution/test_orders.py
```

Symbol audit results:

```text
src/data/fetcher/exchange_client.py
  fetch_universe() receives CCXT symbols such as BTC/USDT:USDT and returns
  display/strategy symbols such as BTC/USDT.

src/data/fetcher/exchange_client.py
  fetch_klines() accepts display/strategy symbols and resolves them to CCXT
  linear swap symbols before calling fetch_ohlcv().

src/engine/trader/execution/orders.py
  order execution still accepts display/strategy symbols from leg_fills, but now
  delegates derivative symbol formatting to the data-layer symbol helper.

src/engine/trader/runtime/tick.py
  pair labels remain display/strategy symbols joined with "|".

src/engine/trader/reconciliation/service.py
  exchange snapshots currently compare against display/strategy symbols. Future
  exchange snapshot providers must normalize exchange symbols to display symbols
  before classification, or reconciliation will produce false mismatches.
```

Current canonical contract:

```text
display/strategy symbol: BTC/USDT
CCXT linear swap symbol: BTC/USDT:USDT
pair label: BTC/USDT|ETH/USDT
```

Implementation:

```text
to_display_symbol("BTC/USDT:USDT") -> "BTC/USDT"
to_display_symbol("BTC/USDT") -> "BTC/USDT"
to_ccxt_linear_swap_symbol("BTC/USDT") -> "BTC/USDT:USDT"
to_ccxt_linear_swap_symbol("BTC/USDT:USDT") -> "BTC/USDT:USDT"
```

Remaining design debt:

```text
The helper preserves the current USDT linear swap convention. It does not yet use
exchange.load_markets() metadata. Before enabling live order execution, replace
or wrap this helper with market metadata resolution so the code does not infer
settlement symbols in strategy/runtime modules.
```

### Completed Slice 4: Dev Run Readiness

Files changed:

```text
tests/engine/trader/config/test_loader.py
src/interfaces/telegram/daemon.py
tests/interfaces/telegram/test_daemon.py
```

Purpose:

```text
Keep the pipeline config surface limited to dev/uat/prod and make Telegram
command wording match state_only behavior.
```

Pipeline config policy:

```text
configs/pipelines/dev.yml
configs/pipelines/uat.yml
configs/pipelines/prod.yml
```

Dev workflow setup:

```text
Required before execute:
  data/universes/1m/surviving_pairs.json must exist
  data/parquet/... must contain the required 1m OHLCV cache

Optional for research/dev fetch:
  exchange_readonly_api_key
  exchange_readonly_api_secret

Optional for Telegram:
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
```

Recommended first commands:

```bash
python main.py research \
  --pipeline configs/pipelines/dev.yml \
  --universe configs/universe/alpha_v1.yml \
  --backtest configs/backtest/stress_test.yml \
  --strategy configs/strategy/alpha_v1.yml

python main.py execute \
  --pipeline configs/pipelines/dev.yml \
  --strategy configs/strategy/alpha_v1.yml \
  --risk configs/risk/alpha_v1.yml
```

Optional Telegram command daemon:

```bash
python main.py execute \
  --pipeline configs/pipelines/dev.yml \
  --strategy configs/strategy/alpha_v1.yml \
  --risk configs/risk/alpha_v1.yml \
  --telegram configs/telegram/dev.yml
```

Behavior:

```text
state_only means no exchange order submission
/stop and /stop_all are now described as forced local-state closes
configs/pipelines/dev.yml is the sandbox config and may be edited freely during
development
```

### Completed Slice 5: Pair Artifact Metadata And Recalculation Policy

Files changed:

```text
src/engine/trader/runtime/pairs.py
src/engine/trader/runtime/trader.py
src/screener/discovery_engine.py
src/simulation/stress_orchestrator.py
src/engine/trader/reporting/backtest_lookup.py
tests/engine/trader/runtime/test_pairs.py
```

Artifact contract:

```json
{
  "metadata": {
    "schema_version": 1,
    "artifact_type": "surviving_pairs",
    "generated_at": "...",
    "timeframe": "1m",
    "exchange": "bybit",
    "pair_count": 12
  },
  "pairs": []
}
```

Runtime validation:

```text
execute fails loudly if data/universes/{timeframe}/surviving_pairs.json is missing
execute rejects legacy list-only surviving_pairs.json artifacts
execute rejects artifact timeframe mismatch
execute rejects artifact exchange mismatch
execute rejects pair_count mismatch
execute still validates every pair row shape before trading
```

Current pair lifecycle:

```text
research recalculates clusters and surviving pairs when the operator runs research
execute loads the surviving pair artifact once on boot
execute trades only that loaded set until process restart
```

Recalculation policy decision:

```text
Pair recalculation is not rebalancing.

Future pair recalculation should update the allowed set for new entries only.
If an existing open position belongs to a pair that falls out of the recalculated
set, the default policy should be to stop opening new entries for that pair and
let the existing position close naturally under its normal signal/exit logic.
Forced close should remain a separate explicit operator/auditor/risk action.
```

Missing future config:

```yaml
execution:
  pair_refresh:
    mode: "manual"
    max_artifact_age_bars: 1440
    reload_on_boot_only: true
    stale_open_position_policy: "natural_exit"
```

Do not implement automatic pair reload yet. First add artifact age validation and
operator-visible warnings once the desired cadence is decided.
