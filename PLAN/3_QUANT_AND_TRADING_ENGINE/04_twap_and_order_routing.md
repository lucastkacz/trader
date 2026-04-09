# V2 Execution Engine: Architecture Blueprint

The Execution Engine is the live 24/7 autonomous component of the platform. Unlike the Universe Screener (which runs passively to calculate structure and build Cohorts), this Engine strictly governs Live Capital. It executes a rigorous continuous cycle, ensuring trades only open under strict, real-time mathematical validation.

---

### Step 6: Atomic Execution & The Micro-TWAP Protocol
The Engine rejects binary `OPEN`/`CLOSED` states. The SQLite `active_trades.db` natively tracks `target_qty` vs `filled_qty`.
* **Notional Validation:** Before building the JSON, the engine crosses the intended order size against Binance's live `/fapi/v1/exchangeInfo`.
* **Limit Maker Chasing Mandate (Anti-Taker):** Market (Taker) execution on entries is strictly prohibited to prevent the annihilation of the statistical Edge due to fees. The router will atomically submit simultaneous **Limit (Post-Only)** orders at the current Bid/Ask. If Leg A fills and Leg B escapes, do not assume double Taker fees by immediately dumping Leg A. Leg B will dynamically adjust its Limit price, chasing the market while re-evaluating the convergence Z-Score. If the chased Z-Score falls below the minimum profitable threshold, abort the spread and take the loss on Leg A via market order.
* **Structural Displacement (The 00:05 Escape):** The "Revolving Door" Effect destroys Spreads. To isolate the engine from massive liquidations and stop-hunts at the zero-second mark (`00:00:00`), the evaluation trigger is rigidly delayed to the `00:05:00` timestamp. The engine allows the market to absorb its toxic leverage first; if the probabilist inefficiency survives until minute 5, it represents an operable structural inertia.
* **Time-To-Live (Orphan Leg Paranoia):** The limit pursuit has a strict life lock **(TTL = 180 seconds)**. If Leg B fails to fill after 3 minutes of chasing, the entire trade is canceled and Leg A is liquidated, assuming the "Orphan Taker Penalty". The engine MUST validate its ability to subsidize this potential failure within the *Expected Value (EV)* calculation BEFORE ever authorizing the initial limit entry.
