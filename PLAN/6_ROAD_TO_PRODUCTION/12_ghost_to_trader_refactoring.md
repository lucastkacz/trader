# The Ghost-to-Trader Refactoring & Mature Environment Architecture

## 1. Background: Why "Ghost" No Longer Fits

The term **Ghost Trading** was introduced during Epoch 3 planning to describe forward-testing against live market data without committing real capital — the bot would "ghost" through the order book, logging simulated fills into a local SQLite database. This was accurate at the time: the engine only had one mode, and that mode was paper trading.

The architecture has since matured far beyond that single use case. The **exact same execution engine** now operates identically across four distinct runtime environments. The only variables that change between them are injected via YAML pipeline configs and `.env` secrets — the Python code is completely environment-agnostic.

Calling this engine "Ghost" is now actively misleading:

- In **prod**, the engine executes real orders with real capital. There is nothing "ghost" about it.
- In **dev** and **uat**, the engine is still called "Ghost" even though it's simply the standard trader running in a sandboxed configuration.
- New developers or AI agents encountering `LiveGhostTrader`, `GhostStateManager`, or `GhostReport` have no intuitive understanding of what these classes actually do — the name implies something temporary or simulated, when in reality these are the permanent, production-grade components of the system.

---

## 2. The Four Runtime Environments

The Stat-Arb engine is a single codebase deployed across four environments. The engine code never changes — only the configuration injected at runtime determines the behavior.

| Environment | Machine | Timeframe | API Permission | Purpose |
|---|---|---|---|---|
| **`dev`** | Local Mac | `1m` | Read-Only | Rapid local iteration. The 1-minute timeframe compresses days of 4H market behavior into hours, allowing developers to observe full trade lifecycles (entry → hold → exit) without waiting real-time. This is a **forward-test** against live exchange data. |
| **`uat`** | Cloud VPS | `4h` | Read-Only | User Acceptance Testing. Runs the identical 4H production configuration but routes all orders to the local SQLite state database instead of the exchange. This is the final **forward-test** gate — the bot must survive 3-4 weeks of real market structure (funding rate cycles, weekend illiquidity, flash crashes) before promotion. |
| **`prod`** | Cloud VPS | `4h` | Full Trading | **Real capital allocation.** The engine executes live orders against a segregated exchange sub-account. This is not a test — this is the system operating autonomously with skin in the game. |
| **`backtest`** | Local Mac | Any | None (offline) | Vectorized historical simulation. Completely offline — no exchange connectivity. Uses the Phase 5 Arena engine with pessimistic friction modeling (buy Highs, sell Lows, continuous funding penalties). |

### Key Architectural Insight

The first three environments (`dev`, `uat`, `prod`) all run the **same trader engine**. The trader:

1. Wakes on candle boundary (or heartbeat interval)
2. Fetches live OHLCV data via CCXT
3. Evaluates cointegration signals
4. Manages state transitions (entry, hold, exit, flip) in SQLite
5. Dispatches Telegram notifications
6. Snapshots equity curves

Whether it's paper-trading or executing real orders is determined entirely by the pipeline YAML config and the API key permissions in `.env` — **not** by anything in the Python code. The code is environment-agnostic. Therefore, the engine deserves an environment-agnostic name.

---

## 3. The Refactoring: `ghost` → `trader`

### Renamed Directory

| Before | After |
|---|---|
| `src/engine/ghost/` | `src/engine/trader/` |

This pairs naturally with the existing `src/engine/analysis/` — analysis discovers alpha, trader executes it.

### Renamed Classes

| Before | After | Rationale |
|---|---|---|
| `LiveGhostTrader` | `LiveTrader` | Environment-neutral. Works for dev, uat, and prod. |
| `GhostStateManager` | `TradeStateManager` | Manages trade state, not "ghost" state. |
| `GhostReport` | `TradeReport` | Reports on trade performance, regardless of environment. |

### Renamed Files

| Before | After |
|---|---|
| `src/engine/ghost/__init__.py` | `src/engine/trader/__init__.py` |
| `src/engine/ghost/live_trader.py` | `src/engine/trader/live_trader.py` |
| `src/engine/ghost/state_manager.py` | `src/engine/trader/state_manager.py` |
| `src/engine/ghost/signal_engine.py` | `src/engine/trader/signal_engine.py` |
| `src/engine/ghost/report_engine.py` | `src/engine/trader/report_engine.py` |
| `src/engine/ghost/report_generator.py` | `src/engine/trader/report_generator.py` |
| `tests/engine/test_ghost_trader_overrides.py` | `tests/engine/test_trader_overrides.py` |

### Renamed Pipeline Functions

| Before | After |
|---|---|
| `task_execute_ghost()` | `task_execute_trader()` |

### Renamed Log Strings & UI Labels

All occurrences of "Ghost" in log messages, Telegram notifications, and CLI output are replaced with environment-neutral equivalents:

| Before | After |
|---|---|
| `"GHOST TICK @ ..."` | `"ENGINE TICK @ ..."` |
| `"Ghost Trader Starting"` | `"Trader Engine Starting"` |
| `"Ghost Trader crashed"` | `"Trader Engine crashed"` |
| `"GHOST TRADER STATUS"` | `"TRADER STATUS"` |
| `"open ghost positions"` | `"open positions"` |
| `data/ghost/reports/` | `data/reports/` |

### Renamed Data Paths

| Before | After |
|---|---|
| `data/ghost/reports/` | `data/reports/` |

---

## 4. Files Impacted (Full Manifest)

### Source (`src/`)
- `src/engine/trader/` — all 6 files (directory rename + class renames)
- `src/pipeline/master_flow.py` — import paths and function names
- `src/interfaces/telegram/daemon.py` — `GhostStateManager` → `TradeStateManager` imports and UI strings
- `src/interfaces/telegram/notifier.py` — docstring update

### Tests (`tests/`)
- `tests/engine/test_trader_overrides.py` — renamed file + updated imports
- `tests/engine/test_state_manager.py` — updated imports
- `tests/engine/test_signal_engine.py` — updated imports
- `tests/engine/test_report_engine.py` — updated imports

---

## 5. Design Principle

> **The engine is environment-agnostic. The name must be too.**

The word "trader" describes what the code *does* — it trades. Whether those trades are simulated (dev/uat) or real (prod) is a runtime configuration concern, not a code identity concern. This refactoring enforces that principle at every level of the codebase.

---

## 6. Data Layer Refactoring: Exchange-Agnostic, Zero Defaults

Performed alongside the Ghost→Trader rename, this refactoring eliminates all hardcoded defaults and exchange-specific coupling from the `src/data/` layer.

### Problem

1. **Two duplicate exchange clients** (`binance_client.py` and `bybit_client.py`) with near-identical logic.
2. **Hardcoded default values** everywhere: `timeframe="4h"`, `limit=1000`, `min_volume=20_000_000`, `exchange="binanceusdm"`.
3. **`live_client.py` referenced dead config fields** (`settings.ghost_exchange`, `settings.bybit_readonly_api_key`).

### Solution

| Change | Before | After |
|---|---|---|
| Exchange clients | `binance_client.py` + `bybit_client.py` | Single `exchange_client.py` |
| Exchange ID | Internal mapping/inference | Raw CCXT ID from YAML |
| `live_client.py` | Broken (dead config refs) | Rebuilt — all params required |
| `historical_miner.py` | Hardcoded to Bybit | Exchange-agnostic |
| `local_parquet.py` | `exchange="binanceusdm"` default | `exchange` required everywhere |
| Credential routing | N/A | `credential_tier` in pipeline YAML |

### Manifesto Updates (Section 6)

- **Zero Default Values in Function Signatures**
- **Exchange Agnosticism** — raw CCXT IDs, never inferred internally

### Pipeline YAML — `credential_tier`

```yaml
execution:
  exchange: "bybit"
  credential_tier: "readonly"  # or "live" for prod
```

### Files Deleted

- `src/data/fetcher/binance_client.py`
- `src/data/fetcher/bybit_client.py`
- `tests/data/test_binance_client.py`

### Files Created

- `src/data/fetcher/exchange_client.py`
- `tests/data/test_exchange_client.py`
