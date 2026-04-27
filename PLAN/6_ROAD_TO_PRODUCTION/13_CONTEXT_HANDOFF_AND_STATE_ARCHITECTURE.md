# Context Handoff & Production State Architecture

## Purpose

This document is a continuation handoff for a new Codex session after the repository was scanned in detail on 2026-04-26. It preserves the current architectural understanding, implementation findings, test results, and the recommended SQL/state-management strategy before the project grows larger.

The user is building a crypto statistical-arbitrage platform that may eventually trade real capital. Treat every architectural decision below as production-risk-sensitive.

---

## One-Paragraph System Summary

The project is an exchange-agnostic statistical arbitrage platform. The intended chain is:

```text
historical data mining
-> liquidity / maturity universe filtering
-> Louvain correlation clustering
-> bidirectional cointegration discovery
-> vectorized stress testing
-> config-driven trader execution
-> SQLite state and reporting
-> Telegram monitoring and overrides
-> CI/CD promotion to VPS
```

The core design goal is one codebase across `dev`, `uat`, `prod`, and `backtest`, with behavior controlled by YAML configuration plus `.env` secrets rather than separate scripts or environment-specific Python branches.

---

## Important Paths

Read these first in a new chat:

```text
PLAN/00_MASTER_INDEX.md
PLAN/1_DEVELOPER_AND_AI_PROTOCOLS/01_coding_manifesto.md
PLAN/6_ROAD_TO_PRODUCTION/10_environment_and_secrets_strategy.md
PLAN/6_ROAD_TO_PRODUCTION/12_ghost_to_trader_refactoring.md
PLAN/6_ROAD_TO_PRODUCTION/13_CONTEXT_HANDOFF_AND_STATE_ARCHITECTURE.md

configs/pipelines/dev.yml
configs/pipelines/uat.yml
configs/pipelines/prod.yml
configs/universe/alpha_v1.yml
configs/strategy/alpha_v1.yml
configs/backtest/stress_test.yml
configs/telegram/dev.yml

main.py
src/pipeline/master_flow.py
src/engine/trader/live_trader.py
src/engine/trader/state_manager.py
src/engine/trader/signal_engine.py
src/engine/trader/report_engine.py
src/interfaces/telegram/daemon.py
src/data/fetcher/exchange_client.py
src/data/fetcher/historical_miner.py
```

---

## Current Implementation Shape

The repository has mostly moved away from procedural scripts into domain packages:

```text
src/core/                  logging and secrets
src/data/                  CCXT and parquet storage
src/screener/              maturity, returns matrix, Louvain clustering, discovery orchestration
src/engine/analysis/       cointegration math
src/simulation/            vectorized stress testing and friction model
src/engine/trader/         live/paper trader, SQLite state, reports
src/interfaces/telegram/   Telegram notifier and command daemon
src/pipeline/              Prefect master flows
src/risk/                  position sizing
src/utils/                 timeframe math
```

`main.py` currently exposes:

```bash
python main.py research --pipeline configs/pipelines/dev.yml \
                        --universe configs/universe/alpha_v1.yml \
                        --backtest configs/backtest/stress_test.yml \
                        --strategy configs/strategy/alpha_v1.yml

python main.py execute --pipeline configs/pipelines/dev.yml \
                       --strategy configs/strategy/alpha_v1.yml \
                       --telegram configs/telegram/dev.yml
```

The current YAML config split is good:

```text
configs/pipelines/   runtime environment, exchange, db path, heartbeat, max ticks
configs/universe/    what assets are eligible
configs/strategy/    live signal thresholds and lookbacks
configs/backtest/    simulation grid and friction assumptions
configs/telegram/    Telegram environment metadata
```

---

## Non-Negotiable Refactoring Policy

The Ghost-to-Trader refactor in `PLAN/6_ROAD_TO_PRODUCTION/12_ghost_to_trader_refactoring.md` is canonical. Do not preserve legacy `ghost` naming to make old code work.

Project rule going forward:

```text
If old code contradicts the new architecture, the old code is wrong.
Do not add compatibility layers to make stale code work.
Prefer clean breakage plus tests over silent support for stale concepts.
```

This matters more than convenience because the system may trade real money. Ambiguous names like `ghost_orders` hide whether a component is paper-only or production-capable. The engine is now `trader`, and state/schema names should be production-neutral.

---

## Findings From Codebase Scan

### 1. Git Ignore Is Currently Dangerous

`.gitignore` contains broad patterns like:

```text
data/
logs/
```

Because these are not root-scoped, they also ignore nested directories named `data`, including:

```text
src/data/fetcher/exchange_client.py
src/data/fetcher/historical_miner.py
tests/data/test_exchange_client.py
```

`git status --ignored src/data tests/data .gitignore` showed those new files as ignored. This is the highest priority repository hygiene bug because the old `binance_client.py` is deleted while the replacement exchange client may not be committed.

Fix by changing the ignore rules to:

```text
/data/
/logs/
```

Then verify:

```bash
git status --short --ignored src/data tests/data
```

### 2. Offline Tests Are Not Green

Command run:

```bash
PYTHONPATH=. .venv/bin/pytest tests -m "not live" --tb=short
```

Result:

```text
43 passed, 6 failed, 3 errors, 3 deselected
```

Main causes:

- `tests/core/test_logger.py` calls `configure_logger(..., env="test")`, but `src/core/logger.py` now expects `log_level`.
- `tests/engine/test_report_engine.py` calls `generate_report(...)` without the new required `min_sharpe`.
- `tests/interfaces/telegram/test_notifier.py` sets `settings.env`, but `Settings` no longer has an `env` field.

These are refactor drift, not deep math failures.

### 3. Ruff Is Not Green

Command run:

```bash
.venv/bin/ruff check src/ scripts/ tests/
```

Failures:

- `scripts/` does not exist.
- `src/pipeline/master_flow.py` has two f-strings without interpolation.
- `tests/engine/test_trader_overrides.py` imports unused `MagicMock`.

CI currently runs `ruff check src/ scripts/ tests/`, so GitHub Actions will fail until workflows are updated.

### 4. Workflows Still Reference Deleted Script Architecture

The GitHub workflows under `.github/workflows/` still call deleted pre-refactor modules such as:

```bash
python -m scripts.ghost_trader --turbo
python -m scripts.ghost_report --turbo --json
```

These commands should not be reintroduced. The current repo no longer has `scripts/`, and the architecture now routes through `main.py` and `src.engine.trader.report_generator`.

The workflows also still reference stale environment names:

```text
BYBIT_READONLY_API_KEY
BYBIT_READONLY_API_SECRET
GHOST_EXCHANGE
data/ghost/
ghost-trader
ghost-telegram
```

These need to be reconciled with the newer model:

```text
EXCHANGE_READONLY_API_KEY
EXCHANGE_READONLY_API_SECRET
EXCHANGE_LIVE_API_KEY
EXCHANGE_LIVE_API_SECRET
configs/pipelines/{dev,uat,prod}.yml
data/{dev,uat,prod}/...
trader
telegram
```

Treat every remaining `ghost` reference in CI/CD, docs, tests, logs, paths, and database schema as architectural debt to remove, not as a compatibility target.

### 5. Telegram Daemon Cannot Currently Run

`src/interfaces/telegram/daemon.py` calls:

```python
state = TradeStateManager()
```

But `TradeStateManager` requires:

```python
TradeStateManager(db_path: str)
```

This appears in every command handler. The daemon receives `--config` from `master_flow.py`, but it does not parse CLI args or read the telegram YAML. It therefore has no way to find the trader database.

This must be fixed before Telegram command control can be trusted.

### 6. `LiveTrader` Has an Uninitialized Pause Flag

`src/engine/trader/live_trader.py` reads:

```python
if SYSTEM_PAUSED:
```

But `SYSTEM_PAUSED` is never initialized at module level. The test passes only because `/pause` creates the global before it is asserted. A real first tick before any `/pause` command can raise `NameError`.

Do not keep pause state as an unstructured global. Move it to durable database-backed runtime state, or at minimum initialize it explicitly while planning the database-backed replacement.

### 7. Config Strictness Is Not Yet Enforced

The PLAN bans `.get("key", default)` for config-originated parameters. The code still contains examples:

```python
pipeline_cfg.get("min_volume", 20_000_000)
pipeline_cfg.get("max_symbols")
execution_cfg.get("max_ticks", None)
p.get("Performance", {}).get("sharpe_ratio", 0)
```

Some `.get()` usage is harmless for optional non-config data, but configuration should move to Pydantic models so missing fields fail on boot with precise errors.

### 8. Live Signal Math Is Not Yet Aligned With Cointegration Output

`DiscoveryEngine` stores `Hedge_Ratio`, `P_Value`, `Half_Life`, and `Best_Params`.

But `signal_engine.py` currently uses:

```python
spread = log_a - log_b
```

This ignores the discovered hedge ratio. The live trader may therefore trade a different spread than the one that passed cointegration and stress testing.

Next stage should align:

```text
discovery spread definition
-> backtest spread definition
-> live signal spread definition
```

The hedge-adjusted spread should be explicit and tested.

### 9. Backtest Execution Model Is Still Simplified

The PLAN wants `T+1m` execution modeling and high/low pessimism. Current `vectorized_engine.py` uses:

```python
out["position"] = out["signal"].shift(1).fillna(0.0)
```

This is a full-bar delay, not the planned `T+1m` latency barrier. That is acceptable for an early work-in-progress, but it should be marked as incomplete because it changes expected performance.

### 10. Exchange Agnosticism Is Incomplete

`exchange_client.py` now accepts a raw CCXT exchange ID, which is good. But `fetch_universe()` assumes symbols end with:

```python
":USDT"
```

That may work for Bybit USDT perpetual swaps but is not fully exchange-agnostic across CCXT. Eventually use `exchange.load_markets()` metadata and filter on market fields such as `swap`, `active`, `quote`, `settle`, and `linear`, with exchange-specific quirks isolated in one adapter layer if unavoidable.

---

## Production SQL / State Architecture Recommendation

### The Core Decision

Do not make RAM the canonical trading state.

For production with real capital:

```text
Exchange = objective reality
SQLite/Postgres = durable expected reality
RAM = temporary cache only
```

If the process dies, RAM disappears. A trading system must be able to reboot and reconstruct:

- what it intended to open
- what it believes is open
- which legs were pending or partially filled
- which commands were issued by the user
- what the latest known exchange reconciliation said
- whether the engine is paused

That information belongs in a durable local ledger.

### Recommended V1: SQLite Is Acceptable On A Single VPS

For your current architecture, SQLite is a good V1 production database if all of these are true:

- one VPS
- one trader process
- one Telegram daemon
- low write volume
- 4H cadence
- no multi-host writers
- no web dashboard doing heavy concurrent writes

This project fits that profile.

The production standard is not "never use SQLite." The production standard is: use the simplest durable database that matches your concurrency model, and design the state machine correctly.

SQLite with WAL mode can support concurrent readers and a single writer. The official SQLite WAL documentation says readers and writers can proceed concurrently, but there is still only one writer at a time. That is fine here because trade-state writes are tiny and infrequent.

Official SQLite caveats matter:

- WAL requires all processes to be on the same host; do not put the database on a network filesystem.
- WAL uses `-wal` and `-shm` sidecar files that are part of the database state while open.
- applications should still be prepared for `SQLITE_BUSY`.

Source: SQLite WAL documentation: https://www.sqlite.org/wal.html

### When To Upgrade To Postgres

Move to Postgres when any of these become true:

- more than one machine writes state
- multiple worker processes execute orders
- you build a dashboard/API server with write access
- you need row-level locking across workers
- you need stronger operational tooling, streaming replication, managed backups, or point-in-time recovery
- SQLite lock behavior becomes an operational bottleneck

Do not start with Postgres just for prestige. It adds deployment, backup, network, credentials, migrations, and monitoring overhead. For a solo 4H bot on one VPS, that complexity can create more risk than it removes.

### Recommended State Model

Use SQLite as both:

1. append-only event ledger
2. durable current-state projection

Do not choose between append-only and current state. Use both.

Event ledger tables answer:

```text
What happened, in what order, and why?
```

Projection tables answer:

```text
What does the engine currently believe is true?
```

This gives you auditability and fast boot recovery.

### Proposed Tables

Do not keep the existing `ghost_orders` table name. It contradicts the completed Ghost-to-Trader refactor and implies paper-only behavior. Replace it with production-neutral state tables.

Recommended canonical table set:

```text
spread_positions
order_events
leg_fills
equity_snapshots
tick_signals
user_commands
runtime_state
reconciliation_runs
reconciliation_deltas
```

#### `spread_positions`

The current projection of each spread.

Important fields:

```text
id
pair_label
asset_x
asset_y
side
status
entry_price_a
entry_price_b
exit_price_a
exit_price_b
weight_a
weight_b
hedge_ratio
entry_z
exit_z
lookback_bars
opened_at
closed_at
realized_pnl_pct
close_reason
created_at
updated_at
```

Allowed statuses should be explicit:

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

Avoid simple binary `OPEN` / `CLOSED` once real orders exist.

#### `order_events`

Append-only journal of intended and observed order actions.

Examples:

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

Every event should include:

```text
spread_id
event_type
payload_json
created_at
idempotency_key
```

The `idempotency_key` is important for crash recovery. If a command is retried after a process death, the system should know whether that intent already exists.

#### `leg_fills`

Tracks the individual exchange legs.

Fields:

```text
spread_id
symbol
side
target_qty
filled_qty
avg_fill_price
exchange_order_id
client_order_id
status
created_at
updated_at
```

This is essential before real money because a spread can be half-filled.

#### `runtime_state`

Durable operational toggles.

Fields:

```text
key
value_json
updated_at
```

Use it for:

```text
system_paused
last_tick_started_at
last_tick_finished_at
engine_version
last_reconciliation_at
```

This replaces the current `SYSTEM_PAUSED` global.

#### `user_commands`

Already exists in current implementation. Keep it append-only from Telegram. Telegram should never directly mutate positions.

Recommended command lifecycle:

```text
PENDING
CLAIMED
EXECUTED
FAILED
IGNORED
```

The trader should claim commands in a transaction, execute them, then mark the result.

#### `reconciliation_runs` and `reconciliation_deltas`

These support the auditor.

Each reconciliation run records:

```text
started_at
finished_at
exchange_snapshot_json
local_open_positions_json
status
```

Each delta records:

```text
run_id
delta_type
symbol
spread_id
action_taken
payload_json
```

Use production-neutral delta names:

```text
EXCHANGE_ONLY_POSITION
LOCAL_ONLY_POSITION
MATCH
PENDING_CLOSE_IGNORED
```

### Transaction Rules

Every state transition must happen inside an explicit transaction.

Examples:

Opening a paper/live spread:

```text
BEGIN
insert order event SIGNAL_ENTRY
insert or update spread_positions -> PENDING_OPEN
insert leg target rows
COMMIT
```

After both legs are confirmed:

```text
BEGIN
insert fill events
update leg_fills
update spread_positions -> OPEN
COMMIT
```

Closing:

```text
BEGIN
update spread_positions -> PENDING_CLOSE
insert close intent event
COMMIT

execute exchange close

BEGIN
insert fill events
update spread_positions -> CLOSED
write realized PnL
COMMIT
```

The important production pattern is: write intent before acting when possible, then write observed result after acting.

### SQLite PRAGMA Settings For Real Money

For the low-frequency trading engine, choose durability over micro-speed:

```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=FULL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;
```

Current code already has:

```sql
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;
```

Add:

```sql
PRAGMA synchronous=FULL;
PRAGMA foreign_keys=ON;
```

Consider periodic checkpoints:

```sql
PRAGMA wal_checkpoint(TRUNCATE);
```

Do not run long transactions. Do not let the Telegram daemon hold a connection open inside a command handler longer than needed.

### Single-Writer Discipline

Even with WAL, SQLite still has one writer at a time. That is okay if writes are tiny.

Production discipline:

- trader owns position state transitions
- Telegram only appends commands
- reporting reads only
- auditor can write reconciliation rows and emergency state transitions, but should be carefully serialized
- never perform network calls while holding a database transaction open

If two processes write often enough to cause lock contention, that is the signal to either funnel writes through the trader or upgrade to Postgres.

### Boot Recovery Protocol

On startup, the trader should not just resume blindly.

Recommended boot sequence:

```text
1. Open database.
2. Load runtime_state.
3. Load spread_positions where status in PENDING_OPEN, OPEN, PENDING_CLOSE, ORPHANED_LEG.
4. Fetch exchange positions.
5. Run reconciliation.
6. Resolve obvious PENDING states.
7. Only then allow new entries.
```

Do not hunt new trades until recovery and reconciliation are complete.

### Exchange Is The Final Truth

The database is the engine's memory, not reality itself.

Reality hierarchy:

```text
1. Exchange balances / positions / order fills
2. Local durable database
3. RAM cache
4. Logs / reports
```

The auditor exists to compare 1 and 2. If they disagree, do not trust RAM.

### Recommendation Summary

For this project:

```text
Use SQLite for now.
Use it as durable state plus append-only audit log.
Do not use RAM as source of truth.
Do not upgrade to Postgres yet.
Design state transitions and reconciliation as if real money depends on them, because it will.
```

---

## Immediate Next Steps For A New Chat

### Step 1: Fix Git Tracking

- Update `.gitignore` root-scoped data/log patterns.
- Ensure these files are no longer ignored:

```text
src/data/fetcher/exchange_client.py
src/data/fetcher/historical_miner.py
tests/data/test_exchange_client.py
```

### Step 2: Make Offline Tests Green

Fix drift in:

```text
tests/core/test_logger.py
tests/engine/test_report_engine.py
tests/interfaces/telegram/test_notifier.py
```

Run:

```bash
PYTHONPATH=. .venv/bin/pytest tests -m "not live" --tb=short
```

### Step 3: Make Ruff Green

Update workflow path away from nonexistent `scripts/`, remove stray f-string prefixes, remove unused imports.

Run:

```bash
.venv/bin/ruff check src tests
```

### Step 4: Fix Telegram DB Wiring

- Parse `--config` in `src/interfaces/telegram/daemon.py`.
- Load `configs/telegram/dev.yml`.
- Decide whether telegram config should point directly to the trader DB or whether the pipeline config should be passed too.
- Instantiate `TradeStateManager(db_path=...)`.
- Add tests for `/status`, `/pause`, `/resume`, `/stop_all` command writes.

### Step 5: Fix Runtime Pause State

Replace uninitialized `SYSTEM_PAUSED` with durable database-backed `runtime_state`.

Short-term minimal fix:

```python
SYSTEM_PAUSED = False
```

Preferred real fix:

```text
runtime_state key = "system_paused"
```

### Step 6: Formalize State Schema

Before live trading work, replace the legacy `ghost_orders` schema with the production-neutral model:

```text
spread_positions
order_events
leg_fills
runtime_state
reconciliation_runs
reconciliation_deltas
```

Do not preserve `ghost_orders` for backwards compatibility. If existing dev databases break, they break. Regenerate local data and reports under the new schema.

### Step 7: Align Signal / Backtest / Cointegration Math

Make the same hedge-adjusted spread definition flow through:

```text
CointegrationEngine
StressTestOrchestrator
SignalEngine
LiveTrader
ReportEngine
```

### Step 8: Update CI/CD

Replace old script calls with current entrypoints:

```bash
python main.py research ...
python main.py execute ...
python -m src.engine.trader.report_generator ...
```

Remove stale `ghost` paths and env var names rather than supporting both old and new names.

---

## Suggested New-Chat Prompt

Use this in a new chat:

```text
Please read PLAN/6_ROAD_TO_PRODUCTION/13_CONTEXT_HANDOFF_AND_STATE_ARCHITECTURE.md and PLAN/6_ROAD_TO_PRODUCTION/12_ghost_to_trader_refactoring.md first, then inspect the current git status, .gitignore, src/engine/trader/state_manager.py, src/engine/trader/live_trader.py, src/interfaces/telegram/daemon.py, main.py, configs, and tests.

Goal: continue from the previous codebase scan. First fix gitignore/tracking and get offline tests plus ruff green. Then begin the production-safe SQLite state architecture refactor described in the handoff document.

Important constraint: the Ghost-to-Trader refactor is canonical. Do not keep legacy ghost naming, old script entrypoints, or backwards-compatible database tables just to make stale code work. If old dev databases or old reports break, that is acceptable. Move the architecture forward cleanly with trader-neutral names and tests.

Do not add new alpha features until the repo is commit-safe and the state strategy is clear.
```

---

## Source Notes

SQLite WAL documentation confirms the relevant concurrency shape: WAL allows readers and writers to proceed concurrently, but there is still only one writer at a time, and WAL should not be used over a network filesystem.

Reference:

```text
https://www.sqlite.org/wal.html
```

PostgreSQL remains the likely future upgrade when the architecture requires multi-host writes, worker concurrency, managed backups, or stronger operational database tooling.

Reference:

```text
https://www.postgresql.org/docs/current/transactions.html
```
