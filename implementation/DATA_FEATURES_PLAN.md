# Data Features Implementation Plan

## Goal
1.  **Funding Rate Support**: Fetch and store Funding Rates for perpetual/futures pairs (critical for Stats Arb).
2.  **Data Quality Control (QC)**: Visualize data health (gaps, missing rows) via a new Dashboard tab.

## 1. Backend: Funding Rates (`src/data/fetcher/`)

### `src/data/fetcher/provider.py`
*   **New Function**: `fetch_funding_rates(exchange, symbol, start_date, end_date)`
    *   Uses `ccxt` method `fetch_funding_rate_history` (if available).
    *   Handles pagination (similar to OHLCV loop).
    *   Returns `List[Dict]` or `pd.DataFrame`.
    *   **Fallback**: If exchange doesn't support it (e.g. Spot), return empty.

### `src/data/fetcher/core.py`
*   **Modify**: `fetch_data`
    *   After fetching OHLCV, attempt to fetch Funding Rates for the same range.
    *   **Merge**: Join Funding Rate on `timestamp`.
    *   **Schema**: Add `fundingRate` column to the Parquet schema.
    *   **Defaults**: Fill `NaN` for spot or missing funding.

## 2. Frontend: Data QC Tab (`src/dashboard/pages/data/qc.py`)

### Features
1.  **Universe Selector**: Pick a saved Universe (JSON) or "All Local Data".
2.  **Heatmap Visualization**:
    *   **X-Axis**: Time (aggregated by Day or Week).
    *   **Y-Axis**: Symbols in Universe.
    *   **Color**:
        *   🟩 Green: 100% Completeness (e.g. 24 hours of data present).
        *   🟨 Yellow: Partial Data (1-23 hours).
        *   🟥 Red: 0 Data (Gap).
3.  **Drill-Down**:
    *   Click/Select a symbol to see a quick line chart of `Close` vs `Funding Rate`.
    *   Show "Gap Report" (list of missing start/end times).

### `src/dashboard/pages/data/layout.py`
*   Add **"QC & Inspection"** tab.

## Verification Plan

### Automated
*   None (No unit tests set up yet).

### Manual Verification
1.  **Funding Rate**:
    *   Go to **Scanner**, fetch `BTC/USDT` from `binanceusdm` (Futures).
    *   Check **QC Tab**: Ensure `fundingRate` column is visible in the drill-down inspector and has values.
2.  **QC Heatmap**:
    *   Create a Universe with `BTC/USDT` and `ETH/USDT`.
    *   Delete the middle month of `ETH/USDT` file (manually or via test script).
    *   Open **QC Tab**: Verify `ETH` shows a <span style="color:red">RED</span> gap in the middle, while `BTC` is <span style="color:green">GREEN</span>.
