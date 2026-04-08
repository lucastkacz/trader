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

### Step B: Fetch "Expected Reality"
**Database Mutex Protocol**: The SQLAlchemy read/write operations must implement Row-Level locking via `.with_for_update()`. This prevents lethal Race Conditions where the Auditor kills a legitimate trade milliseconds before the Engine commits it to the DB.
The Auditor queries the local SQLAlchemy ORM: `SELECT leg_1_symbol, leg_2_symbol FROM active_trades WHERE status = 'OPEN'`.

### Step C: Compute the Delta
* **The Safe State:** If `Objective Reality == Expected Reality`. The auditor sleeps.
* **The Ghost State (Binance > Local DB):** Binance shows an open position for `ADA/USDT`, but the local DB has no record of it.
* **The Desertion State (Local DB > Binance):** The local DB thinks we are Short `DOGE/USDT`, pero Binance dice que la exposición es `0.0`. **Cláusula de Transición de Estado**: Si la base de datos local está transitoriamente en estado `PENDING_CLOSE` (indicando que el motor principal está en pleno proceso de venta a mercado), el Auditor DEBE IGNORAR este par. Actuar ciegamente sobre un `PENDING_CLOSE` dispararía webhooks fantasmas. Solo debe intervenir si el DB indica activamente `OPEN` mientras el exchange reporta vacio.

---

## 3. Autonomous Execution Directives

The Auditor is ruthless. It does not wait for a human to debug the database. It is authorized to shoot first and ask questions later.

### Handling "Ghost Positions"
If a position exists on Binance but is invisible to the local database, it means the trade is mathematically unmanaged. It has no Take Profit, no Stop Loss, and no Cointegration tracking.
1. The Auditor evaluates the size of the Ghost Position against the asset's Average Daily Volume (1min-ADV).
2. If the size is immense (e.g., $> 2\%$ volumetric order block), the Auditor delegates the execution to a **5-Minute TWAP Submodule**. It NEVER fires a raw Market Close for size, preventing a massive self-inflicted Flash Crash.
3. For small orders, the Auditor submits a standard API execution to liquidate the Ghost Position.
4. It fires a `Sink C Webhook` to Telegram: `[CRITICAL] Ghost Position liquidated on ADA/USDT. Cost: $1.20`.
5. It logs the anomaly to the `.jsonl` audit trail.

### Handling "Desertion Positions"
If Binance reports `0.0` exposure for a token that the database believes is actively `OPEN` (y NO `PENDING_CLOSE`) and holding capital:
1. The engine has lost synchronization. Attempting to update or execute logic on this pair will trigger "Insufficient Balance" API errors and crash the main loop.
2. The Auditor instantly overrides the database, forcefully mutating the `status` of the spread from `OPEN` to `FORCE_CLOSED_BY_AUDITOR`.
3. It flags the Spread ID to ensure the 4-Hour engine never interacts with it again.
4. It fires a `Sink C Webhook` alert.
