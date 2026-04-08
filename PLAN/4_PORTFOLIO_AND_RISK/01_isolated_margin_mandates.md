# V2 Portfolio & Risk Management

A robust Statistical Arbitrage engine never executes trades in a vacuum. A trade is only as valid as the Portfolio that sustains it. This architectural document outlines the strict global Risk constraints required to survive Black Swan events and optimize capital efficiency.

## Mode B: Volatility-Weighted Sizing (Risk Parity)
* **Logic:** Position sizing is distributed inversely proportional to the asset's trailing volatility (ATR). A highly stable pair like `LINK/USDT` might receive $2500 exposure, while a violent, wildly fluctuating meme-pair like `PEPE/USDT` receives only $400 exposure.
* **Use Case:** The target endpoint for production scaling. It guarantees that a 10% daily swing on `PEPE` has the exact same dollar-impact on your total equity curve as a 2% daily swing on `LINK`. The portfolio achieves true balance.

---

