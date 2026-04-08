# V2 Execution Engine: Architecture Blueprint

The Execution Engine is the live 24/7 autonomous component of the platform. Unlike the Universe Screener (which runs passively to calculate structure and build Cohorts), this Engine strictly governs Live Capital. It executes a rigorous continuous cycle, ensuring trades only open under strict, real-time mathematical validation.

---

### Step 1: Manage Active Entanglements (First Priority)
Before looking for new opportunities, the bot queries SQLite for all `OPEN` spreads. 
It downloads the freshest 4H candles and updates their real-time Z-Scores.
* **Take Profit:** Has the Spread reverted to the mean (e.g., $Z-Score \approx 0.0$)? If yes, execute immediate dual-leg market closes. Mark DB row as `CLOSED`.
* **Stop Loss:** Has the Spread mathematically broken (e.g., $Z-Score > 4.0$)? If yes, execute immediate Stop Loss procedures.
* **Cost-Benefit Delta Hedging (EW-OLS Drift Shield):** Has the dynamic relationship between the two assets drifted? The Engine recalculates the actual **EW-OLS (Exponentially Weighted OLS)** Beta. Para la temporalidad 4H, la ventana rígida histórica de $\approx 90$ días anula la velocidad de respuesta frente a hackeos o shocks fundamentales repentinos. El uso de EW-OLS obligará al motor a darle peso supremo a las métricas direccionales de las últimas 48 horas. El motor evalúa si el dólar del riesgo descubierto ($PnL_{drift}$) es matemáticamente superior al costo asimétrico de rebalanceo (`0.05% Taker Fee`). Si $Risk > Cost$, se rebalancea la Beta inmediatamente.


### Step 3: Phase 4 Cointegration Screen (Live Reality)
If the market is safe, the Engine iterates over the Universal Cohorts using the absolute freshest 4H candles.
**The Asymmetry Fix:** The Engle-Granger test is order-dependent ($OLS(A, B) \neq OLS(B, A)$). The engine mathematically mandates running the regression bidirectionally. It selects the direction that generates the lowest ADF P-Value to serve as the Hedge Ratio. If neither direction yields $P-Value < 0.05$, the pair is discarded.
**The Half-Life Filter (Ornstein-Uhlenbeck):** Having cointegration is useless if the reversion cycle is structurally too slow. The engine calculates the mathematical Half-Life of the spread. If $HalfLife > 14\ days$, the engine discards the trade to prevent locking up capital that will be eroded strictly by funding rates while waiting for reversion.


### Step 4: Signal Flagging
For the subset of pairs strictly cointegrated *right now*, calculate the Z-Score spread.
**Dynamic Friction Adjustment:** The standard threshold is $|Z| > 2.0$. However, $2.0$ is useless in tight markets. The engine must dynamically adjust this baseline up by adding the current total Maker/Taker friction loop of the specific pair. If Exchange fees total 0.1%, the required Entry flag mathematically shifts to $2.5$ to guarantee the Expected Value (EV) of the spread survives the literal transaction costs.


### Step 5: Phase 5 Sieve (Mean-Reverting Funding)
For flagged targets, query live Perpetual 8-hour Funding Rates. 
The algorithm does NOT assume static, linear funding costs extrapolated out 7-days (which rejects highly profitable setups). Instead, it evaluates the **Funding Z-Score**. If current funding is at historical extremes (which often drives the asset's price divergence), the math assumes the funding rate itself will mean-revert rapidly. It only rejects the entry if the structural, historical baseline funding is overwhelmingly toxic.
