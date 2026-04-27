# Source Code Refactoring Journal

This document tracks structural refactoring changes applied to the `src/` directory to enforce clean separation of concerns and eliminate architectural debt.

---

## 2026-04-26 — Telegram Logic Extracted from `core/`

### Problem

The `src/core/` package was housing Telegram-specific integration logic (`notifier.py` and `telegram_daemon.py`) alongside foundational plumbing (`config.py`, `logger.py`). This violated single-responsibility: `core/` should contain only the lowest-level, dependency-free infrastructure that every other module imports.

### Solution

Created a new `src/interfaces/` namespace to house all external communication integrations. Telegram logic was relocated into `src/interfaces/telegram/`.

### File Moves

| Before | After |
|---|---|
| `src/core/notifier.py` | `src/interfaces/telegram/notifier.py` |
| `src/core/telegram_daemon.py` | `src/interfaces/telegram/daemon.py` |
| `tests/core/test_notifier.py` | `tests/interfaces/telegram/test_notifier.py` |

### Import Updates

- `src/engine/trader/live_trader.py` — `TelegramNotifier` import updated
- `src/pipeline/master_flow.py` — daemon subprocess module path updated
- `tests/engine/test_trader_overrides.py` — `TelegramNotifier` import updated

### Result

`src/core/` now contains strictly:
- `config.py` — Pydantic-settings secret loader
- `logger.py` — Loguru dual-sink setup

The `src/interfaces/` namespace is extensible for future integrations (Discord, Slack, webhooks, etc.) without polluting core infrastructure.

---

## 2026-04-26 — Ghost-to-Trader Rename

> # STATUS WARNING — SUPERSEDED IMPLEMENTATION DETAIL
>
> This section is a historical journal entry. It records the initial rename
> direction, but one detail below was later superseded by the production state
> architecture work:
>
> ```text
> ghost_orders was not preserved.
> spread_positions is the canonical positions table.
> ```
>
> Do not use this journal as authority for current database schema. The current
> authority is:
>
> ```text
> PLAN/6_ROAD_TO_PRODUCTION/12_ghost_to_trader_refactoring.md
> PLAN/6_ROAD_TO_PRODUCTION/13_CONTEXT_HANDOFF_AND_STATE_ARCHITECTURE.md
> PLAN/6_ROAD_TO_PRODUCTION/14_trader_modularization_and_production_hardening.md
> src/engine/trader/state_manager.py
> ```
>
> Any mention of preserving `ghost_orders` is obsolete and must not be followed.

### Problem

The term "Ghost" was introduced during Epoch 3 to describe paper trading against live data. The architecture has since matured into a single codebase deployed across four environments (dev, uat, prod, backtest). Calling the engine "Ghost" implied simulation-only behavior, which is misleading in production where real capital is at stake.

### Solution

Renamed the entire `src/engine/ghost/` directory and all associated classes, functions, and log strings to environment-neutral "trader" equivalents.

### Renamed Classes

| Before | After |
|---|---|
| `LiveGhostTrader` | `LiveTrader` |
| `GhostStateManager` | `TradeStateManager` |
| `GhostReport` | `TradeReport` |

### Renamed Directories & Files

| Before | After |
|---|---|
| `src/engine/ghost/` | `src/engine/trader/` |
| `tests/engine/test_ghost_trader_overrides.py` | `tests/engine/test_trader_overrides.py` |

### Renamed Functions

| Before | After |
|---|---|
| `task_execute_ghost()` | `task_execute_trader()` |

### Data Paths

| Before | After |
|---|---|
| `data/ghost/reports/` | `data/reports/` |

### SQL Table Preservation

**Superseded.** The initial idea of preserving `ghost_orders` for backward
compatibility was rejected during the production state architecture work.

Current canonical schema uses:

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

Old dev databases and reports are allowed to break. Do not add compatibility
layers for `ghost_orders`.

---
