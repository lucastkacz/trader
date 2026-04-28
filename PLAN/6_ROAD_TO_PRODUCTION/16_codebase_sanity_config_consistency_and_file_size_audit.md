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

Only split when behavior can remain identical.

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

