# V2 Backtesting Engine: The Time Machine

Before a single dollar is deployed in the Live `03_execution_engine`, the statistical theories constructed in `01` (Universe) and `03` (Live Cointegration) must be rigorously simulated against historical data. 

A backtester is a time machine. If it possesses "Look-Ahead Bias" (accidentally peeking at the next candle to make decisions today), the simulation is poison. This document defines the strict constraints for the Historical Simulator to guarantee that historical Sharpe Ratios perfectly mirror future Live Performance.

---

## 2. Dynamic Transaction Cost Modelling (Friction)
A mathematically perfect strategy on paper often loses 90% of its Edge to the Exchange in reality. The backtester must mathematically simulate brutal friction. Every simulated Spread must deduct:
* **Taker Fees:** `~0.05%` subtracted on every emergency Market execution entry or stop-loss.
* **Maker Fees:** `~0.02%` subtracted on Limit Order take-profits.
* **Quadratic Slippage Impact:** A static `0.05%` slip is a lie that hides scale. The backtester enforces an asymmetric Liquidity Impact model: $Impact = Volatility \times \sqrt{Position Size / ADV}$. Simulating a $50,000 dump on a memecoin will inflict cataclysmic mathematical friction, completely destroying false high-Sharpe strategies.
* **Empirical Funding Series (Time-in-Market Priority):** Extrapolating proxy funding ignores compounding tail risks. The Simulator MUST download the true chronological Binance 8H Historical Funding Rate database and merge it as a parallel temporal array.
    * **Penalización por Estancia Prolongada:** Dado el entorno de Arbitraje de 4H (con lapsos de estancamiento del capital por 5 a 12 días continuos), sostener deudas en posiciones `Short` contra rallys alcistas disolverá secretamente las ganancias (`~0.05%` de tributo por cada límite de 8H atravesado). El backtester tiene mandato directo de cobrar sistemáticamente las tasas de fondeo de acuerdo a su *Time-in-Market*. Si el simulador descarta penalizar los peajes del financiamiento en largos recorridos temporales, quedará inválido por inyectar retornos empíricamente falsos e ilusorios.

---

