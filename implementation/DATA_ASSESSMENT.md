# Data Strategy Assessment for Statistical Arbitrage

We have a strong foundation: **Downloader**, **Scanner**, **Universes**, and **Local Management**.
However, for a robust **Stats Arb** system (especially in Crypto), we are missing three critical components.

## 1. Funding Rates & Open Interest (The "Carry" Cost)
*   **Gap**: Currently, we only fetch `OHLCV` (Price/Volume).
*   **Why it matters**: In Crypto Stats Arb (Futures/Perps), the **Funding Rate** is a huge component of PnL.
    *   *Example*: You are Long Token A / Short Token B. If Token B has a high negative funding rate, you pay massive fees to hold the short. Your backtest will show profit, but reality will show a loss.
*   **Recommendation**:
    *   Add `fetch_funding_rate()` to the fetcher.
    *   Store it alongside price data (e.g., `data/binance/funding/BTC_USDT.parquet`).

## 2. Data Quality Control (The "Holes" Checker)
*   **Gap**: We assume downloaded data is perfect.
*   **Problem**: Exchanges have downtime. A 1-hour gap in `ETH` while `BTC` is trading causes the "Ratio" to spike artificially. The strategy will trigger a fake entry.
*   **Recommendation**:
    *   **Universe QC Tab**: A heatmap visualization.
        *   X-axis: Time.
        *   Y-axis: Asset.
        *   Color: Green (Data present), Red (Missing).
    *   *Quick check*: "Do all these 50 assets have exactly 8,760 rows for 2023?"

## 3. Delisting & Survivorship Logic
*   **Gap**: Determining if an asset was *actually tradable* on a specific past date.
*   **Why it matters**: Creating a universe of *current* top coins and backtesting 2 years ago is "Survivor Bias".
*   **Recommendation**:
    *   Hard to solve perfectly without a master database.
    *   *Intermediate Solution*: A "Listed Interval" check. When creating a Universe, warn if the asset's first timestamp > Universe Start Date.

## Summary of Proposed Tasks
1.  **[High Priority]** Implement `Funding Rate` downloading.
2.  **[Medium Priority]** Add a `Universe QC` visualization (Heatmap).
3.  **[Low Priority]** Add `Volume` filters to Universe configs (e.g. "Only include if Vol > $1M").
