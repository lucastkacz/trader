# Quant Platform Handover Prompt

**Role & Context:**
You are an expert Quantitative Developer, Data Scientist, and Software Architect. We are currently pair programming to build a sophisticated statistical arbitrage trading platform in Python for a hedge fund. We have separated the architecture into distinct, highly modularized components:
- `data/`: Ingestion, standardizing, and management of historical datasets.
- `strategies/`: Trading logic, configuration, and analysis.
- `engine/`: Execution logic and backtesting framework.
- `dashboard/`: A dynamic Streamlit UI that acts as our primary visual workspace.

**Current Architecture & Accomplishments:**
1. **Data Pipeline & Correlation:** We pull perpetual futures data using `UniverseManager` and `DataLoader`. We have a working *Correlation* dashboard page that applies statistical pre-filtering (Skewness & Kurtosis) and measures multi-asset correlations to output `basket.json` files.
2. **Strategy Factory & Pydantic Configs:** We use a strict architectural pattern anchored by `BaseStrategy`. Recently, we overhauled strategy configurations to strictly enforce **Pydantic Models** (`src/strategies/models.py`). 
   - A strategy's `config.yml` is parsed and strongly typed.
   - We enforce a `Methodology` Enum (`MeanReversionMethod` inside `src/strategies/constants.py`) to categorize all strategies (e.g., `CLASSIC_COINTEGRATION`).
3. **Alpha Discovery (Research):** This is our dynamic, modular Strategy Screener located in `src/dashboard/pages/research/layout.py`.
   - The user selects an input Basket and a target Strategy.
   - The UI intelligently reads the strategy's `Methodology` Pydantic Enum and dynamically generates the required input parameters (e.g., Rolling Windows, thresholds).
   - Upon execution, it renders methodology-specific visualizations. For `CLASSIC_COINTEGRATION`, we implemented a Scatter Plot (OLS Regression) and a Rolling Z-Score Spread chart. These are neatly organized in dedicated folders (`src/dashboard/pages/research/components/`).

**Current Project State:**
- The `Pairs Trading (Classic Cointegration)` strategy is fully implemented and mathematically verified. The Alpha Discovery UI successfully runs it and renders its complex visualizations.
- We have laid the foundation for expanding into other mathematical methodologies, creating empty component sub-folders for `oscillator_divergence`, `kalman_filter`, `dynamic_time_warping`, and `copula_tail_dependence`.

**Next Immediate Objective:**
Our next step is to design the mathematical model, project structure, and implementation plan for the **RSI Divergence Spread** strategy.

We need to:
1. Create its config YAML file (`config.yml`), assigning it the `OSCILLATOR_DIVERGENCE` methodology enum.
2. Implement its class inheriting from `BaseStrategy`, specifically defining the `evaluate()` and `get_screening_metric()` functions to detect divergence between the RSI momentum and price.
3. Wire its specific visual components (e.g., overlapping price and RSI subplot charts) into the empty `oscillator_divergence` UI component folder within Alpha Discovery.

**Given this context, please acknowledge the project's architecture, summarize your understanding of the Pydantic-driven dynamic UI we've built, and provide a detailed Implementation Plan (in markdown codeblocks) outlining how we will build the RSI Divergence Spread strategy.**
