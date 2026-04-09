# V2 LLM Agent Protocol: The Orchestrator

This document is the **Agent's Instruction Manual**. Any LLM (Cursor, Aider, Devin, or custom agents) assigned to building this repository **MUST** read this file before writing a single line of code. Its objective is to prevent hallucinations, spaghetti code, and architectural degradation of the V2 system.

---

## 1. The Atomic Construction Sequence

It is strictly forbidden to program multiple modules in parallel. Development must follow this linear and foundational order, isolating each phase in its own tested PR/Commit before advancing to the next.

*   **Phase 1: Central Infrastructure (The Base Brain)**
    *   Set up the virtual environment and standardized base dependencies.
    *   Write `src/core/logger.py` implementing Loguru standardization (Sinks, `enqueue=True`, `diagnose=False`, `.bind()` mandate).
    *   Write configuration infrastructure (bifurcation `.env` with Pydantic-Settings and `config.yml`).
*   **Phase 2: The Isolated Muscle (Data and Network Access)**
    *   Write CCXT wrappers (`src/data/fetcher/`).
    *   Implement the Parquet/PyArrow storage manager with metadata injection (`src/data/storage/`).
    *   *Rule:* This is the only phase that interacts with the internet. `unittest.mock` must be used for testing.
*   **Phase 3: The Universe Pipeline (Pure Mathematics)**
    *   Implement `src/screener/` step by step (Global Switch, Volume Sieve, Data Maturity, Clustering, Cointegration Mesh).
    *   *Rule:* No `ccxt` imports are allowed here. All DataFrame/Numpy math taking >50ms must use secondary thread delegation.
*   **Phase 4: Transactional State Architecture**
    *   Setup SQLAlchemy and SQLite (`active_trades.db`) passively. *Note*: Database is relegated to an Append-Only Log to prevent DB locks. Live State will be managed by a volatile dictionary in RAM.
    *   Write ORM models that will passively record history.
*   **Phase 5: The 24/7 Execution Engine**
    *   Write the async loop and the Limit Maker Chasing protocols (`src/engine/`).
    *   *Re-entrancy Rule:* The Engine MUST implement an `asyncio.Lock()` (or Global State Mutex) if routing asynchronously. Ensure the 00:05 offset Loop never overlaps concurrently with subsequent ticks.
*   **Phase 6: The Cryptographic Auditor (State Reconciliation)**
    *   Build the async, independent cronjob that resolves discrepancies (Ghost/Desertion Positions) and manages the Blackout Amnesia "Join" recovery protocol.
