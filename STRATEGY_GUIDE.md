# The Ultimate Pair Trading Strategy Guide

**Welcome.** This document is a comprehensive manual for the **Statistical Arbitrage Pair Trading** strategy. It is designed to take you from zero to understanding the complex mechanics of quantitative trading.

We will cover the **Theory**, the **Math**, and the **Execution** without a single line of code.

---

## 🏗️ 1. The Core Philosophy (The "Big Idea")

Markets are chaotic, but sometimes two assets get tied together by fundamental economic forces (e.g., Bitcoin and a Bitcoin-ETF, or Pepsi and Coke).

### Mean Reversion: The "Rubber Band" Effect
Imagine a rubber band connecting two assets.
*   Most of the time, they move together.
*   Sometimes, panic or greed stretches the rubber band (the price difference widens).
*   **The Bet:** We bet that the rubber band will eventually snap back to its normal size.

### Market Neutrality
We don't care if the market goes Up or Down.
*   We buy the "Cheap" asset.
*   We sell the "Expensive" asset.
*   If the market crashes, our Short position makes money while our Long position loses money. Ideally, they cancel out, leaving us with the profit purely from the **relationship** (the rubber band snapping back).

---

## ⛽ 2. Data: The Fuel

Before we calculate anything, we need raw material. We don't trade on feelings; we trade on data.

*   **The Data:** We use **Perpetual Futures** market data.
*   **The Atom:** A single data point is a "Candle" containing **OHLCV** (Open, High, Low, Close, Volume).
*   **The Pulse:** We check the market every hour ($t \rightarrow 1h$). This balances having enough opportunities with filtering out random noise.

---

## 🔍 3. The Selection Funnel: Finding the Gems

We start with a list of 50+ assets. We can't trade them all. We use a "Funnel" to filter out the noise and find the gold.

### Step A: Correlation (The "Do they dance together?" Test)
First, we check if two assets generally move in the same direction. We look at their **Logarithmic Returns** ($R$), which is just the percentage move from one hour to the next.

**The Math:**
$$ \rho_{A,B} = \frac{\sum (R_A(t) - \bar{R}_A)(R_B(t) - \bar{R}_B)}{\sqrt{\sum (R_A(t) - \bar{R}_A)^2 \sum (R_B(t) - \bar{R}_B)^2}} $$ 

*   **Plain English:** A score of `1.0` means they are identical twins. `0.0` means they are strangers.
*   **The Filter:** We only keep pairs with a score $> 0.70$.

### Step B: Cointegration (The "Drunk Man & Dog" Test)
Correlation isn't enough. Two assets can go up together but drift further and further apart.
**Cointegration** is stronger. It implies a "leash". Even if they wander aimlessly (random walk), the distance between them is bounded.

**The Math (Engle-Granger Method):**
1.  **Find the Ratio:** We try to find a "Hedge Ratio" ($\beta$) that makes the difference between them stable.
    $$ \ln(P_A(t)) = \alpha + \beta \ln(P_B(t)) + \epsilon(t) $$ 
2.  **Test the Leash:** We check the leftovers ($\epsilon(t)$) to see if they stay close to zero or drift away. We use the **Augmented Dickey-Fuller (ADF)** test.
    *   **The Filter:** A p-value $< 0.05$ (We are 95% sure the leash exists).

### Step C: Quality Control
We found a pair with a leash. But is the leash good for trading?

1.  **Half-Life ($\lambda$):** How long does it take for the rubber band to snap back halfway?
    *   *Good:* 6 hours. (Fast money).
    *   *Bad:* 3 weeks. (Capital is stuck).
    *   **The Filter:** Must be $< 48$ hours.
2.  **Hurst Exponent ($H$):** Is the series "Mean Reverting"?
    *   $H < 0.5$: It likes to return to the average (Good).
    *   $H > 0.5$: It likes to trend away (Bad).
    *   **The Filter:** Must be $< 0.5$.

---

## 🔮 4. Bias Mitigation: avoiding the "Crystal Ball"

**The Trap:** If you look at a chart of the last month, find the best pair, and then say "I would have traded this," you are cheating. You used future knowledge to pick the winner. This is called **Lookahead Bias**.

**The Solution:**
We split time into two zones.
1.  **The Lab (In-Sample):** We look at Days 1-14 to find the best pairs.
2.  **The Wild (Out-of-Sample):** We test how those specific pairs performed on Days 15-30.

We *never* let the strategy see tomorrow's newspaper.

---

## 🧠 5. The Brain: Signal Generation

Now we are live. How do we know when to trade?

### 1. The Dynamic Hedge Ratio ($\beta(t)$)
Relationships change. One asset might become more volatile. We re-calculate the "perfect ratio" ($\beta$) every single hour using a rolling window (e.g., the last 14 days).

$$ \beta(t) = \frac{\text{Covariance}(A, B)_{recent}}{\text{Variance}(B)_{recent}} $$ 

### 2. The Spread ($S(t)$)
We calculate the current "distance" between the assets using that fresh ratio.

$$ S(t) = \ln(P_A(t)) - \beta(t) \ln(P_B(t)) $$ 

### 3. The Z-Score ($Z(t)$) — "The Thermometer"
The raw spread number (e.g., "0.005") is confusing. Is that high? Low?
We convert it to a **Z-Score**. This tells us how many "Standard Deviations" we are away from the average.

*   $Z = 0$: Normal.
*   $Z = +2$: Very High (Hot).
*   $Z = -2$: Very Low (Cold).

$$ Z(t) = \frac{S(t) - \text{Average}(S)}{\text{Volatility}(S)} $$ 

### 4. The Rules
*   **Open Trade:** If $Z(t)$ goes above **+2** or below **-2**, the rubber band is stretched. We bet on the snapback.
*   **Take Profit:** If $Z(t)$ returns to **0**, the rubber band is relaxed. We cash out.
*   **Stop Loss:** If $Z(t)$ goes beyond **+4**, the rubber band has snapped (broken). We exit immediately to save our money.

---

## ⚖️ 6. Execution: Balancing the Scales

We don't just put $500 on Asset A and $500 on Asset B. That would be reckless. Asset B might be twice as volatile as Asset A!

**The Formula:**
We weight the trade using the Hedge Ratio ($\beta$) to make it volatility-neutral.
If we have $C$ dollars:

$$ \text{Buy Amount}_A = \frac{C}{P_A + |\beta| P_B} $$ 
$$ \text{Sell Amount}_B = \text{Amount}_A \times |\beta| $$ 

This ensures that if the *whole market* moves up 1%, our Long makes \$X and our Short loses \$X, leaving us flat (protected).

### The "Toll Booths" (Costs)
Real life has friction. We simulate these strictly:
1.  **Fees:** Exchange takes a cut (e.g., 0.05%) every time we touch a button.
2.  **Slippage:** The price moves slightly against us before our order fills.
3.  **Funding:** In crypto, you pay a "rent" every 8 hours to hold a position. Sometimes you pay, sometimes you get paid. We track this hourly.

---

## 📊 7. The Report Card

How do we know if we did well? It's not just about "Total Profit".

*   **Sharpe Ratio:** "Bang for your buck." How much profit did we make per unit of risk? (Higher is better).
*   **Max Drawdown:** "The Pain." What was the worst drop from the peak? (Lower is better).
*   **Win Rate:** How often were we right? (StatArb strategies often have high win rates, > 60%).

---
*Created for the Quant Strategy Project.*