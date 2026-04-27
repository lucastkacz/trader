# Trader Modularization & Production Hardening Plan

## Purpose

This document is the next roadmap after:

```text
PLAN/6_ROAD_TO_PRODUCTION/12_ghost_to_trader_refactoring.md
PLAN/6_ROAD_TO_PRODUCTION/13_CONTEXT_HANDOFF_AND_STATE_ARCHITECTURE.md
```

The Ghost-to-Trader refactor is now canonical, the immediate state-architecture checklist is complete, and the trader stack is green. The next risk is maintainability.

The current `src/engine/trader/` directory has become too dense:

```text
src/engine/trader/live_trader.py        ~420 lines
src/engine/trader/state_manager.py      ~677 lines
src/engine/trader/report_engine.py      ~745 lines
src/engine/trader/report_generator.py   ~414 lines
src/engine/trader/signal_engine.py      ~136 lines
```

This violates the spirit of the coding manifesto: the platform should be readable, testable, and operationally safe before it handles real capital. Adding order execution, boot reconciliation, stricter config parsing, and auditor behavior into these large files would create a brittle system that is difficult for both humans and AI agents to reason about.

The goal is to break the trader package into professional, small, purpose-owned modules without changing trading behavior in one large risky jump.

---

## Guiding Principles

### 1. Behavior Preservation First

This migration is primarily structural. Each slice should keep behavior unchanged unless the slice explicitly says otherwise.

Allowed:

```text
move code
rename modules
extract dataclasses
extract pure helper functions
add tests around existing behavior
add thin wrappers during a transition
```

Not allowed inside pure modularization slices:

```text
new alpha behavior
new exchange order behavior
new entry/exit logic
silent schema compatibility for legacy ghost tables
large untested rewrites
```

### 2. Public Facades Are Acceptable, Legacy Concepts Are Not

Short-term import facades are acceptable if they preserve the current canonical trader names:

```python
from src.engine.trader.state_manager import TradeStateManager
from src.engine.trader.live_trader import LiveTrader
```

But do not preserve old `ghost` names, old script entrypoints, or old database tables.

### 3. Separate Pure Math, State, I/O, Orchestration, and Presentation

The trader package should make it obvious which modules:

```text
compute pure values
mutate SQLite
talk to the exchange data layer
orchestrate the event loop
format reports
render CLI output
process user commands
reconcile local state against exchange state
```

No file should become a "god module" again.

### 4. Tests Move With Boundaries

As files split, tests should mirror the new package structure. For example:

```text
src/engine/trader/state/commands.py
tests/engine/trader/state/test_commands.py
```

Do not leave all trader behavior covered only through high-level integration tests.

### 5. Production-Hardening Must Be Planned Into The Shape

The package shape must leave clean homes for the broader remaining work from the previous handoff:

```text
strict typed config
more realistic backtest execution
exchange-agnostic market filtering
fuller order lifecycle states
boot reconciliation
real auditor behavior
future live order execution and fill tracking
```

If the new package tree has no obvious place for these, the plan is incomplete.

---

## Current Responsibility Map

### `live_trader.py`

Currently owns too many responsibilities:

```text
load surviving pairs
compute candle scheduling
fetch recent candles
calculate unrealized PnL
calculate per-pair PnL
determine action from current side and new signal
execute emergency liquidation
process user commands
execute one full tick
run the infinite loop
resolve credentials from settings
instantiate notifier and state manager
send Telegram messages
```

This should become a thin orchestrator around smaller services.

### `state_manager.py`

Currently owns:

```text
SQLite connection setup
PRAGMAs
schema creation
future migration hook
spread position lifecycle
order event writes
leg target writes
equity snapshots
tick signal writes
runtime state
user commands
reconciliation runs
reconciliation deltas
JSON serialization
time calculations
```

This should become a package with domain-specific repositories/services around a shared SQLite connection.

### `report_engine.py`

Currently owns:

```text
report dataclasses
annualization detection
return calculations
risk calculations
per-pair calculations
signal quality
state ledger summaries
backtest lookup loading
top-level report assembly
```

This should split into report models, metrics, state-ledger summaries, and assembly.

### `report_generator.py`

Currently owns:

```text
terminal color constants
terminal rendering
JSON export
Markdown export
CLI arg parsing
state manager construction
report generation
```

This should split presentation renderers from command-line entrypoint/export concerns.

### `signal_engine.py`

This file is still modest, but it should be placed in a more explicit signal package as the live/backtest math grows.

---

## Target Package Shape

Recommended target:

```text
src/engine/trader/
  __init__.py

  live_trader.py                  # thin compatibility facade for LiveTrader
  state_manager.py                # thin compatibility facade for TradeStateManager
  report_engine.py                # thin compatibility facade for generate_report / TradeReport
  report_generator.py             # CLI entrypoint only

  config/
    __init__.py
    models.py                     # typed pipeline/strategy/telegram config models
    loader.py                     # YAML -> typed models

  runtime/
    __init__.py
    trader.py                     # LiveTrader orchestration class
    scheduler.py                  # candle boundary and heartbeat timing
    credentials.py                # credential tier resolution
    pairs.py                      # surviving pair loading/filtering
    tick.py                       # single tick orchestration
    actions.py                    # ENTRY / EXIT / HOLD / FLIP / SKIP decisions

  execution/
    __init__.py
    market_data.py                # recent candle fetch adapter
    liquidation.py                # emergency liquidation workflow
    pnl.py                        # realized/unrealized/per-pair PnL helpers
    orders.py                     # future live order submit/ack/fill logic
    precision.py                  # future ccxt amount/price precision rules

  signals/
    __init__.py
    models.py                     # SignalResult and signal enums/constants
    evaluator.py                  # evaluate_signal()
    spread.py                     # re-export/bridge to analysis spread math if useful

  state/
    __init__.py
    manager.py                    # TradeStateManager facade over repositories
    connection.py                 # sqlite connect, PRAGMAs, row_factory
    schema.py                     # CREATE TABLE statements
    migrations.py                 # explicit current-schema migrations
    serialization.py              # JSON helpers
    positions.py                  # spread_positions projection repository
    events.py                     # order_events append-only ledger
    legs.py                       # leg_fills repository
    equity.py                     # equity_snapshots repository
    signals.py                    # tick_signals repository
    commands.py                   # user_commands lifecycle
    runtime.py                    # runtime_state repository
    reconciliation.py             # reconciliation_runs/deltas repository
    models.py                     # typed row/data models if introduced

  commands/
    __init__.py
    processor.py                  # trader-side command execution
    handlers.py                   # pause/resume/stop routing

  reconciliation/
    __init__.py
    auditor.py                    # future boot and periodic reconciliation
    models.py                     # exchange/local snapshot/delta models
    policy.py                     # delta classification/action policy

  reporting/
    __init__.py
    models.py                     # TradeReport, PairMetrics, RiskSnapshot, etc.
    metrics.py                    # sharpe/sortino/drawdown/trade stats
    per_pair.py                   # per-pair breakdown
    signal_quality.py             # signal quality calculations
    risk.py                       # risk snapshot calculations
    state_ledger.py               # order/leg/command/reconciliation counts
    assembler.py                  # generate_report()
    backtest_lookup.py            # surviving_pairs loading
    render_terminal.py            # terminal text rendering
    render_markdown.py            # markdown export body
    export.py                     # JSON/Markdown file writes
```

This tree is intentionally a little larger than the current code needs. The point is to prevent the next production features from being crammed back into four giant files.

---

## Desired Final File Size Targets

These are guidelines, not hard laws:

```text
0-150 lines: ideal for pure helpers, models, small repositories
150-250 lines: acceptable for focused services
250-350 lines: warning zone; split if responsibilities differ
350+ lines: must justify why it cannot be split
```

Expected after refactor:

```text
state/schema.py                    150-250 lines
state/manager.py                   80-160 lines
state/positions.py                 120-180 lines
runtime/trader.py                  120-220 lines
runtime/tick.py                    120-220 lines
reporting/metrics.py               120-220 lines
reporting/assembler.py             100-180 lines
reporting/render_terminal.py       150-250 lines
reporting/render_markdown.py       120-220 lines
```

---

## Migration Strategy

Do this in small, green, reviewable slices. Every slice should end with:

```bash
PYTHONPATH=. .venv/bin/pytest tests -m "not live" --tb=short
.venv/bin/ruff check src tests
```

### Phase 0: Freeze Current Behavior

Before moving code, add or confirm tests around:

```text
state schema table names
open/close position lifecycle
order_events lifecycle
leg_fills target rows
runtime pause state
user command lifecycle
reconciliation row helpers
report generation
report terminal rendering
signal/backtest spread parity
Telegram daemon DB wiring
trader command processing
```

Most of this coverage already exists. Add focused tests only where a move would otherwise be blind.

### Phase 1: Extract State Package Internals

Goal: break `state_manager.py` without changing imports used by the rest of the app.

New files:

```text
state/connection.py
state/schema.py
state/serialization.py
state/positions.py
state/events.py
state/legs.py
state/equity.py
state/signals.py
state/commands.py
state/runtime.py
state/reconciliation.py
state/manager.py
```

Keep:

```text
src/engine/trader/state_manager.py
```

as:

```python
from src.engine.trader.state.manager import TradeStateManager
```

Recommended internal shape:

```python
class TradeStateManager:
    def __init__(self, db_path: str):
        self.conn = connect_sqlite(db_path)
        create_schema(self.conn)
        migrate_schema(self.conn)
        self.positions = PositionRepository(self.conn)
        self.events = EventRepository(self.conn)
        ...
```

Then keep method proxies for current callers:

```python
def get_open_positions(self):
    return self.positions.get_open()
```

This keeps the first refactor low-risk while allowing later callers to use focused repositories directly.

State split ownership:

```text
connection.py       sqlite3 connect, row_factory, PRAGMAs
schema.py           CREATE TABLE statements only
migrations.py       current-schema migration hooks only
serialization.py    JSON dumping/loading helpers
positions.py        open/close/get spread_positions
events.py           append/read order_events
legs.py             target/fill leg_fills
equity.py           equity_snapshots
signals.py          tick_signals
commands.py         user_commands lifecycle
runtime.py          runtime_state
reconciliation.py   reconciliation_runs/deltas
manager.py          compatibility facade and transaction coordination
```

Important rule: repositories should not call each other randomly. Multi-table transitions belong in `manager.py` or a service that explicitly coordinates a transaction.

### Phase 2: Extract Signal Package

Move:

```text
signal_engine.py -> signals/evaluator.py
SignalResult -> signals/models.py
```

Keep:

```text
signal_engine.py
```

as a compatibility facade:

```python
from src.engine.trader.signals.evaluator import evaluate_signal
from src.engine.trader.signals.models import SignalResult
```

Do not duplicate spread math here. The canonical spread helper lives in:

```text
src/engine/analysis/spread_math.py
```

or a similarly shared analysis module. Trader signal code should import it.

### Phase 3: Extract Runtime / Tick Orchestration

Break `live_trader.py` into:

```text
runtime/trader.py
runtime/scheduler.py
runtime/credentials.py
runtime/pairs.py
runtime/actions.py
runtime/tick.py
execution/market_data.py
execution/pnl.py
execution/liquidation.py
commands/processor.py
```

Suggested ownership:

```text
runtime/trader.py
  - LiveTrader class
  - run loop
  - owns high-level orchestration only

runtime/scheduler.py
  - seconds_until_next_candle()
  - heartbeat/boundary calculations

runtime/credentials.py
  - credential tier -> api key/secret

runtime/pairs.py
  - load surviving pairs
  - Tier 1 filtering

runtime/actions.py
  - determine_action()
  - action enum/string constants

runtime/tick.py
  - execute one tick
  - process each pair
  - call signal evaluator
  - record tick signal
  - route entry/exit/flip
  - snapshot equity

execution/market_data.py
  - fetch_recent_candles()
  - data-layer adapter only

execution/pnl.py
  - calculate_unrealized_pnl()
  - calculate_per_pair_pnl()

execution/liquidation.py
  - emergency liquidation workflow

commands/processor.py
  - claim pending commands
  - execute pause/resume/stop/stop_all
  - mark executed/failed/ignored
```

Keep:

```text
live_trader.py
```

as:

```python
from src.engine.trader.runtime.trader import LiveTrader
```

### Phase 4: Extract Reporting Package

Break `report_engine.py` into:

```text
reporting/models.py
reporting/metrics.py
reporting/per_pair.py
reporting/signal_quality.py
reporting/risk.py
reporting/state_ledger.py
reporting/backtest_lookup.py
reporting/assembler.py
```

Break `report_generator.py` into:

```text
reporting/render_terminal.py
reporting/render_markdown.py
reporting/export.py
report_generator.py
```

Keep:

```text
report_engine.py
```

as:

```python
from src.engine.trader.reporting.assembler import generate_report
from src.engine.trader.reporting.models import TradeReport
```

Keep:

```text
report_generator.py
```

as the CLI entrypoint and argument parser only. It should import render/export functions.

### Phase 5: Update Tests To Mirror New Packages

After the compatibility facades are stable, move tests gradually:

```text
tests/engine/test_state_manager.py
  -> tests/engine/trader/state/test_manager.py
  -> tests/engine/trader/state/test_positions.py
  -> tests/engine/trader/state/test_commands.py
  -> tests/engine/trader/state/test_reconciliation.py

tests/engine/test_signal_engine.py
  -> tests/engine/trader/signals/test_evaluator.py

tests/engine/test_report_engine.py
  -> tests/engine/trader/reporting/test_assembler.py
  -> tests/engine/trader/reporting/test_metrics.py
  -> tests/engine/trader/reporting/test_render_terminal.py

tests/engine/test_trader_overrides.py
  -> tests/engine/trader/commands/test_processor.py
  -> tests/engine/trader/execution/test_liquidation.py
```

Do not move all tests in one giant commit. Move them with the modules they validate.

### Phase 6: Retire Compatibility Facades If Desired

Once the package is stable, decide whether to keep or remove facades.

Keeping these is acceptable:

```text
src/engine/trader/live_trader.py
src/engine/trader/state_manager.py
src/engine/trader/report_engine.py
src/engine/trader/report_generator.py
src/engine/trader/signal_engine.py
```

because they are canonical trader names, not legacy ghost names.

If kept, they should stay tiny: import/re-export only.

---

## Production-Hardening Backlog Carried Forward

The previous handoff's immediate checklist is complete, but the broader production work remains. The new package structure should make each of these straightforward.

### 1. Strict Typed Config

Current issue:

```text
the code still reads raw dicts in many places
some config-origin values still use .get(...)
missing config can silently fall back
```

Target home:

```text
src/engine/trader/config/models.py
src/engine/trader/config/loader.py
```

Recommended models:

```text
PipelineConfig
ExecutionConfig
StrategyConfig
TelegramConfig
```

Rules:

```text
YAML is parsed once at the boundary
internal services receive typed config objects
no config-origin .get("key", default)
missing required fields fail on boot
secrets remain in pydantic-settings .env, not YAML
```

Also note: the manifesto currently contains older language saying SQLite should be passive and RAM should be canonical. That conflicts with the newer production state architecture. A future doc cleanup should update the manifesto so it no longer contradicts the durable SQLite state model.

### 2. More Realistic Backtest Execution

Current issue:

```text
vectorized_engine.py uses full-bar shift via signal.shift(1)
the planned model wants T+1m latency / pessimistic high-low execution
```

Target home:

```text
src/simulation/execution_model.py
src/simulation/vectorized_engine.py
```

Trader refactor relevance:

```text
runtime/tick.py should expose clear signal timestamp semantics
execution/market_data.py should preserve candle timestamps precisely
reporting should state execution assumptions clearly
```

### 3. Exchange-Agnostic Market Filtering

Current issue:

```text
fetch_universe() still assumes Bybit-ish symbols ending in :USDT
```

Target home:

```text
src/data/fetcher/exchange_client.py
src/data/fetcher/market_filters.py
```

Desired approach:

```text
use exchange.load_markets() metadata
filter on active, swap, quote, settle, linear fields where available
isolate exchange-specific quirks behind adapter functions
do not hardcode exchange names inside strategy modules
```

### 4. Fuller Order Lifecycle States

Current issue:

```text
spread_positions is still mostly OPEN / CLOSED
leg_fills records target rows but not real exchange fills
```

Target home:

```text
state/positions.py
state/legs.py
state/events.py
execution/orders.py
```

Future statuses:

```text
PENDING_OPEN
OPEN
PENDING_CLOSE
CLOSED
FORCE_CLOSED_BY_AUDITOR
FAILED_OPEN
FAILED_CLOSE
ORPHANED_LEG
```

Future event types:

```text
SIGNAL_ENTRY
ORDER_SUBMITTED
ORDER_ACKED
PARTIAL_FILL
FILLED
ORDER_CANCELLED
ORDER_REJECTED
FORCE_CLOSE_REQUESTED
AUDITOR_OVERRIDE
```

Important production pattern:

```text
write intent before exchange action where possible
write observed result after exchange action
never hold DB transaction open during network calls
```

### 5. Boot Reconciliation

Current issue:

```text
schema and helpers exist
reports surface reconciliation status
no real boot reconciliation sequence blocks new entries yet
```

Target home:

```text
reconciliation/auditor.py
reconciliation/policy.py
state/reconciliation.py
runtime/trader.py
```

Boot sequence:

```text
open database
load runtime state
load active/pending local positions
fetch exchange positions/orders/fills
write reconciliation_runs row
write reconciliation_deltas rows
resolve obvious pending states
only then allow new entries
```

This should be implemented before real capital trading.

### 6. Real Auditor Behavior

Current issue:

```text
reconciliation tables exist, but no periodic auditor compares exchange reality to local expected reality
```

Target home:

```text
reconciliation/auditor.py
reconciliation/models.py
reconciliation/policy.py
```

Responsibilities:

```text
build exchange snapshot
build local snapshot
classify MATCH / EXCHANGE_ONLY_POSITION / LOCAL_ONLY_POSITION / PENDING_CLOSE_IGNORED
write deltas
decide whether to notify, pause, or request force close
avoid direct position mutation unless explicitly designed and tested
```

### 7. Future Live Order Execution

Current issue:

```text
the engine records paper-like state transitions
it does not submit real orders or update fills
```

Target home:

```text
execution/orders.py
execution/precision.py
state/legs.py
state/events.py
```

Rules:

```text
all precision goes through ccxt amount_to_precision / price_to_precision
client_order_id must be deterministic and idempotent
partial fills must update leg_fills
order events must be append-only
live order submission should be sequential and traceable
```

---

## Suggested Slice Order

Recommended implementation order:

```text
1. Extract state connection/schema/repositories behind TradeStateManager facade.
2. Extract reporting models/metrics/assembler/renderers.
3. Extract signals package.
4. Extract runtime scheduler/pairs/actions/pnl/market-data helpers.
5. Extract command processor and liquidation workflow.
6. Move tests to mirrored package paths.
7. Add typed config models.
8. Add boot reconciliation/auditor skeleton in read-only/reporting mode.
9. Expand order lifecycle statuses and leg fill update paths.
10. Only then consider real exchange order submission.
```

Why this order:

```text
state is the biggest and highest-risk file
reporting is large but read-only and easier to split safely
signals are already small and now math-aligned
runtime extraction becomes easier after state/report/signal APIs are stable
production behavior should wait until boundaries are readable
```

---

## Review Gates

Each phase should satisfy:

```text
full offline tests green
ruff green
no new ghost references except tests asserting absence of ghost schema
no new default config fallbacks
no network calls in unit tests
no DB transaction held over exchange/network calls
no file above ~350 lines without explicit justification
```

For larger phases, add a short note in the PR or commit message:

```text
Moved code only: yes/no
Behavior changed: yes/no
Schema changed: yes/no
Tests added/updated: list
```

---

## Definition Of Done For This Refactor

This refactor is done when:

```text
state_manager.py is a tiny facade or focused manager, not a 600+ line mixed repository
live_trader.py is a tiny facade or focused runtime class, not the entire engine
report_engine.py is a tiny facade or report assembler, not all metrics and models
report_generator.py is CLI glue only
signal_engine.py is either small or a facade to signals/evaluator.py
tests mirror the package structure
all current behavior remains green
the new tree has clear homes for config strictness, reconciliation, order execution, and auditor work
```

When this is complete, the trader layer should be ready for the next production-hardening stage without becoming unreadable.
