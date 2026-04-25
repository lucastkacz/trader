# V2 Quant Platform: The Python Coding Manifesto

This document serves as the absolute rulebook for the platform's codebase. Every developer, and every AI Agent working on this repository, **MUST** strictly adhere to these principles. The goal is to maintain institutional-grade reliability, readability, and high-frequency performance.

---

## 1. The Vectorization Mandate (The "No Loop" Rule)
Financial data processing in Python is disastrously slow if forced into pure python `for` loops. Time-series data operates in millions of rows.
* **The Absolute Ban:** You are strictly forbidden from using `df.iterrows()`, `df.itertuples()`, or base python `for` loops to iterate over historical prices or technical indicators.
* **The Standard:** Mathematical and statistical logic must rely entirely on **Vectorized Operations** via `pandas` and `numpy`. Use matrix multiplication, native `df.shift()`, `df.rolling()`, and `np.where()` to perform instantaneous bulk-calculations in C-compiled memory.
* **The "Thread Offloading" Law (Async Safety):** The I/O system is asynchronous (`asyncio`/`ccxt`), but Numpy and Pandas are **blocking**. Any mathematical operation lasting >50ms (e.g., `df.corr()` over hundreds of assets) **MUST be delegated to a secondary thread** (using `asyncio.to_thread()` or `run_in_executor`). The main *Event Loop* is reserved EXCLUSIVELY for networking, webhooks, and emergency cancellations. Blocking the thread paralyzes the bot and triggers false disconnection alarms.

---

## 2. Test-Driven Framework (TDD)
A Quantitative bot trading real capital cannot rely on "print debugging".
* **Test Architecture:** The testing suite relies exclusively on `pytest`. Tests must be structured in the `/tests/` directory strictly mirroring the `/src/` paths (e.g., `src/stats/math.py` -> `tests/stats/test_math.py`). 
* **The "Airplane Mode" Rule:** API networks fail. Thus, unit tests must execute cleanly without internet access. All `ccxt` Exchange API calls MUST be perfectly walled off and mocked using `unittest.mock`.
* **Coverage Requirements:** No core mathematical function (e.g., *Engle-Granger*, *Half-life calculations*, *Hedge Ratios*) is allowed to be pushed to the repository without exhaustive test assertions covering edge cases like Division by Zero, `NaN` gaps, and flat lines.

---

## 3. Strict Execution Typing (The Precision Rule)
Code is read orders of magnitude more often than it is written, and Crypto APIs are unforgiving regarding primitive data types.
* **Type Hinting:** Mandatory for ALL function signatures across the repository. (Example: `def fetch_ohlcv(symbol: str, limit: int = 100) -> pd.DataFrame:`).
* **Floating Point Shield:** A primary failure vector in live trading is "Precision Errors" (e.g., sending `1.234567891` lots to an asset that only accepts 4 decimal places). All Python `float` arithmetic must be routed directly through `ccxt.amount_to_precision(symbol, amount)` and `ccxt.price_to_precision(symbol, price)` before generating the final JSON POST payload.
* **Configuration & Secrets Bifurcation:** It is **strictly prohibited** to mix secrets and math in the same file. `config.yml` is reserved ONLY for bot hyperparameters (Limits, windows, VIX thresholds). Credentials (API Keys, Webhooks) MUST be placed in an independent `.env` parsed securely via `pydantic-settings`. All this must be strongly typed before touching the Live Engine.

---

## 4. The Core Tech Stack
Do not reinvent the wheel. The engine relies exclusively on these battle-tested, heavy-duty frameworks to guarantee speed and stability:
1. **Data Ingestion:** `ccxt` (Universal Exchange API async management).
2. **Storage Execution:** `pyarrow` / `parquet` (Gigabyte-scale OHLCV local cache reading relying exclusively on Custom Metadata headers, completely abandoning heavy CSV processing). **Mandate:** Parquet writes MUST be shielded with strongly typed schemas (`pyarrow.schema()`). The bot will crash if it blindly trusts pandas type inference while the Exchange silently alters its payload (e.g., returning strings instead of floats).
3. **Core Mathematics:** `pandas`, `numpy`, and `statsmodels` (Augmented Dickey-Fuller, OLS regression matrixes, Johansen Vectors).
4. **Machine Learning:** `networkx` (For Unsupervised Louvain Community Clustering).
5. **State Auditing:** `loguru` (JSON Lines Dual-Sink architecture).
6. **SQLite Degradation (Append-Only Log):** `active_trades.db` has immediately lost its transactional status and is relegated passively. Using the local DB as a synchronously active manager promotes "Database is Locked" fatalities and thread interference (Main Thread vs Auditor Thread). State routing will happen inside a **Shared Volatile Dictionary in RAM**. SQLite is strictly a silent layer of historical, append-only logging required for retroactive AI Audit joins.
7. **`asyncio` Abstraction Restriction:** Prioritizing *Solopreneur* technical sanity, the use of abstractly complex concurrent paradigms is strictly restricted. Broker transactions must be explicitly routed in a "Sequential Iterative Single-Thread" format. The `asyncio.gather()` method is permitted ONLY when capturing massive static reads against the Binance API to evade REST congestion; when opening or chasing stat-arb legs, sequential execution guarantees traceability.
8. **Workflow Data Orchestrator:** `prefect` (Native Python E2E DAG execution, handling state dependencies and Dirty Runs seamlessly).
9. **Configuration Engine:** `pyyaml` (External strategy blueprint and hyperparameter ingestion to decouple hardcoded script execution flags).

---

## 5. Architectural Boundaries (Separation of Concerns)
To guarantee the system is hyper-scalable, the modules are strictly isolated.
* **The Brain (`src/screener/`, `src/stats/`):** Purely mathematical. These modules must NEVER import an API network library. They accept raw matrices or generic DataFrames, crunch numbers, and return boolean flags or vectors.
* **The Muscle (`src/data/`):** The only system allowed to make I/O internet connections via `ccxt`. It is completely oblivious to trading strategy physics. It only fetches raw candles and saves them to local Parquet nodes.
* **The Spokesperson (`src/core/logger.py`):** The sole entity allowed to write out to the console or disk. The usage of the base `print()` function is globally and permanently banned.

---

## 6. The Agnostic Architecture Mandate
The quantitative framework must be completely oblivious to specific configurations and parameters. The engine relies on the user's YAML files as the **Absolute Single Source of Truth**.
* **Strict Dictionary Lookups (The "No Default" Rule):** The usage of `.get("key", default_value)` is permanently banned across the entire codebase. Configurations must be strictly parsed via `cfg["key"]`. If the user omits a vital execution parameter in their YAML, the bot **MUST explicitly crash on boot** with a `KeyError`. Silent fallbacks cause catastrophic logical errors in live execution.
* **Timeframe Oblivion:** The codebase is forbidden from making assumptions about timeframes (e.g., `if timeframe == '3h'` or `BARS_PER_DAY = 6`). All timeframe-related operations must mathematically deduce the number of bars dynamically utilizing centralized agnostic utility modules (e.g., parsing `'15m'` or `'4h'` strictly). 
* **Eradication of 'Days':** The core live trading loop and mathematics operate on the purest raw metric: **"Bars"**. All execution loops must refer to `lookback_bars` rather than `lookback_days` to prevent calculation mismatch across disparate timeframe environments.
