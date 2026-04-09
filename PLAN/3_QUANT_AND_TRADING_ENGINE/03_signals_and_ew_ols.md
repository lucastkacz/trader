# V2 Execution Engine: Architecture Blueprint

The Execution Engine is the live 24/7 autonomous component of the platform. Unlike the Universe Screener (which runs passively to calculate structure and build Cohorts), this Engine strictly governs Live Capital. It executes a rigorous continuous cycle, ensuring trades only open under strict, real-time mathematical validation.

---

### Step 1: Manage Active Entanglements (First Priority)
Before looking for new opportunities, the bot queries RAM internal State for all `OPEN` spreads. 
It downloads the freshest 4H candles and updates their real-time Z-Scores.
* **Take Profit:** Has the Spread reverted to the mean (e.g., $Z-Score \approx 0.0$)? If yes, execute immediate dual-leg market closes. Mark DB row as `CLOSED`.
* **Stop Loss:** Has the Spread mathematically broken (e.g., $Z-Score > 4.0$)? If yes, execute immediate Stop Loss procedures.
* **Cost-Benefit Delta Hedging (EW-OLS Drift Shield):** Has the dynamic relationship between the two assets drifted? The Engine recalculates the actual **EW-OLS (Exponentially Weighted OLS)** Beta. For the 4H timeframe, a rigid historical window of ~90 days destroys responsiveness against hacks or sudden fundamental shocks. Using EW-OLS will force the engine to give supreme weight to the directional metrics of the last 48 hours. The engine evaluates if the exact dollar value of the exposed drift risk ($PnL_{drift}$) is mathematically superior to the explicit asymmetric cost of rebalancing (`0.05% Taker Fee`). If $Risk > Cost$, the Beta is immediately re-aligned.


### Step 3: Phase 4 Cointegration Screen (Live Reality)
If the market is safe, the Engine iterates over the Universal Cohorts using the absolute freshest 4H candles.
**The Asymmetry Fix:** The Engle-Granger test is order-dependent ($OLS(A, B) \neq OLS(B, A)$). The engine mathematically mandates running the regression bidirectionally. It selects the direction that generates the lowest ADF P-Value to serve as the Hedge Ratio. If neither direction yields $P-Value < 0.05$, the pair is discarded.
**The Half-Life Filter (Ornstein-Uhlenbeck):** Having cointegration is useless if the reversion cycle is structurally too slow. The engine calculates the mathematical Half-Life of the spread. If $HalfLife > 14\ days$, the engine discards the trade to prevent locking up capital that will be eroded strictly by funding rates while waiting for reversion.


### Step 4: Signal Flagging
For the subset of pairs strictly cointegrated *right now*, calculate the Z-Score spread.
**Dynamic Friction Adjustment:** The standard threshold is $|Z| > 2.0$. However, $2.0$ is useless in tight markets. The engine must dynamically adjust this baseline up by adding the current total Maker/Taker friction loop of the specific pair. If Exchange fees total 0.1%, the required Entry flag mathematically shifts to $2.5$ to guarantee the Expected Value (EV) of the spread survives the literal transaction costs.


### Step 5: Phase 5 EV Mathematical Equation (Funding Direct Discount)
The Funding Rate is no longer a simple passive toxicity filter. It transforms into an explicit, real-time mathematical deduction that annihilates the Expected Return and prevents blindly inefficient limit-chasing. This EV evaluation is categorically injected into the builder agents:
$$EV = S_{proj} - (F_{8H} \times 3 \times D_{est})$$
(Projected Spread Return minus [8H Funding Rate x 3 Cycles x Estimated Hold Days based on Half-Life]).
The engine parametrically discards the operation if this total EV does not comfortably neutralize this Perpetual Friction while also subsidizing the potential "Orphan Taker Penalty" if the Leg B chase aborts at minute 3.
