# Feature Design: Asset Universes

## Goal
To allow the creation of **"Universes"** of assets. A Universe is a **Configuration** that defines a specific set of assets, a timeframe, and a date range, ensuring they are valid for backtesting without duplicating the underlying data.

## Data Structure: The Universe Config

Instead of a massive Parquet file, a Universe is a lightweight **JSON** file stored in `data/universes/`.

**Example: `data/universes/DeFi_Bluechips_2023.json`**
```json
{
  "name": "DeFi_Bluechips_2023",
  "description": "Top DeFi tokens by volume in 2023",
  "timeframe": "1h",
  "data_source": "binance",
  "range": {
    "start": "2023-01-01 00:00:00",
    "end": "2023-12-31 23:00:00"
  },
  "symbols": [
    "AAVE/USDT",
    "UNI/USDT",
    "MKR/USDT",
    "SNX/USDT",
    "COMP/USDT"
  ],
  "alignment_check": "passed", // Metadata to confirm we verified this at creation
  "created_at": "2024-05-20 10:00:00"
}
```

### Advantages
1.  **Zero Duplication**: Uses the existing `data/binance/1h/*.parquet` files.
2.  **Flexibility**: Easy to edit JSON to add/remove a pair.
3.  **Speed**: Creating a universe is instant (just validating existence).

## Workflow Integration

### 1. Dashboard Refactor
The `data_page.py` file is too large. We will split it:
*   `src/dashboard/pages/data/layout.py` (Main entry point)
*   `src/dashboard/pages/data/downloader.py` (Tab 1: Single Fetch)
*   `src/dashboard/pages/data/scanner.py` (Tab 2: Batch Fetch)
*   `src/dashboard/pages/data/universe.py` (Tab 3: Universe Management)

### 2. Market Scanner Integration (The "Fast Track")
The **Market Scanner** already fetches a batch of valid, aligned data.
*   **Action**: After a successful "Batch Fetch" in the Scanner tab, add a **"Save as Universe"** button.
*   **Logic**: Since we just fetched them with the *same* start/end/timeframe, they are guaranteed to be a valid universe. We just write the JSON.

### 3. Universe Manager (New Tab)
*   **Create Manually**: Select from list of *all* downloaded files (filtered by timeframe).
*   **Load**: View details of an existing Universe.
*   **Validate**: A button to "Check Alignment" (opens all files and checks if they still cover the range).

## Engine Interaction
The `Loader` needs a new method:
```python
def load_universe(universe_name: str):
    config = read_json(f"data/universes/{universe_name}.json")
    # Uses existing load_data logic but restricted to the config's symbols and range
    return load_data(config['symbols'], config['timeframe'], config['range'])
```
