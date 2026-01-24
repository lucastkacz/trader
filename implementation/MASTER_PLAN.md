# Master Plan: StatArb Research & Validation System

> **Goal**: Develop a professional-grade, local research environment for statistical arbitrage strategies on crypto. Focus on rigorous statistical validation, scalability, and "visual validation" through a central dashboard.

## 1. Executive Summary & Code Review
Based on the review of the current `src/statarb` codebase:
*   **Architecture**: The **Modular Monolith** structure is excellent. The separation of `infra` (Parquet/DuckDB) from `domain` (Candle models) is clean and professional. It follows best practices for Domain-Driven Design (DDD).
*   **Scalability**: The "Lakehouse" approach using Hive-partitioned Parquet files (`exchange=*/timeframe=*/symbol=*`) managed by DuckDB is **highly scalable**. It allows for efficient querying of specific time ranges and symbols without loading the entire dataset.
*   **Code Quality**: The code uses modern Python features (Pydantic, Type Hinting, Pathlib). It is production-ready.
*   **Verdict**: The foundation is solid. We do not need to rebuild the data layer. We can build the **Backtesting** and **Validation** layers directly on top of `src/statarb/infra/lakehouse`.

## 2. Philosophy: "Bite-Sized" & Rigorous
We will avoid "big crunch" development. Every step must be:
1.  **Small**: Implementable in 1-2 coding sessions.
2.  **Testable**: Verifiable via unit tests or visual output.
3.  **Rigorous**: No "trust me" logic. Everything is backed by statistics.

## 3. High-Level Roadmap

### [Phase 1: The Vectorized Backtester](implementation/PHASE_1_BACKTESTING.md)
**Goal**: Create a fast, efficient engine to simulate trading strategies on historical data.
*   **Focus**: Event-driven vs Vectorized (we start with Vectorized for research speed), Latency simulation, Fee modeling.
*   **Output**: A `BacktestResult` object containing equity curves and trade logs.

### [Phase 2: Statistical Validation & Rigor](implementation/PHASE_2_VALIDATION.md)
**Goal**: Ensure strategies are not overfit.
*   **Focus**: Walk-Forward optimization, K-Fold Cross Validation (purged), Monte Carlo Permutation tests.
*   **Output**: A "Pass/Fail" report for any given strategy.

### [Phase 3: The "Central Hub" Dashboard](implementation/PHASE_3_DASHBOARD.md)
**Goal**: Visual verification of data and strategies.
*   **Focus**: Data Lake health, Strategy Performance visualization, Trade-by-trade inspection.
*   **Tech**: Streamlit or Dash (Python-based, no complex frontend needed).

---

## 4. Daily Workflow Definition
To maintain momentum, your "Day" should check these boxes:

### Morning: Review & Plan
*   Check the **Dashboard**: Is the Data Lake healthy? Are there gaps in the data?
*   Review `task.md`: What is the single bite-sized chunk for today?

### Mid-Day: Implementation (Deep Work)
*   **TDD First**: Write the test for the feature (e.g., "Test that backtester deducts 0.1% fee correctly").
*   Implement the logic in `src/statarb`.
*   Run the specific test.

### Evening: Validation & Committal
*   Run the full test suite.
*   Update the **Implementation Log** (a simple markdown file tracking decisions).
*   Commit to git.

## 5. Next Immediate Step
Go to **[Phase 1: Backtesting](implementation/PHASE_1_BACKTESTING.md)** to start building the simulation engine.
