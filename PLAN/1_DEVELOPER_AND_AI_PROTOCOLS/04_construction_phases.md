# V2 LLM Agent Protocol: El Director de Orquesta

Este documento es el **Manual de Instrucciones del Agente**. Cualquier LLM (Cursor, Aider, Devin o agentes personalizados) asignado a la construcción de este repositorio **DEBE** leer este archivo antes de escribir una sola línea de código. Su objetivo es evitar alucinaciones, código espagueti y la degradación arquitectónica del sistema V2.

---

## 1. La Secuencia de Construcción Atómica

Está estrictamente prohibido programar en paralelo múltiples módulos. El desarrollo debe seguir este orden lineal y fundacional, aislando cada fase en su propio PR/Commit comprobado antes de avanzar a la siguiente.

*   **Fase 1: Infraestructura Central (El Cerebro Base)**
    *   Configurar el entorno virtual y las dependencias base estandarizadas.
    *   Escribir `src/core/logger.py` implementando estandarización Loguru (Sinks, `enqueue=True`, `diagnose=False`, mandato de `.bind()`).
    *   Escribir infraestructura de configuración (bifurcación `.env` con Pydantic-Settings y `config.yml`).
*   **Fase 2: El Músculo Aislado (Acceso a Datos y Red)**
    *   Escribir wrappers de CCXT (`src/data/fetcher/`).
    *   Implementar el gestor de almacenamiento Parquet/PyArrow con inyección de metadata (`src/data/storage/`).
    *   *Regla:* Esta es la única fase que interactúa con internet. Se debe usar `unittest.mock` para las pruebas.
*   **Fase 3: El Pipeline del Universo (Matemática Pura)**
    *   Implementar `src/screener/` paso a paso (Global Switch, Volume Sieve, Data Maturity, Clustering, Cointegration Mesh).
    *   *Regla:* Ninguna importación de `ccxt` está permitida aquí. Toda la matemática en DataFrames/Numpy que tarde >50ms debe usar delegación a hilos secundarios.
*   **Fase 4: Arquitectura de Estado Transaccional**
    *   Configurar SQLAlchemy y SQLite (`active_trades.db`). *Mandato Categórico*: SQLite no soporta verdaderos bloqueos a nivel de fila. Se debe usar estrictamente el motor asíncrono `sqlite+aiosqlite://` y configurar `PRAGMA journal_mode=WAL;` y `PRAGMA busy_timeout=5000;`. El uso de `.with_for_update()` queda revocado por inestabilidad de concurrencia.
    *   Escribir los modelos ORM que rastrearán las posiciones fraccionales.
*   **Fase 5: El Motor de Ejecución 24/7**
    *   Escribir el loop asíncrono y los protocolos de entrada Atómica/Fraccional (`src/engine/`).
    *   *Regla de Re-entrancia:* El Motor DEBE implementar un `asyncio.Lock()` (o Mutex de Estado Global). Si el loop de las 00:00 se congestiona a causa de la red hasta las 04:00, se prohíbe el solapamiento concurrente. No pueden existir dos instancias del motor evaluando la base de datos simultáneamente.
*   **Fase 6: El Auditor Criptográfico (State Reconciliation)**
    *   Construir el cronjob asíncrono e independiente que ajusta las discrepancias (Ghost/Desertion Positions).

---

