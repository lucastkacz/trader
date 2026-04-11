# Road to Production: Epochs and Timelines

The software architecture is complete (Phases 1 through 6). However, algorithmic trading requires a rigid pipeline to transition from code to autonomous physical capital allocation.

This infrastructure must undergo **Four Development Epochs** to neutralize hallucinated profitability and guarantee baseline robustness against live order-book latency.

---

## Epoch 1: Historical Alpha Discovery (The Data Mine)
*Objective: Build the master universe configuration without touching capital.*

1. **Mass Data Ingestion:** Utilize the Phase 2 `fetcher` to download the entirety of Binance's USD-M perpetuals landscape. 
   - **Mandate:** Strictly 4H (Four-Hour) candles. This honors the macro-thesis of holding periods ranging from days to weeks, neutralizing HFT market noise and compressing Parquet storage overhead.
2. **The Great Filtering:** Propagate the Parquet data into the Phase 3 `screener`. Calculate NetworkX clusters.
3. **Cointegration Baseline:** Evaluate the clusters through the Phase 4 `Alpha Core` to discover historical stationary tethers.

## Epoch 2: Vectorized Optimization (The Stress Test)
*Objective: Subject the discovered pairs to the absolute worst-case friction scenarios.*

1. **Vectorized Execution:** We process the surviving pairs inside the `Phase 5 Arena` (Vectorized Engine) and `Phase 6 Risk Vault`.
2. **Pessimism Filter:** The simulator will force extreme slippage (buying Highs, selling Lows) and continuous 8H Funding Rate penalties. If the Equity Curve generated natively collapses below $0$, the configuration is incinerated.
3. **Hyperparameter Grid:** Iteratively test parameter boundaries:
   - `Z-Score Entries`: [1.5, 2.0, 2.5]
   - `Half-Life Limits`: [7, 14, 21 Days]

## Epoch 3: The Stateful Paper-Tracer (Forward Testing / Ghost Trading)
*Objective: Leave the historical realm and prove profitability against the present future.*

1. **Chronological Trigger:** Develop an asynchronous `orchestrator.py` that wakes up strictly every 4 Hours (aligned chronologically with the 4H closures of Binance APIs).
2. **State Reconciliation Execution:** Generate signals from live CCXT payloads, but route order executions into a local SQLite `/trades.db`. 
3. **Quarantine Duration:** Let this process run uninterrupted on a cloud VPS for a minimum of **3 to 4 Weeks**. This timeframe guarantees the bot encounters multiple structural changes in Funding Rate cycles and weekend illiquidity. Compare theoretical Sandbox EV vs Live Ghost EV.

## Epoch 4: Institutional Dry-Run (Skin in the Game)
*Objective: Test the physical latency, Limit Maker order routing, and API limits.*

1. **Isolation Mandate:** Open an explicitly segregated Binance API sub-account. Cap the wallet transfer to a hyper-conservative disposable amount (e.g., $100 to $500).
2. **Live Insertion:** Activate the live CCXT wrappers for programmatic ordering. Monitor the exact deviations between the Ghost Database slippage and the Real Order Book physical execution. 
3. **Maturity:** If the bot physically survives without crashing the Isolated Margin and correctly maintains spread balance for 30 days, the Engine is fully certified for real portfolio capital injection.
