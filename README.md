# Crypto StatArb: Simple & Rigorous

> **Goal**: A lightweight, professional research environment for Crypto Pairs Trading. 
> **Philosophy**: Complexity is the enemy. We value fast iteration, transparency, and statistical rigor over complex "enterprise" architectures.

## 1. Objectives
1.  **Backtest Only**: Focus purely on research and validation. No live trading clutter.
2.  **Vectorized Speed**: Use Pandas/Vectorization to test years of data in seconds.
3.  **Statistical Rigor**: Go beyond "PnL". Use Monte Carlo permutations, Purged Cross-Validation, and Sharpe decay to validate skill vs luck.
4.  **Visual Validation**: Use a minimal Streamlit dashboard to inspect trade entries visually.

## 2. Tech Stack
*   **Python 3.9+**
*   **Pandas**: Core data manipulation and vectorized logic.
*   **Parquet**: Efficient, compressed file storage for 1h candles.
*   **Streamlit**: One-file dashboard for interactive chart exploration.
*   **Pytest**: Unit testing for critical math.

## 3. Simplified Architecture
No microservices. No complex dependency injection. Just clear modules.

```text
project_root/
├── data/                   # Flat Parquet files (e.g., BTC_USDT.parquet)
├── src/
│   ├── data/
│   │   ├── loader.py       # Data loading logic
│   │   └── fetcher.py      # Binance fetching script
│   ├── engine/
│   │   └── backtester.py   # Vectorized PnL calculator
│   ├── stats/
│   │   └── metrics.py      # Statistical tests (Monte Carlo, etc.)
│   ├── strategies/
│   │   └── pairs.py        # Logic for Pairs Trading
│   └── dashboard/
│       └── app.py          # Streamlit Dashboard
├── tests/                  # Unit tests
├── run_backtest.py         # Entry point for CLI
└── README.md
```

## 4. Key Workflows
*   **Research**: Edit `src/strategies/pairs.py` -> Run `python run_backtest.py` -> Check output.
*   **Verify**: Run `streamlit run app.py` -> Zoom into specific trades on the chart.
*   **Validate**: Run `python src/stats.py` -> Get a "Pass/Fail" on the strategy's robustness.
