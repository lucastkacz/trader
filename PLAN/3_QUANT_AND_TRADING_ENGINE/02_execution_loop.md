# V2 Execution Engine: Architecture Blueprint

The Execution Engine is the live 24/7 autonomous component of the platform. Unlike the Universe Screener (which runs passively to calculate structure and build Cohorts), this Engine strictly governs Live Capital. It executes a rigorous continuous cycle, ensuring trades only open under strict, real-time mathematical validation.

---

## 1. Schedule Synchronization & API Lag Traps
The Engine remains dormant until slightly after a 4-Hour boundary (`00:00:05 UTC`). 
**REST API Delay Trap:** Crypto exchange REST APIs lag severely under massive global volume during daily closes (e.g., exactly at 00:00:00). Fetching at 00:00:05 may yield stale data where the "latest" candle is still technically the previous 4-hour block. The system must implement a **Timestamp Validation Loop**: if the `close_time` of the fetched candle does not perfectly match the cron boundary, the engine executes **strictly `asyncio.sleep(2)`** (blocking with synchronous `time.sleep()` will paralyze the entire bot engine) and waits asynchronously until the exchange database synchronizes.

---

## 2. Active State Management (SQLite vs JSON)
The Engine requires an internal memory to track what Spreads it physically owns. 

While Binance knows you own "100 AVAX" and "-100 NEAR", the Exchange API does not mathematically link them. An internal database is required to group isolated Exchange legs under a single `SpreadID`.

**We mandate SQLite over JSON.**
State Management requires ACID compliance (Atomicity, Consistency, Isolation, Durability). If the engine crashes or loses power at the precise millisecond it is writing an update to a `trades.json` file, the file will completely corrupt and irreparably destroy the internal tracking ledger. SQLite prevents this natively with Write-Ahead Logging (WAL) and rollback safeties, all without requiring complex server setups.

---

## 3. The 6-Step Execution Loop
When the 4-Hour trigger fires, the Engine executes the following deterministic order.


### Step 2: Phase 0 Engine Check (The Master Switch)
The system connects to Binance to read Bitcoin's trailing volatility. If Bitcoin is currently experiencing a historic Flash-Crash ($VIX \gg Threshold$), the entire crypto market correlations skew artificially to 1.0. 
The Engine **activates the Master Switch**. This panic breaker EXCLUSIVELY prohibits the hunting of new horizons (it bypasses Steps 3 through 6). The positions that were already `OPEN` (managed above in Step 1) MUST continue to be evaluated and managed for their Take Profit or Stop Loss. Abandoning them would leave the portfolio in freefall during a market crash.
