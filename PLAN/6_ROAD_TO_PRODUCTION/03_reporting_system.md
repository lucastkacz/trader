# Ghost Trader Reporting System

## The Problem

The current `ghost_report.py` is a basic text dump. When the ghost trader runs for 3-4 weeks, we need rigorous quantitative reporting that:

1. Tells you **exactly** what happened on every tick and every trade
2. Calculates the **institutional metrics** that determine if this system is viable
3. Generates **structured data** that can be fed back to an LLM for iterative improvement
4. Compares **live performance vs backtest expectations** to detect strategy decay

---

## Report Architecture

We will build a single comprehensive report engine (`src/engine/ghost/report_engine.py`) that computes all metrics from the SQLite database, and two output formats:

```
src/engine/ghost/report_engine.py    ← Pure math: reads DB → computes metrics
scripts/ghost_report.py              ← CLI: calls report engine → prints to terminal
data/ghost/reports/                  ← Auto-generated JSON + Markdown reports
```

---

## Report Sections

### 1. Executive Summary

The 30-second answer to "is it working?"

| Metric | Description |
|--------|-------------|
| **Total Equity** | Realized + Unrealized PnL as % of notional |
| **Realized PnL** | Closed trade profits/losses |
| **Unrealized PnL** | Open position mark-to-market |
| **Active Pairs** | How many of the 11 pairs currently have open positions |
| **Total Trades** | Completed round-trips |
| **Uptime** | Time since first tick |
| **Status** | 🟢 Healthy / 🟡 Degraded / 🔴 Failing |

### 2. Portfolio-Level Metrics

The numbers that determine if this engine has institutional viability.

| Metric | Formula | Why It Matters |
|--------|---------|---------------|
| **Sharpe Ratio** | Mean(returns) / Std(returns) × √N | Risk-adjusted return — the single most important metric |
| **Sortino Ratio** | Mean(returns) / Downside_Std × √N | Sharpe but only penalizes downside volatility |
| **Max Drawdown** | Max peak-to-trough decline in equity curve | Worst-case capital destruction |
| **Calmar Ratio** | Annualized Return / Max Drawdown | Return per unit of tail risk |
| **Win Rate** | Winning trades / Total trades | How often we're right |
| **Profit Factor** | Gross Profit / Gross Loss | How much we make vs lose |
| **Expectancy** | (Win% × Avg Win) - (Loss% × Avg Loss) | Expected PnL per trade |
| **Avg Holding Period** | Mean time from entry to exit | How long capital is locked |
| **Trades Per Week** | Total trades / Weeks elapsed | Activity rate |

#### Equity Curve Returns

The equity snapshots are recorded every 4H tick. From these we derive:

- **Per-tick returns**: `r_t = equity_t - equity_{t-1}`
- **Rolling 7-day Sharpe**: Trailing window for trend detection
- **Rolling Max Drawdown**: Peak-to-trough with recovery tracking
- **Drawdown Duration**: How many ticks until recovery from each trough

### 3. Per-Pair Breakdown

Individual pair performance to identify which pairs are carrying alpha and which are dragging.

| Metric | Per Pair |
|--------|----------|
| Realized PnL | Sum of all closed trade PnL |
| Unrealized PnL | Current mark-to-market (if position open) |
| Trade Count | Completed round-trips |
| Win Rate | Wins / Total for this pair |
| Avg PnL per Trade | Mean realized PnL |
| Avg Holding Period | Mean time in position |
| Current Status | FLAT / LONG_SPREAD / SHORT_SPREAD |
| Current Z-Score | Latest signal evaluation |
| **Backtest Sharpe** | From `surviving_pairs.json` — for comparison |
| **Live vs Backtest** | Is live PnL direction matching backtest expectation? |

This is the most actionable section: if a pair consistently loses in live while it won in backtest, it signals **strategy decay** for that cointegration relationship.

### 4. Trade Log

Every single completed trade, chronologically, with full detail:

```
ID | Pair          | Side         | Entry Z | Entry A    | Entry B   | wA   | wB   | Exit A     | Exit B    | PnL%     | Holding | Result
---+---------------+--------------+---------+------------+-----------+------+------+------------+-----------+----------+---------+-------
 1 | MET/LTC       | LONG_SPREAD  | -2.31   | 0.1337     | 53.52     | 0.35 | 0.65 | 0.1350     | 53.10     | +0.82%   | 12h     | ✓
 2 | 1000PEPE/AVNT | SHORT_SPREAD | +1.87   | 0.003461   | 0.1331    | 0.52 | 0.48 | 0.003440   | 0.1345    | -0.15%   | 8h      | ✗
```

### 5. Signal Quality Analysis

How good are our signals? This section measures the *predictive accuracy* of the Z-score model:

| Metric | Description |
|--------|-------------|
| **Signal Accuracy** | % of entries that result in positive PnL |
| **Avg Entry Z-Score** | Mean absolute Z at entry — are we entering at extreme enough levels? |
| **Avg Exit Z-Score** | Mean absolute Z at exit — are we exiting at mean reversion? |
| **False Signal Rate** | % of entries where spread diverged further instead of reverting |
| **Mean Reversion Speed** | Avg ticks from entry to Z-score crossing zero |

### 6. Risk Monitoring

Real-time risk dashboard for the currently running system:

| Metric | Description |
|--------|-------------|
| **Portfolio Heat** | Sum of absolute exposure across all open positions |
| **Pair Correlation** | Are open positions' PnL moving together? (correlation = 1 means no diversification) |
| **Largest Single Position Loss** | Worst unrealized loss right now |
| **Days Since Last Trade** | Staleness detector — if no trades for 7+ days, something is wrong |
| **Consecutive Losses** | Current losing streak |
| **Data Freshness** | Timestamp of last successful candle fetch per pair |

### 7. Backtest vs Live Comparison (Strategy Health)

The core question: **Is the backtest alpha surviving contact with reality?**

| Metric | Backtest (4yr) | Live (N weeks) | Deviation |
|--------|---------------|----------------|-----------|
| Sharpe Ratio | 1.65 | ? | ? |
| Win Rate | ? | ? | ? |
| Avg Trade PnL | ? | ? | ? |
| Max Drawdown | -29.82% | ? | ? |

If live Sharpe is > 50% of backtest Sharpe, the strategy is **validated**.
If live Sharpe is < 30% of backtest Sharpe, investigation required.
If live Sharpe is negative, the cointegration may have structurally broken.

---

## Output Formats

### 1. Terminal (Human-Readable)

```bash
# Quick check
PYTHONPATH=. python -m scripts.ghost_report

# Detailed with trade log
PYTHONPATH=. python -m scripts.ghost_report --detailed

# Specific pair deep-dive
PYTHONPATH=. python -m scripts.ghost_report --pair "MET/USDT|LTC/USDT"
```

### 2. JSON (Machine-Readable / LLM-Consumable)

Every report run also writes a structured JSON file:

```bash
data/ghost/reports/report_20260415_0800.json
```

This file contains ALL computed metrics in a format that can be:
- Fed back to an LLM for analysis and improvement suggestions
- Loaded into a Jupyter notebook for custom visualization
- Compared across time periods to track strategy evolution
- Used to auto-generate alerts (e.g., if max DD exceeds threshold)

### 3. Markdown (Archival)

A rendered Markdown report for each week:

```bash
data/ghost/reports/weekly_report_week01.md
```

---

## Data We Need to Capture (Schema Enhancements)

The current SQLite schema is missing some fields that the reporting system needs.

### Additional Fields for `ghost_orders` Table

| Field | Type | Purpose |
|-------|------|---------|
| `exit_z` | REAL | Z-score at exit — needed for signal quality analysis |
| `holding_bars` | INTEGER | Trade duration in 4H bars — avoids timestamp math |

### Additional Fields for `equity_snapshots` Table

| Field | Type | Purpose |
|-------|------|---------|
| `per_pair_pnl` | TEXT (JSON) | JSON dict of unrealized PnL per pair — needed for correlation analysis |

### New Table: `tick_signals`

Record every signal evaluation, not just entries/exits:

```sql
CREATE TABLE IF NOT EXISTS tick_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    pair_label TEXT NOT NULL,
    z_score REAL NOT NULL,
    weight_a REAL NOT NULL,
    weight_b REAL NOT NULL,
    signal TEXT NOT NULL,        -- LONG_SPREAD / SHORT_SPREAD / FLAT
    action TEXT NOT NULL,        -- ENTRY / EXIT / HOLD / SKIP
    price_a REAL NOT NULL,
    price_b REAL NOT NULL
);
```

This is critical for signal quality analysis. Without it, we only know what happened when we entered/exited, not what signals were generated on ticks where we held or stayed flat.

---

## Implementation Plan

### Phase 1: Schema Enhancement
- Add `exit_z`, `holding_bars` to `ghost_orders`
- Add `per_pair_pnl` to `equity_snapshots`
- Add `tick_signals` table
- Update `state_manager.py` and `ghost_trader.py` to populate new fields

### Phase 2: Report Engine
- Build `src/engine/ghost/report_engine.py` — pure computation, no I/O formatting
- Accepts a `GhostStateManager` → returns a `GhostReport` dataclass with all metrics

### Phase 3: Output Renderers
- Rewrite `scripts/ghost_report.py` to use report engine
- Add `--detailed`, `--pair`, `--json`, `--export` flags
- Auto-generate JSON reports per tick

### Phase 4: Alerting (Future)
- Webhook integration for critical alerts (max DD exceeded, pair failure, process crash)
- This uses the existing `webhook_url` config field

---

## What This Gives an LLM

When you feed me a `report_YYYYMMDD.json`, I can:

1. **Identify dying pairs** — spot cointegration decay before it costs money
2. **Tune parameters** — suggest Z-score or lookback adjustments based on live signal quality
3. **Recommend pair removal/addition** — data-driven universe management
4. **Debug anomalies** — if a specific tick produced unexpected behavior, the `tick_signals` table tells me exactly what the engine saw
5. **Project forward** — estimate Epoch 4 capital requirements based on live Sharpe and drawdown data
6. **Stress test assumptions** — compare the pessimistic backtest friction model against actual live spread behavior
