# Vectorized Engine Implementation Details

## Overview
The `VectorizedEngine` (located in `src/engine/core/engine.py`) is the core simulation unit. It avoids event-driven loops (iterating row-by-row) in favor of Pandas vector operations. This design choice makes it roughly **100-500x faster** than traditional backtesters, enabling rapid "Research -> Backtest" loops.

## How It Works

### 1. Data Alignment
The engine expects two primary inputs:
*   `Prices`: A DataFrame of Close prices (Dates x Symbols).
*   `Weights`: A DataFrame of Target Portfolio Weights (Dates x Symbols).

It ensures these are aligned on the same timestamp index.

### 2. Signal Shifting (Look-Ahead Bias Prevention)
A critical step in backtesting is preventing the strategy from acting on data it hasn't seen yet.
*   **Logic**: If a Signal is generated at the **Close** of bar `t` (using `Close_t`), we cannot trade until `t+1`.
*   **Implementation**: `allocated_weights = target_weights.shift(1)`
*   **Result**: The returns for bar `t` are driven by the weights decided at `t-1`.

### 3. PnL Calculation
The core PnL loop is calculated as:

$$ R_{net} = R_{gross} - C_{fund} - C_{txn} $$

#### A. Gross Returns ($R_{gross}$)
$$ R_{gross, t} = \sum (W_{i, t-1} \times R_{asset, i, t}) $$
*   Where $W$ is the weight of asset $i$ and $R_{asset}$ is the percentage change in price.

#### B. Funding Costs ($C_{fund}$)
Crucial for Perpetual Futures.
$$ C_{fund, t} = \sum (W_{i, t-1} \times FundingRate_{i, t}) $$
*   We use `DataFetcher`'s `ffill` logic to ensure funding rates effectively apply to the holding period.
*   If we are Long ($W > 0$) and Rate > 0, we Pay (Cost positive reduces return).
*   If we are Short ($W < 0$) and Rate > 0, we Receive (Cost negative increases return).

#### C. Transaction Costs ($C_{txn}$)
$$ C_{txn, t} = Turnover_t \times (Fee + Slippage) $$
*   **Turnover**: Defined as the absolute change in weights $|W_t - W_{t-1}|$.
*   **Rate**: Defaults to 0.06% (0.05% Fee + 0.01% Slippage).

### 4. Compounding vs Linear
*   **Compounding**: `Equity_t = Equity_{t-1} * (1 + R_{net})`. Logic: You reinvest profits.
*   **Linear**: `Equity_t = Initial + Sum(R_{net} * Initial)`. Logic: You trade a fixed size (e.g. $10k) regardless of account balance.

## Future Extensions
*   **Trade Reconstruction**: Converting the continuous weight series into a discrete "Trade Log" (Entry Price, Exit Price, Duration) for analysis.
*   **Drift Handling**: Currently the engine assumes we "rebalance to target" every bar. In reality, we might let prices drift to save fees. This can be added to the `Rebalancing Logic` section.
