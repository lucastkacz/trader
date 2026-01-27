# Master Plan: The "Sprint" to Verification

This plan prioritizes getting a working Backtest + Dashboard loop immediately, then adding the heavy statistics.

## Phase 1: The Skeleton (Day 1)
**Goal**: Get data in, run a dummy strategy, see a chart.
1.  **Data**: Create a script to fetch 1h data for BTC and ETH from Binance and save as `data/BTC_USDT.parquet`.
2.  **Loader**: Write `src/data.py` to load these into aligned DataFrames.
3.  **Strategy**: Write a simple "Ratio" calculation in simple Pandas.
4.  **Visualization**: Spin up `app.py` (Streamlit) to plot the Ratio and Price.

## Phase 2: The Engine (Day 2)
**Goal**: Calculate accurate PnL.
1.  **Signals**: Define exact entry/exit rules (e.g., Z-Score > 2).
2.  **Vector Backtester**: Implement `src/engine.py` to take signals -> calculate Equity Curve.
    *   *Constraint*: Must account for Transaction Costs (Fees + Slippage).
3.  **Metrics**: Calculate Sharpe, Max Drawdown, CAGR.

## Phase 3: The "Science" (Day 3)
**Goal**: Validate the strategy is not random noise.
1.  **Monte Carlo**: Shuffle the trades 1000 times. Does the real strategy beat 95% of random runs?
2.  **Stability**: Run the strategy on different time subsets (Cross-Validation).

## Phase 4: Refinement (Day 4+)
1.  Add more pairs (screening/selection).
2.  Optimize Z-Score windows.
