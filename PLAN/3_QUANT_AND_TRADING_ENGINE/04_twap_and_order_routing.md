# V2 Execution Engine: Architecture Blueprint

The Execution Engine is the live 24/7 autonomous component of the platform. Unlike the Universe Screener (which runs passively to calculate structure and build Cohorts), this Engine strictly governs Live Capital. It executes a rigorous continuous cycle, ensuring trades only open under strict, real-time mathematical validation.

---

### Step 6: Atomic Execution & The Micro-TWAP Protocol
The Engine rejects binary `OPEN`/`CLOSED` states. The SQLite `active_trades.db` natively tracks `target_qty` vs `filled_qty`.
* **Notional Validation:** Before building the JSON, the engine crosses the intended order size against Binance's live `/fapi/v1/exchangeInfo`.
* **The Short Window TWAP Mandate (Anti-Crowding):** El Efecto "Puerta Giratoria" (Crowded Trades) destruye los Spreads en los primeros 10 segundos de la vela 4H. **Queda terminantemente prohibido disparar órdenes completas a las 00:00:05.** El motor dividirá el capital previsto (ej. $5000) en sub-órdenes fraccionales (ej. 5 órdenes de $1000). Estas patas se dispararán progresivamente bajo un esquema **TWAP de Ventana Corta**, ejecutando exclusivamente en el intervalo de **`00:00:15` a `00:02:45`**, espaciando los disparos cada 30 segundos. Esto dilata el slippage masivo sin afectar cualitativamente el modelo de reversión a la media en marcos de 4H.
* **The "Defensive Abort" Mandate:** Para cada micro-tranche de la TWAP, si el precio se escapa y la Pata 2 no logra su entrada por rebasar el **Limite Máximo de Slippage de Aborto** estricto, la fracción asimétrica se cancela y deshace inmediatamente a mercado (abortando ese fragmento particular) para prevenir hundimientos asimétricos desbalanceados o arrastre perpetuo del capital.
