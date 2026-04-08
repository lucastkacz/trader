# V2 Portfolio & Risk Management

A robust Statistical Arbitrage engine never executes trades in a vacuum. A trade is only as valid as the Portfolio that sustains it. This architectural document outlines the strict global Risk constraints required to survive Black Swan events and optimize capital efficiency.

## 1. Modular Position Sizing (The Allocation Engine)

The system will decouple capital allocation from the signal generation logic. It will support a **Dynamic Configuration Toggle**, allowing the User to seamlessly switch between two institutional strategies without rewriting core logic:

#
## Mode A: Uniform Fixed Sizing (Simple Base)
* **Logic:** Every single Spread spawned by the execution engine receives exactly identical `USDT` baseline exposure, regardless of the underlying token's behavior. (e.g., Every spread gets tightly $1000 Total Capital).
* **Use Case:** Excellent for beta-testing a fresh architecture because it guarantees PnL is highly readable and directly mirrors the Win/Loss accuracy of the Cointegration models without volatility skewing the analysis.

#