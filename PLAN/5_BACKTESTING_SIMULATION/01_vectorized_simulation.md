# V2 Backtesting Engine: The Time Machine

Before a single dollar is deployed in the Live `03_execution_engine`, the statistical theories constructed in `01` (Universe) and `03` (Live Cointegration) must be rigorously simulated against historical data. 

A backtester is a time machine. If it possesses "Look-Ahead Bias" (accidentally peeking at the next candle to make decisions today), the simulation is poison. This document defines the strict constraints for the Historical Simulator to guarantee that historical Sharpe Ratios perfectly mirror future Live Performance.

---

## 1. Vectorized Simulation Mandate (No Event-Loops)
The backtester is absolutely prohibited from using event-driven `for` loops (e.g., iterating chronologically candle by candle). Iterating through 4 years of 4-hour candles for 150 assets takes hours.
The engine must be **100% Vectorized** using pandas arrays (taking seconds):
1. **The VWAP Pricing Mandate:** Operating on the naked `close` price of a 4H candle exposes the backtest to extreme Adverse Selection. The Z-Score math MUST be calculated using a 5-minute Time/Volume Weighted Average Price (TWAP/VWAP) aggregated at the 4H boundary.
2. **Z-Score Generation:** Calculate Rolling Mean, STDEV, and Z-Scores across the VWAP array simultaneously using `.rolling()`.
3. **Boolean Masking:** Generate entry signals (`+1`, `-1`, or `0`) instantly for the entire matrix.
4. **The "T+1m" Latency Barrier (No Time Travel):** We eradicate the naive `signals = signals.shift(1)` logic (which forces execution 4-Hours late). Instead, signals are evaluated strictly on the $T$ 4H boundary. To simulate API Latency, the system merges a High-Frequency 1-minute DataFrame. The simulation calculates explicit Entry PnL using the exact $OPEN$ / $VWAP$ of the $T+1m$ candle. This flawlessly mimics the "5-second delayed" execution reality of the live bot.

---


## 3. The Output Topology (Tearsheet)
The simulator will not just print out "Total Expected Profit". It must generate an institutional Tearsheet:
- **Maximum Drawdown (Max DD):** If the historical simulation experienced a `> 40%` peak-to-trough drop, the strategy is discarded regardless of end profit.
- **Sharpe Ratio & Sortino Ratio:** To evaluate risk-adjusted returns compared to simply buying and holding Bitcoin.
- **Win Rate & Profit Factor:** Ratio of Gross Profits over Gross Losses.
- **Capital Hostage Time:** How many total days the capital was held hostage inside spreads awaiting mean reversion.
