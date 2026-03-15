# Quant Project AI Mandates

## 1. Project Overview
This is a quantitative trading research and execution platform. It consists of a backtesting/execution engine, statistical analysis modules, and a web-based dashboard for visualizing strategies.

## 2. Tech Stack & Libraries
- **Frontend/Dashboard:** `streamlit` (UI and Visualization).
- **Data & Math:** `pandas`, `numpy`, and `statsmodels`. Avoid base Python loops for data crunching.
- **Configuration & Validation:** `pydantic` and YAML files.
- **Testing:** `pytest`.

## 3. Architectural Boundaries (Strict MVC & Modularity)
We adhere to a professional, modular architecture strictly separating data, logic, and presentation.
- **Model / Core Logic:** Heavy mathematical calculations, engine execution, and state management must reside in core files (e.g., `strategy.py`, `weighting.py`, `src/engine/`).
- **View / UI Components (`components/`):** Files rendering the UI (Streamlit, Plotly) MUST be "dumb" components. They should strictly accept pre-calculated dataframes/results as arguments and render pixels. NEVER execute core engine runs or heavy mathematical transformations inside UI components.
- `src/dashboard/`: Strictly UI orchestration and layout. No complex data fetching or statistical heavy lifting.
- `src/engine/`: Core logic for backtesting, data loading, and execution. Must be completely decoupled from the UI.
- `src/stats/`: Pure, stateless mathematical and statistical functions (e.g., z-score, hedge ratios, ADF tests).
- `src/strategies/`: Concrete implementations of trading logic inheriting from `BaseStrategy`. Must act as the Controller/Orchestrator for their specific domain, managing the flow between their core math modules and their dumb UI components.
- `src/data/`: Modules responsible for raw data fetching, storage, and caching.

## 4. Coding Conventions
- **Module Documentation (Mandatory):** EVERY major directory or complex module (e.g., inside `src/strategies/` or `src/engine/`) MUST have its own local `README.md` file explaining its domain-specific logic. Read these files before modifying the code within them.
- **AI-Friendly Code (Commenting):** Write explicit, context-rich inline comments explaining the *intent* and *business logic* behind complex mathematical or architectural blocks. This ensures AI agents (like me) can instantly understand the system design without needing to reverse-engineer formulas or guess intentions.
- **Type Hinting:** Mandatory for all function signatures, especially in `src/engine/`, `src/stats/`, and `src/strategies/`.
- **Docstrings:** Use Google-style docstrings for all classes and public methods.
- **OOP & Contracts:** Strategies must inherit from the Abstract Base Class (`BaseStrategy`) and adhere to the established validation patterns (like Pydantic config parsing).

## 5. AI Workflow & Git Rules
- **Context Initialization:** When starting a new chat session, ALWAYS run `git log main -n 10` (or similar) to read recent commit history from the `main` branch to better understand the current context and recent progress.
- **Branching:** If it appears we are starting work on a new feature, proactively suggest creating a new Git branch before writing any code.
- **Committing:** When a feature or fix is successfully implemented, explicitly ask the user for feedback to confirm completion. Once confirmed, automatically prepare and commit the changes using a very detailed, meaningful, and well-structured commit message.
- **Testing First:** When modifying core logic (`src/engine/`, `src/stats/`, or `src/strategies/`), run `pytest tests/` before finalizing the change.
- **Dependencies:** Never add a new pip package without explicitly asking first.
- **No Mocking Data for Tests:** If a test fails because of missing data, flag it so the data can be downloaded. Do not generate synthetic price data to force a test to pass unless specifically instructed.
