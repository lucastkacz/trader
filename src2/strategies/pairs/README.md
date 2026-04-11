# Pairs Trading Strategy (Statistical Arbitrage)

## Overview
This strategy exploits temporary pricing inefficiencies between two historically correlated and **cointegrated** assets. It assumes that if two assets share a long-term equilibrium (mean-reverting spread), any short-term divergence presents a profitable opportunity to bet on their convergence.

## 1. The Regime Filter: Cointegration ($p$-value)
Before taking any trades, the strategy must confirm that the assets are currently acting together. We measure this using the **Augmented Dickey-Fuller (ADF) Test**, which outputs a $p$-value indicating the probability that the spread is just random noise (a random walk).

*   **Safe Zone ($p \le 0.10$):** green zone. The spread is statistically mean-reverting. The bot is cleared to enter new positions.
*   **Hold Zone ($0.10 < p \le 0.40$):** yellow zone. The relationship is getting noisy. The bot stops taking *new* trades, but trusts the math enough to hold existing open positions while waiting for the target to be hit.
*   **Emergency Cut-off ($p > 0.40$):** red zone. Structural break. The assets have completely decoupled. The bot panics, forcing the closure of all open positions immediately to prevent infinite drawdown.

## 2. Signal Generation: Z-Score
Once the regime is safe, the bot calculates the **Z-Score** of the rolling spread. The Z-Score tells us how many standard deviations the current spread is away from its recent historical average (usually measured over the last 30 hours).

*   **Go Long Spread ($Z \le -2.0$):** Asset A is unusually cheap compared to Asset B. The bot buys Asset A and shorts Asset B.
*   **Go Short Spread ($Z \ge +2.0$):** Asset A is unusually expensive compared to Asset B. The bot shorts Asset A and buys Asset B.
*   **Take Profit ($Z$ crosses $0.0$):** The spread has returned to its historical mean. The pricing inefficiency is gone, and the bot closes both legs of the trade to secure profits.

## 3. Position Sizing & Beta Hedging
This is a **market-neutral** strategy. To maintain neutrality, the short leg must be weighted by the *Hedge Ratio* (Beta), calculated via rolling OLS regression. 
If Beta is 0.5, it means Asset B moves half as much as Asset A. Thus, for every $10,000 invested in Asset A, the bot will short $5,000 of Asset B, neutralizing directional market risk (Delta = 0).
