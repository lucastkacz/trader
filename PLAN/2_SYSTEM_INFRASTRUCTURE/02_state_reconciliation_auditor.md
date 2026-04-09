# V2 State Reconciliation: The Cryptographic Auditor

Distributed systems are inherently unreliable. When your trading bot sends an HTTP request to Binance to open a $10,000 position, the exchange might execute the order perfectly, but the HTTP `200 OK` response might be dropped by a brief internet outage. 

When the response drops, your local `active_trades.db` never records the trade. You are now holding a **"Ghost Position"**—a live, capital-risking trade that your bot doesn't know exists, and therefore, will never close.

This document outlines the **State Reconciliation Auditor**, the final safety perimeter of the V2 Engine.

---

## 1. The Audit Cadence (Asynchronous Independence)
The Reconciliation Auditor must **never** be part of the 4-Hour Execution Engine loop. If the Execution Engine crashes, the Auditor must survive to catch the pieces.
* It runs as an entirely independent Cronjob or background thread.
* It executes an aggressive reconciliation poll exactly every **10 Minutes**.

---

## 2. The Three-Way Ledger Mathematical Cross-Check
Every 10 minutes, the Auditor performs a strict Set-Theory mathematical difference check.

### Step A: Fetch "Objective Reality"
The Auditor calls `ccxt.fetch_positions()`. This returns an array of every single token currently holding > 0 exposure on the Binance Futures account. This is the undeniable truth.

### Step B: Fetch "Expected Reality" (The RAM-Log Join)
**The Awakening from Amnesia:** All 4H market loop transactions were abstracted away from the Database into a volatile "Python RAM Dictionary". 
The *Blackout Protocol* dictates that if Binance yields $502$ Gateway errors consecutively for $\ge 60$s, the primary engine collapses intentionally, paralyzing core operations to evade noise (Amnesia State). 
When REST is restored, the Auditor enters a `Join()` detour. 
Binance (`/fapi/v2/positionRisk`) returns passive inventory but omits the quantitative correlation ("You solely hold X and Y"). The Auditor queries the **Append-Only SQLite Logbook**: crisscrossing the reality of Binance's reported balances against the passive relational history previously documented in SQLite. It recovers a semantic Cointegration trail (`engine_state['Y-X'] = 'OPEN'`), rigorously forcing the reimplantation of the exact RAM dictionary before safely releasing the primary engine back out to hunt.

### Step C: Compute the Delta
* **The Safe State:** If `Objective Reality == Expected Reality`. The auditor sleeps.
* **The Ghost State (Binance > Local DB):** Binance shows an open position for `ADA/USDT`, but the local RAM has no record of it.
* **The Desertion State (Local DB > Binance):** The local RAM thinks we are Short `DOGE/USDT`, but Binance states that exposure is `0.0`. **State Transition Clause**: If the local engine state is transiently in `PENDING_CLOSE` (indicating the core engine is actively executing a market sell), the Auditor MUST IGNORE this pair. Acting blindly upon a `PENDING_CLOSE` state triggers phantom panics. It should only intervene if the engine explicitly holds an `OPEN` state flag while the exchange is empty.

---

## 3. Autonomous Execution Directives

The Auditor is ruthless. It does not wait for a human to debug. It is authorized to shoot first and ask questions later.

### Handling "Ghost Positions"
If a position exists on Binance but is invisible to the local engine, it means the trade is mathematically unmanaged. It has no Take Profit, no Stop Loss, and no Cointegration tracking.
1. The Auditor evaluates the size of the Ghost Position against the asset's Average Daily Volume (1min-ADV).
2. If the size is immense (e.g., $> 2\%$ volumetric order block), the Auditor delegates the execution to a **5-Minute TWAP Submodule**. It NEVER fires a raw Market Close for size, preventing a massive self-inflicted Flash Crash.
3. For small orders, the Auditor submits a standard API execution to liquidate the Ghost Position.
4. It fires a `Sink C Webhook` to Telegram: `[CRITICAL] Ghost Position liquidated on ADA/USDT. Cost: $1.20`.
5. It logs the anomaly to the `.jsonl` audit trail.

### Handling "Desertion Positions"
If Binance reports `0.0` exposure for a token that the internal engine believes is actively `OPEN` (and NOT `PENDING_CLOSE`) and holding capital:
1. The engine has lost synchronization. Attempting to update or execute logic on this pair will trigger "Insufficient Balance" API errors and crash the main loop.
2. The Auditor instantly overrides the engine, forcefully mutating the `status` of the spread from `OPEN` to `FORCE_CLOSED_BY_AUDITOR`.
3. It flags the Spread ID to ensure the 4-Hour engine never interacts with it again.
4. It fires a `Sink C Webhook` alert.
