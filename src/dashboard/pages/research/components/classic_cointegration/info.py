import streamlit as st

def render_methodology_info(window: int = None, timeframe: str = None):
    window_text = f" (calculated over our **{window}-period Evaluation/Lookback Window** of {timeframe} data)" if window and timeframe else ""
    with st.expander("📚 Methodology Details: Classic Cointegration (OLS) - A Complete Guide"):
        st.markdown(r"""
### 📊 The Ultimate Guide to Classic Cointegration (Pairs Trading)

Welcome to the **Statistical Arbitrage** engine base. This specific strategy profits when two historically correlated assets temporarily "break" their relationship, betting that they will eventually snap back together like a rubber band.

We use two distinct charts, and **you need both to trade safely**:
1. **Scatter Plot (OLS)** tells you **HOW MUCH** to buy/sell (Position Sizing & Hedge Ratio).
2. **Z-Score Spread** tells you **WHEN** to buy/sell (The Trading Signal).

---

#### 1. The Scatter Plot (Getting your Hedge Ratio)
This chart plots Asset A's price on the X-axis against Asset B's price on the Y-axis. 
The straight line cutting through the dots is the **Regression Line (OLS)**.

*   **The Math:** $ y_t = \beta x_t + \alpha + \epsilon_t $
*   **The "Slope" ($\beta$) is your Hedge Ratio:** Look below the Scatter chart for the value of $\beta$. 
    *   *Dummy Example:* If $ \beta = 0.5 $, it means Asset B moves exactly half as fast as Asset A. 
    *   *How to use it:* If our signal tells us to **Buy 1 unit of Asset A**, to stay market-neutral (hedged against a market crash), we must **Short 0.5 units of Asset B**. If you ignore the Hedge Ratio and short 1 unit of Asset B, you are taking a massive directional risk!

#### 2. The Dickey-Fuller Test (P-Value)
Even if the Scatter plot forms a beautiful diagonal line, it only proves *Correlation* (they move together). It does **not** prove *Cointegration* (that they bounce back when they separate). For that, we use the Augmented Dickey-Fuller test on the distance between the dots and the line.
*   **P-Value $\le$ 0.05**: Excellent! Like a rubber band, when the assets separate, mathematical forces pull them back together. 
*   **P-Value $\ge$ 0.05 (e.g., 0.89)**: Terrible! This is a "Random Walk". If the assets separate, they might float away from each other forever. Do not trade this pair.

#### 3. The Z-Score Spread (Getting your Trading Signal)
Once we confirm a low P-Value""" + window_text + r""", we track the "Spread" over time. The Spread is just the distance between the two assets on a given day.
To make it readable regardless of the crypto's price, we convert the spread into a **Z-Score** (Standard Deviations away from the mean).

*   **The Center Line (0):** The assets are perfectly balanced. Hold no position.
*   **The Red Upper Band (+2.0):** The Spread is "too high". Asset A got overly expensive compared to Asset B.
    *   *Action:* **Short the Spread**. (Sell Asset A, Buy Asset B according to your $\beta$ Hedge Ratio).
*   **The Green Lower Band (-2.0):** The Spread is "too low". Asset A got overly cheap compared to Asset B.
    *   *Action:* **Buy the Spread**. (Buy Asset A, Sell Asset B according to your $\beta$ Hedge Ratio).

#### 👁️ How to visually read the Z-Score Chart like a Pro
*   **The "Money Printer" Pattern:** The blue line looks like a frantic heartbeat or a sawtooth. It rapidly spikes to touch the red line (+2), and within a few bars, crashes violently down through the center line (0) to touch the green line (-2). *This means your trades open and close fast for rapid profit turnover.*
*   **The "Account Drainer" Pattern:** The blue line slowly climbs to +1.5 or +2.0 and just stays there, drifting sideways for days without ever crossing the 0 line again. *This means your capital gets trapped in an open trade paying high funding rates while refusing to mean-revert.*
        """)
