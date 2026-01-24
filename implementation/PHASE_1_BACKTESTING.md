# Phase 1: The Vectorized Backtester

> **Objective**: Build a fast, lightweight simulation engine to test strategies against historical data in the Lakehouse.

## Overview
We will implement a **Vectorized Backtester** first. 
*   **Why Vectorized?**: It is 100x faster than event-driven for initial research. It allows us to iterate on thousands of parameter combinations in minutes.
*   **Engine**: We will use `pandas` (or `polars` if performance dictates later) to calculate signal columns and PnL vectors.

## Detailed Tasks

### Day 1: The `Strategy` Interface
- [ ] Define the abstract `BaseStrategy` class in `src/statarb/core/strategy.py`.
- [ ] **Critical Requirement**: Support **Multi-Asset** input (e.g. `btc_df` and `eth_df` for Pairs Trading).
- [ ] **Critical Requirement**: Return not just `Signals`, but also an `indicators` dict (e.g. `{'z_score': series}`) for visualization.
- [ ] Define the `Signal` data structure (timestamp, symbol, side, strength).
- [ ] **Acceptance Test**: Create a `DummyStrategy` that takes TWO symbols and calculates a spread.

### Day 2: The `VectorBacktester` Class
- [ ] Create `src/statarb/analytics/backtest.py`.
- [ ] Implement `calculate_pnl(signals, ohlcv)` function.
    - [ ] Logic: Entry price = Open (or Close of previous), Exit price = next entry.
    - [ ] Fee deduction: Apply `0.075%` (standard crypto taker fee) per trade side.
- [ ] **Acceptance Test**: Run backtest on a known sequence of prices (e.g., flat, double, flat). Manual calculation matches code output.

### Day 3: Metrics Calculation
- [ ] Implement `calculate_metrics(equity_curve)` in `src/statarb/analytics/metrics.py`.
    - [ ] Total Return (%)
    - [ ] Sharpe Ratio (Annualized)
    - [ ] Max Drawdown (%)
- [ ] **Acceptance Test**: Unit tests with synthetic equity curves (e.g., a straight line up should have huge Sharpe).

### Day 4: Integration with Lakehouse
- [ ] Create a script `apps/backtest_runner.py`.
- [ ] Logic:
    1.  Load data via `DuckDBReader`.
    2.  Instantiate Strategy.
    3.  Run Backtest.
    4.  Print Metrics.
- [ ] **Acceptance Test**: Run a "Golden Cross" strategy on 1 year of BTC/USDT data. It should complete in < 5 seconds and output a realistic PnL.

## Acceptance Criteria for Phase 1
1.  **Speed**: Backtest 1 year of 1-minute data in under 5 seconds.
2.  **Accuracy**: Fees are correctly deducted (PnL should be lower than raw price move).
3.  **Usability**: Changing a strategy parameter (e.g., Moving Average window) requires changing only 1 line of config.
