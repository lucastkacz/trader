# Blueprint: Centralized Dual-Logging System

Every institutional algorithmic engine runs in an unsupervised 24/7 environment. When a catastrophic failure occurs at 3:00 AM, the only diagnostic tool a Developer (or an AI Agent) has to reconstruct the crash is the audit trail. 

This document defines the strict, universal Logging Architecture that **must** be globally adopted by every single script in the V2 engine.

---

## 1. The "Multi-Sink" Protocol

A classic `print()` statement is an anti-pattern. `print()` cannot be piped, filtered, or parsed programmatically. The V2 logger will implement a **Multi-Sink architecture** relying exclusively on the highly-optimized **`loguru`** external Python library, abandoning the clunky standard Python `logging` module.

### Sink A: The Console (For Humans)
When a developer is actively watching the `stdout` terminal, logs must be color-coded, clean, and highly human-readable.
`[2026-03-30 18:00:00] [INFO] [volume_liquidity] Successfully filtered 150 dead pairs.`

### Sink B: The Local Disk (For AI Agents)
Simultaneously, the physical log files saved to the hard drive must be strictly formatted as **JSON Lines (`.jsonl`)**. Every log is a pure, flat JSON object. If an error occurs, an LLM Agent can be commanded to `cat engine.jsonl | grep '"level": "ERROR"'` and instantly reconstruct the mathematical state of the system in milliseconds.

### Sink C: Webhook Push Alerts (For Critical Escalation)
A third sink will actively monitor for `CRITICAL` or `ERROR` level logs. When triggered, it will immediately execute an HTTP `POST` to a Telegram or Discord Webhook. If the Global Master Switch halts the engine at 3:00 AM, the portfolio manager must be notified instantly.

### Sink D: Uptime Heartbeat (Detecting Silent Kills)
Logging events is insufficient if the script suffers an Out-Of-Memory (OOM) kill by the Linux Kernel, which leaves no error log behind. The Engine **must** transmit an HTTP Ping (Heartbeat) to an external service (e.g., Uptime Kuma or BetterUptime) every 5 minutes. If a ping is missed, the external service will fire a catastrophic failure alert.

---

## 2. Global Context Injection (Traceability)

If the Live Engine is concurrently executing 15 different Long/Short spreads and spits out a log saying `[ERROR] Failed to fetch current price`, that log is clinically useless because we don't know *which* pair failed.

Every physical `.jsonl` log emitted in the V2 system **must** be dynamically injected with structured context fields.

**Mandato de Binding (Contextualización Estricta):** 
Queda estrictamente prohibido inyectar variables de contexto (como el par de trading o el ID de la orden) formateadas directamente dentro del string del mensaje (Ej. MAL: `logger.info(f"[{pair}] Calculando")`). Esto destruye la pureza del esquema JSONL al atrapar los metadatos. 
El LLM tiene prohibido confiar en su memoria para la estructura del JSONL. Se DEBE crear un modelo Pydantic estricto llamado `LogContext`. Toda llamada a `.bind()` debe pasar previamente por la validación de ese modelo. Si se intenta loggear basura, Pydantic lanzará una excepción y lo detendrá durante el testing.
*Ejemplo Obligatorio:* 
```python
context = LogContext(pair="BTC/USDT", trade_id="123")
logger.bind(**context.model_dump(exclude_none=True)).info("Calculando Z-score")
```


**Required Schema for every JSON Log:**
* `timestamp`: ISO-8601 strict UTC string.
* `level`: The severity string (INFO, DEBUG...).
* `module`: The physical python file generating the log (e.g., `returns_matrix.py`).
* `msg`: The human-readable string.

**Dynamic (Optional) Schema:**
* `trade_id`: The UUID of the operation, if the log is executing an active trade.
* `pair`: The CCXT symbol (e.g., `AVAX/USDT`), if the log is constrained to one asset.

---

## 3. The 4 Domains of Severity

To prevent "Log Spam" from overwhelming the hard drive, logs must be strictly partitioned by their intention.

1. **`DEBUG` (Mathematical Traceability):** Used exclusively for low-level quantitative footprints that a human normally ignores. 
   - *Example:* `"Calculated Z-Score of 1.45 for SOL/APT on candle 24."*
2. **`INFO` (State Orchestration):** Used for macro-events and checkpoints. 
   - *Example:* `"Universe Pipeline finished. Exported clusters_2026-03-31.json"`
3. **`WARNING` (Infrastructure Recovery):** Used when the system handles an external failure successfully. 
   - *Example:* `"Binance Timeout caught for LDO/USDT. Initiating retry 1 of 3."*
4. **`ERROR / CRITICAL` (System Halts):** Used when an insurmountable anomaly occurs that compromises the engine. 
   - *Example:* `"BTC Volatility > 15%. Global Master Switch terminating execution."*

---

## 4. Log Rotation & Storage Management

An aggressive Execution Engine generates hundreds of megabytes of text a week. If left unchecked, it will inevitably crash the Linux server by consuming 100% of the storage space.

Loguru handles this natively with a single line of code instead of complex FileHandlers:
1. **Midnight Rollover:** A fresh file is automatically generated every single day at 00:00 UTC using `rotation="00:00"`.
2. **Auto-Purge (Garbage Collection):** The script is hardcoded to hold 30 days of data via `retention="30 days"`. Old files are permanently deleted.

---

## 5. Architectural Implementation

**The Master Rule:** We will build this centralized system in a single, perfectly isolated file: **`src/core/logger.py`**. 

No file in `src/screener`, `src/data`, or the Execution engine is allowed to use `print()` or configure its own loggers. Every single module must simply import the pre-configured Loguru instance:
`from src.core.logger import logger`

Loguru also natively captures Deep Exception Tracebacks, instantly injecting local variables into the `.jsonl` crash report if the math engine throws a zero-division error overnight.

**Configuraciones Críticas de Seguridad (Anti-LLM Fallbacks):**
1. **Escritura Segura en Concurrencia:** Todo archivo `.jsonl` configurado en `logger.add()` DEBE llevar flag `enqueue=True`. Esto fuerza a Loguru a usar una cola asíncrona segura (*thread/process safe*), eliminando las colisiones de escritura cuando la base de datos y el motor principal intentan fallar a la vez.
2. **Drenaje de Cola (Graceful Exit):** Al usar `enqueue=True`, el logger despacha volcados en segundo plano. Si el script sufre aprietes de SIGTERM, las excepciones recientes que aguardan en la cola se perderán antes de impactar el JSONL físico. El motor DEBE integrar el comando estricto `logger.complete()` en las rutinas del try-finally/shutdown protocol.
3. **Límite de Profundidad de Errores (OOM Shield):** En el entorno de producción, la configuración de rescate de Loguru DEBE llevar `diagnose=False`. Los LLMs suelen dejar en `True` la introspección completa. Al intentar subir a memoria RAM un pandas de 500MB crasheado para loggearlo, el servidor Linux sufre un Out-Of-Memory terminal.
