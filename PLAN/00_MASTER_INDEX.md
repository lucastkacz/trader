# V2 PLAN MASTER INDEX

This file is the **Root Directory** for the architectural planning of the Phase 2 Statistical Arbitrage Engine.
The monolithic documents have been fragmented into 5 single-responsibility domains to ensure that Agents and Developers do not suffer from cross-contamination of instructions.

Any Bot or Developer entering the system must consult this index to find the rules pertinent to their specialty.

---

## 📂 1_DEVELOPER_AND_AI_PROTOCOLS/
*Foundation rules for Autonomous Agents (Cursor, Aider, Gemini) and technological restrictions.*
- `01_coding_manifesto.md` -> Strict vectorization, PyArrow Schema guards, asynchronous SQLite/RAM logic.
- `02_llm_system_prompts.md` -> Anti-Hallucination rules, network Rate Limits, and Human Interaction.
- `03_tdd_and_testing_rules.md` -> Forced network isolation, CCXT mocking, and TDD flow.
- `04_construction_phases.md` -> Strict Order Sequence from Base Logger to Reconciliation Auditor.

## 📂 2_SYSTEM_INFRASTRUCTURE/
*Transactional structural plumbing ensuring 24/7 survival.*
- `01_dual_sink_logging.md` -> Structured Jsonlines in Loguru, OOM queues, and drainage `.complete()`.
- `02_state_reconciliation_auditor.md` -> The 10-minute Cronjob, Ghost/Desertion Tracker, and the Amnesia/Blackout Protocol logic.

## 📂 3_QUANT_AND_TRADING_ENGINE/
*Mathematical Generation and Execution of Production-Grade orders.*
- `01_universe_and_clustering.md` -> Volume Sieves, 180-day Data Maturity, and Louvain Graph Clustering pipelines.
- `02_execution_loop.md` -> The foundational 4H cron cycle, passive API Delays, and the VIX Master Switch (Panic Protection).
- `03_signals_and_ew_ols.md` -> The quantitative layer (Phases 4 & 5): Expected Value (EV) formal equation, Exponentially Weighted OLS Deviation, Hedge Ratios, and O-U filters.
- `04_twap_and_order_routing.md` -> Atomic 4H Surgical Protocol: "Limit Maker Chasing" at the 00:05 mark, and Slippage Tolerance Abort rules (180s TTL).

## 📂 4_PORTFOLIO_AND_RISK/
*Real capital firewalls.*
- `01_isolated_margin_mandates.md` -> Strict prohibition of Cross Margin, and the absolute Isolated Margin limit to survive systemic collapses.
- `02_capital_exposure_limits.md` -> Volumetric rules, proportional scaling, and Sector Bias interruption via "Clustering".

## 📂 5_BACKTESTING_SIMULATION/
*Simulated Reality Engine rules.*
- `01_vectorized_simulation.md` -> Exhaustive prohibition of look-ahead bias via "T+1m" and absolute High/Low pessimistic execution masking.
- `02_friction_and_funding_penalties.md` -> Quadratic transactional costs and Funding deduction to heavily penalize illusory projections.
