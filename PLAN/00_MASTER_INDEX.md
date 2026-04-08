# V2 PLAN MASTER INDEX

Este archivo es el **Directorio Raíz** de la planeación arquitectónica del Motor de Arbitraje Estadístico Fase 2.
Los documentos monolíticos han sido fragmentados en 5 dominios de responsabilidad única para asegurar que los Agentes y los Desarrolladores no sufran contaminación cruzada de instrucciones.

Cualquier Bot o Desarrollador ingresando al sistema debe consultar este índice para encontrar las reglas pertinentes a su especialidad.

---

## 📂 1_DEVELOPER_AND_AI_PROTOCOLS/
*Reglas base para los Agentes Autónomos (Cursor, Aider, Gemini) y restricciones de tecnología.*
- `01_coding_manifesto.md` -> Vectorización estricta, PyArrow Schema guards, SQLAlchemy asíncrono.
- `02_llm_system_prompts.md` -> Reglas de Anti-Alucinación, Rate Limits en red e Interacción con Humanos.
- `03_tdd_and_testing_rules.md` -> Aislamiento forzoso de red, mocking de CCXT y flujo TDD.
- `04_construction_phases.md` -> Strict Order Sequence desde Logger Base hasta Reconciliation Auditor.

## 📂 2_SYSTEM_INFRASTRUCTURE/
*La plomería estructural transaccional que asegura la supervivencia en 24/7.*
- `01_dual_sink_logging.md` -> Jsonlines estructurado en Loguru, colas OOM y `.complete()` de drenaje.
- `02_state_reconciliation_auditor.md` -> El Cronjob en 10 min, Ghost/Desertion Tracker y exclusión `PENDING_CLOSE`.

## 📂 3_QUANT_AND_TRADING_ENGINE/
*Matemática de Generación y Ejecución de órdenes de Nivel de Producción.*
- `01_universe_and_clustering.md` -> Sieve Volumes, Data Maturity de 180 días, y Louvain Graph Clustering pipelines.
- `02_execution_loop.md` -> El ciclo cron 4H basal, Retraso API pasivo y el Master Switch del VIX (Protección de Pánicos).
- `03_signals_and_ew_ols.md` -> La capa cuantitativa (Fase 4 y 5): Mean Reverting Funding, Exponentially Weighted OLS Deviation, Hedge Ratios y filtros O-U.
- `04_twap_and_order_routing.md` -> Protocolo Quirúrgico Atómico 4H: El "Micro-TWAP" y las reglas de Aborto de Tolerancia a Slippage.

## 📂 4_PORTFOLIO_AND_RISK/
*Los cortafuegos del capital real.*
- `01_isolated_margin_mandates.md` -> Prohibición estricta del Cross Margin, y el límite absoluto de Aislamiento.
- `02_capital_exposure_limits.md` -> Reglas volumétricas, fraccionado proporcional e interrupción del sesgo de Sector por "Clúster".

## 📂 5_BACKTESTING_SIMULATION/
*Reglas del Motor de Realidad Simulado.*
- `01_vectorized_simulation.md` -> Prohibición exhaustiva de look-ahead bias a través de "Tiempo + 1m".
- `02_friction_and_funding_penalties.md` -> Costos transaccionales cuadráticos y deducción de *Time-in-Market* para castigar proyecciones ilusorias.
