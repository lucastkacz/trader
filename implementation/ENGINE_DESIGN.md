# Engine Design Document: Vectorized Backtester for Statistical Arbitrage

## Overview
This document outlines the architecture for a high-performance, vectorized backtesting engine designed specifically for Statistical Arbitrage (Pairs Trading, Cointegration, Mean Reversion) on crypto perpetual futures.

The core philosophy is **Vectorization First**: We calculate signals, positions, and returns on entire arrays (Pandas/NumPy) at once, rather than iterating row-by-row. This allows for rapid iteration and optimization.

## Core Requirements
1.  **Speed**: Vectorized operations (~100x faster than event loops).
2.  **Accuracy**: Realistic cost modeling (Fees, Slippage, Borrow).
3.  **Robustness**: Handling missing data, delistings, and universe changes.
4.  **Analysis**: Built-in Walk-Forward Optimization and detailed tearing sheets.

## Architecture Components

### 1. Data Layer (`src/engine/data.py`)
Responsible for preparing the "Matrix" of prices.
*   **Inputs**: Universe configuration, Date Range.
*   **Outputs**: Aligned DataFrames for `Close`, `Open`, `High`, `Low`, `Volume`.
*   **Handling Gaps**: Forward-fill (ffill) logic for missing ticks, with "Stuten" check (if gap > X hours, treat as missing/flat).

### 2. Alpha Engine (`src/engine/alpha.py`)
Abstract base class for strategies.
*   **Input**: `MarketData` object.
*   **Output**: `Signal` DataFrame (Start with raw signal, e.g., Z-Score).
*   Example: `PairsTradingAlpha` takes SymA, SymB -> Returns Z-Score of Spread.

### 3. Portfolio Optimizer (`src/engine/portfolio.py`)
Converts Raw Signals into **Target Weights**.
*   **Responsibility**:
    *   Scaling: Volatility targeting? Fixed capital?
    *   Constraints: `Sum(Weights) == 0` (Dollar Neutrality).
    *   Leverage: `Sum(Abs(Weights)) <= MaxLeverage`.
*   **Output**: `TargetWeights` DataFrame.

### 4. Execution Simulator (`src/engine/backtest.py`)
The core vector engine.
*   **Logic**:
    1.  **Shift**: `TargetWeights` are shifted by 1 period (signal at Close `t` -> trade at Open/Close `t+1`).
    2.  **Turnover**: Calculate `DeltaWeights` = `Abs(Weight_t - Weight_{t-1})`.
    3.  **Costs**: `Cost = Turnover * (Fee + Slippage)`.
    4.  **Gross Returns**: `Weight_{t-1} * AssetReturn_t`.
    5.  **Net Returns**: `Gross Returns - Costs`.
*   **Funding Rates**: If trading Perps, subtract `FundingRate * Position`! (Critical for crypto).

### 5. Statistics & Reporting (`src/engine/stats.py`)
*   **Metrics**: Total Return, CAGR, Volatility, Sharpe, Sortino, Max Drawdown, Win Rate.
*   **Plots**: Equity Curve (Log/Linear), Drawdown Underwater, Monthly Heatmap.

### 6. Walk-Forward Analysis (`src/engine/walkforward.py`)
*   **Function**: Splits data into Rolling Train/Test windows.
*   **Workflow**:
    1.  Define `TrainWindow` (e.g., 3 months) and `TestWindow` (e.g., 1 month).
    2.  Optimize Parameters on Train.
    3.  Run Best Params on Test.
    4.  Stitch Test results together for the final equity curve.

## Implementation Roadmap

### Phase 2.1: The Core Vector Engine
- [ ] Implement `Engine` class to accept `Weights` and `Prices`.
- [ ] Implement `CostModel` (Fee tier + Slippage).
- [ ] Output: `EquityCurve` series.

### Phase 2.2: Strategies & Signals
- [ ] Implement `ZScoreStrategy` (Rolling Mean/Std).
- [ ] Implement `CointegrationCheck` (Engle-Granger for pair selection).

### Phase 2.3: Walk-Forward Framework
- [ ] Implement `TimeSeriesSplit` logic.
- [ ] Implement Parallel processing for optimization (Joblib).

## Design Decisions (Validated)
1.  **Execution Price**: **OPEN** of the next bar.
2.  **Funding Rates**: Mandatory. Gaps will be `ffill`ed (forward filled) to ensure every timestamp has a rate.
3.  **Rebalancing Strategy**: **Signal-Based** (Default). We only rebalance when the *Strategy's Target Weight* changes, not just because price drifted. This saves transaction costs.
4.  **Capital Growth**: **Compounding** (Default). Profits are reinvested. Trade size grows with equity.

## Questions / Assumptions to Clarify
*(Resolved)*

