# Phase 3: The Research Dashboard (Visual Validation)

> **Objective**: A central "Mission Control" to interactively explore data, strategies, and validation results.

## Overview
We will use **Streamlit** (or Dash) for its rapid development cycle and Python-native nature. It requires zero HTML/CSS knowledge and deals natively with Pandas DataFrames.

## Detailed Tasks

### Day 1: Data Lake Explorer
- [ ] Setup `src/statarb/apps/dashboard.py`.
- [ ] Create Tab 1: "Data Inspection".
- [ ] Components:
    -   Dropdown to select Exchange/Symbol.
    -   Candlestick Chart (using `plotly`).
    -   "Data Health" metrics: Missing candles count, Start/End dates.
- [ ] **Acceptance Test**: Open dashboard, select `BTC/USDT`, see a correct interactive chart.

### Day 2: Interactive Backtester
- [ ] Create Tab 2: "Strategy Lab".
- [ ] Components:
    -   Sidebar with Strategy Parameters (Sliding windows, thresholds).
    -   "Run Backtest" button.
    -   **Dynamic Charts**: Automatically plot the `indicators` returned by the strategy.
        -   Intelligent handling of "Overlays" (Bollinger Bands) vs "Oscillators" (Z-Score on separate panel).
    -   Output: Equity Curve chart, Monthly Returns Heatmap.
- [ ] **Acceptance Test**: Change a parameter, click Run, see the Equity Curve update in < 2 seconds.

### Day 3: Trade Inspector
- [ ] Add "Trade Drill-down" section to Tab 2.
- [ ] Logic: Click a trade in the log -> Zoom chart to that specific time -> Show markers for Entry/Exit.
- [ ] **Acceptance Test**: "Visual Verification" that the strategy buys where we think it should buy.

### Day 4: Validation Report Viewer
- [ ] Create Tab 3: "Rigor Check".
- [ ] Components:
    -   Upload/Select a Strategy Result.
    -   Show Histogram of Monte Carlo permutations.
    -   Show DSR (Deflated Sharpe Ratio) gauge.
- [ ] **Acceptance Test**: Visualize the "bell curve" of random strategies vs our strategy's performance.

## Acceptance Criteria for Phase 3
1.  **Zero Lag**: Charts must load fast (downsample data if needed).
2.  **Interactivity**: All charts must be zoomable/pannable.
3.  **No Code**: A non-technical user (or you in "Trader Mode") can evaluate a strategy using only the UI.
