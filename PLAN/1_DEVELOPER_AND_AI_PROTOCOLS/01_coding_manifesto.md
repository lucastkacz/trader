# V2 Quant Platform: The Python Coding Manifesto

This document serves as the absolute rulebook for the platform's codebase. Every developer, and every AI Agent working on this repository, **MUST** strictly adhere to these principles. The goal is to maintain institutional-grade reliability, readability, and high-frequency performance.

---

## 1. The Vectorization Mandate (The "No Loop" Rule)
Financial data processing in Python is disastrously slow if forced into pure python `for` loops. Time-series data operates in millions of rows.
* **The Absolute Ban:** You are strictly forbidden from using `df.iterrows()`, `df.itertuples()`, or base python `for` loops to iterate over historical prices or technical indicators.
* **The Standard:** Mathematical and statistical logic must rely entirely on **Vectorized Operations** via `pandas` and `numpy`. Use matrix multiplication, native `df.shift()`, `df.rolling()`, and `np.where()` to perform instantaneous bulk-calculations in C-compiled memory.
* **La Ley del "Thread Offloading" (Async Safety):** El sistema I/O es asíncrono (`asyncio`/`ccxt`), pero Numpy y Pandas son **bloqueantes**. Cualquier operación matemática que dure >50ms (ej. `df.corr()` sobre cientos de activos) **DEBE ser delegada a un hilo secundario** (usando `asyncio.to_thread()` o `run_in_executor`). El *Event Loop* principal queda EXCLUSIVAMENTE liberado para red, webhooks y cancelaciones de emergencia. Bloquear el hilo paraliza el bot y dispara falsas alarmas de desconexión.

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
* **Bifurcación de Configuración & Secretos:** Está **terminantemente prohibido** mezclar secretos y matemática en un mismo archivo. `config.yml` se reserva ÚNICAMENTE para hiperparámetros del bot (Limits, ventanas, VIX thresholds). Las credenciales (API Keys, Webhooks) DEBEN ir en un `.env` independiente cargado con `pydantic-settings`. Todo esto debe ser parseado fuertemente antes de tocar el Engine Live.

---

## 4. The Core Tech Stack
Do not reinvent the wheel. The engine relies exclusively on these battle-tested, heavy-duty frameworks to guarantee speed and stability:
1. **Data Ingestion:** `ccxt` (Universal Exchange API async management).
2. **Storage Execution:** `pyarrow` / `parquet` (Gigabyte-scale OHLCV local cache reading relying exclusively on Custom Metadata headers, completely abandoning heavy CSV processing). **Mandato:** Las escrituras en Parquet DEBEN blindarse con esquemas (`pyarrow.schema()`) fuertemente tipados. El bot crasheará si confía ciegamente en la inferencia de tipos de pandas y el Exchange altera silenciosamente su payload (ej. regresando strings en lugar de floats).
3. **Core Mathematics:** `pandas`, `numpy`, and `statsmodels` (Augmented Dickey-Fuller, OLS regression matrixes, Johansen Vectors).
4. **Machine Learning:** `networkx` (For Unsupervised Louvain Community Clustering).
5. **State Auditing:** `loguru` (JSON Lines Dual-Sink architecture).
6. **State Management (ORM):** `SQLAlchemy` apoyado estrictamente en **`aiosqlite`**. (Raw SQL strings are strictly prohibited). El motor de base de datos DEBE ser asíncrono (`sqlite+aiosqlite://`). Usar un driver síncrono bloquearía el hilo principal durante las lecturas escrituras masivas a `active_trades.db`, paralizando el sistema y disparando cancelaciones de red.

---

## 5. Architectural Boundaries (Separation of Concerns)
To guarantee the system is hyper-scalable, the modules are strictly isolated.
* **The Brain (`src/screener/`, `src/stats/`):** Purely mathematical. These modules must NEVER import an API network library. They accept raw matrices or generic DataFrames, crunch numbers, and return boolean flags or vectors.
* **The Muscle (`src/data/`):** The only system allowed to make I/O internet connections via `ccxt`. It is completely oblivious to trading strategy physics. It only fetches raw candles and saves them to local Parquet nodes.
* **The Spokesperson (`src/core/logger.py`):** The sole entity allowed to write out to the console or disk. The usage of the base `print()` function is globally and permanently banned.
