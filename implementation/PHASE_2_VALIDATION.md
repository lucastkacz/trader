# Phase 2: Statistical Validation & Rigor

> **Objective**: Implement rigorous statistical tests to distinguish "skill" from "luck" and prevent overfitting.

## Overview
A backtest PnL is meaningless without statistical context. We will build a suite of tests that every strategy *must* pass before being considered for live trading.

## Detailed Tasks

### Day 1: Purged K-Fold Cross Validation
*Concept: Standard K-Fold leaks information because time-series data is correlated. We must "purge" (remove) data between train and test sets.*

- [ ] Implement `PurgedKFold` iterator in `src/statarb/analytics/validation.py`.
- [ ] Logic: Split data into K chunks. Train on K-1, Test on 1. Drop `embargo` samples after the test set to prevent leakage.
- [ ] **Acceptance Test**: Visual plot showing the Train/Test/Purge ranges on a timeline.

### Day 2: Combinatorial Purged Cross-Validation (CPCV)
*Concept: Generate many backtest paths to see distribution of outcomes.*

- [ ] Implement CPCV logic to generate N paths from K splits.
- [ ] **Acceptance Test**: Run on a strategy. Output mean Sharpe and StdDev of Sharpe across all paths.

### Day 3: The "White Reality Check" (Monte Carlo)
*Concept: Detrend the prices and run the strategy on "noise". If the strategy performs well on noise, it's overfit.*

- [ ] Implement `bootstrap_prices(ohlcv)` to generate synthetic price paths.
- [ ] Implement `run_permutation_test(strategy, n_paths=1000)`.
- [ ] **Acceptance Test**: A "Random Strategy" should fail this test (p-value > 0.05). A "Golden Cross" on a trending period might pass.

### Day 4: Deflated Sharpe Ratio (DSR)
*Concept: A Sharpe Ratio of 2.0 is good if you tried 1 strategy. It is bad if I tried 1000 strategies to find it.*

- [ ] Implement DSR calculation adjusting for the "Number of Trials".
- [ ] **Acceptance Test**: Calculator takes `Sharpe`, `N_trials`, and `Variance_of_Sharpes` and returns a Probability of Overfitting.

## Acceptance Criteria for Phase 2
1.  **The "Gatekeeper"**: A script `apps/validate_strategy.py` that takes a Strategy and runs ALL the above tests.
2.  **Output**: A PDF or Markdown report: "Strategy PASSED (p-value=0.01)" or "Strategy FAILED (High Probability of Overfitting)".
