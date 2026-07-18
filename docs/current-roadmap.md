# Current Roadmap

**Actualizado:** 2026-07-18

**Objetivo activo:** construir Research V2 como un flujo offline, determinista
y entendible que produzca un candidate pair-set artifact auditable.

La secuencia congelada de implementación y el prompt obligatorio para nuevos
chats viven en
[`_IMPLEMENTATION_AGENT_GUIDE.md`](_IMPLEMENTATION_AGENT_GUIDE.md). Ese archivo
solo admite marcar una tarea completamente terminada; este roadmap sigue siendo
el documento corto y evolutivo del trabajo activo.

La implementación anterior está congelada en el tag
`legacy-v1-before-rewrite` y en el worktree
`/Users/lucastkacz/Documents/quant-v1-reference`. Es referencia histórica, no
una API que V2 deba preservar.

## North star

```text
Research V2 reproducible
-> market data readonly real
-> promoción manual confiable
-> paper trader local con fills y costos
-> demo exchange con recovery
-> gate separado para capital real
```

## Estado actual

- La branch `refactor/package-architecture` contiene solamente el setup de V2.
- El namespace decidido es `stat_arb`, bajo `src/`.
- `pyproject.toml` reemplaza requirements y configuración de pytest separados.
- No existe todavía código productivo, CLI, config operativa ni test de V2.
- Las decisiones M0/MD0/PR0 y la historia de aceptación offline están
  congeladas en la documentación; el siguiente trabajo es `V2-102`.
- Los workflows de deploy, health y live probes de V1 fueron retirados de esta
  branch para no operar accidentalmente un sistema inexistente.
- No hay ninguna ruta aprobada para Observe, Paper, Exchange/Demo o
  Exchange/Production.

## NOW — Milestone 1: Research V2 offline

Especificación canónica completa: [`RESEARCH.md`](RESEARCH.md).

Guía temporal, inventario de referencia y secuencia de implementación:
[`RESEARCH_MIGRATION.md`](RESEARCH_MIGRATION.md). Se elimina al completar la
migración del módulo.

Contratos de los módulos que sostienen este vertical:
[`PAIRS.md`](PAIRS.md), [`MARKET_DATA.md`](MARKET_DATA.md) y
[`EXCHANGE.md`](EXCHANGE.md). Sus decisiones temporales permanecen en
[`PAIRS_MIGRATION.md`](PAIRS_MIGRATION.md),
[`MARKET_DATA_MIGRATION.md`](MARKET_DATA_MIGRATION.md) y
[`EXCHANGE_MIGRATION.md`](EXCHANGE_MIGRATION.md).

### 1A. Decisiones cuantitativas explícitas

- [x] Elegir una única identidad y orientación de par.
- [x] Elegir una definición canónica del spread.
- [x] Especificar transformación de precios y convención del hedge ratio.
- [x] Definir Engle-Granger: trend, autolag, maxlag y criterio de aceptación.
- [x] Definir formation, validation y OOS sin selección con datos futuros.
- [x] Definir el tratamiento de múltiples hipótesis por corrida.
- [x] Fijar seeds para cualquier algoritmo no determinista.

### 1B. Contratos de datos y research

- [x] Definir símbolo canónico, timeframe y vela cerrada.
- [x] Definir dataset validado y universe manifest exacto.
- [x] Definir config tipada sin paths, exchange o clocks ocultos.
- [x] Definir resultado de cada etapa y errores observables.
- [x] Definir `CandidatePairSet` y provenance mínimo obligatorio.
- [x] Definir JSON como adapter de persistencia, no como modelo interno.

Estos checks indican decisiones contractuales documentadas. Los tipos y su
comportamiento ejecutable se implementan en `V2-102` a `V2-105`.

### 1C. Primer vertical determinista

```text
fixture local
-> OHLCV validado
-> universe manifest
-> discovery y cointegration
-> validación/stress mínimo
-> CandidatePairSet tipado
-> JSON versionado
-> reporte reproducible
```

- [ ] Implementar una única ruta pública de research.
- [ ] Mantener matemática, I/O, orchestration y rendering separados.
- [ ] Crear tests de comportamiento offline a través de interfaces públicas.
- [ ] Probar que idénticos inputs producen idéntico resultado semántico.
- [ ] Probar ausencia de network y exchange mutation.

### Definition of Done

- El flujo completo corre desde un workspace sin artifacts previos.
- No usa red, credenciales ni datos externos durante la prueba de aceptación.
- Solo consume velas explícitamente cerradas y no tiene look-ahead.
- El universo usado queda persistido con identidad exacta de símbolos.
- El spread estimado, testeado, reportado y serializado es el mismo.
- Formation, validation y OOS tienen límites temporales auditables.
- El candidate artifact tiene schema version, stage y provenance verificable.
- Tests, lint y validación de packaging pasan localmente y en CI.
- Una persona puede seguir el flujo desde una única API pública y el reporte.

## NEXT — Market data readonly y promoción

- Resolver primero las preguntas bloqueantes de `MARKET_DATA_MIGRATION.md` y la
  fase readonly de `EXCHANGE_MIGRATION.md`.
- Agregar un adapter readonly de exchange detrás del contrato probado con
  fixtures.
- Implementar backfill y gap/tail refresh idempotente.
- Preservar símbolos canónicos a través de storage.
- Excluir vela abierta y validar continuidad, cobertura y freshness.
- Agregar candidate review y promoción manual auditable.
- Verificar que recalcular pares solo afecta futuras entradas.

## THEN — Evidencia cuantitativa y paper local

- Expandir walk-forward/OOS, costos y estabilidad temporal sin cambiar el
  spread canónico.
- Diseñar el contrato inmutable que cruzará de research a trading.
- Recién después crear `trading` y un paper broker stateful con intents, fills,
  partials, rejects, fees, funding, slippage y restart determinista.
- Derivar PnL y equity desde fills, no desde precios teóricos de señal.
- Resolver y ejecutar las etapas de [`TRADING_MIGRATION.md`](TRADING_MIGRATION.md)
  bajo el contrato de [`TRADING.md`](TRADING.md).
- Incorporar `operations` e `interfaces` solo desde casos de uso concretos,
  siguiendo [`OPERATIONS.md`](OPERATIONS.md) e
  [`INTERFACES.md`](INTERFACES.md), sin adelantar UI o scheduler.

## LATER — Demo y capital real

Demo/testnet y capital real requieren sizing, límites, precisión, idempotent
submission/recovery, partial-leg compensation, reconciliación fail-closed,
kill switch operativo, single-writer, migraciones, alertas y recovery drills.

Demo valida integración y recovery; no demuestra alpha. Capital real requiere
además completar la fase de capital real de
`_IMPLEMENTATION_AGENT_GUIDE.md`, los gates de `TRADING_MIGRATION.md` y una
aprobación manual separada con capital mínimo.

## Fuera de alcance ahora

- Feature parity con V1.
- Trading runtime, paper broker u order routing.
- Telegram, HTTP, dashboard o login.
- PostgreSQL, cloud, microservicios o scheduler.
- Auto-promoción, hot reload o rebalancing.
- FM-OLS, DOLS, GARCH o baterías estadísticas antes del baseline causal/OOS.
- Abstracciones creadas solamente para anticipar posibilidades futuras.

## Regla de entrada

Una tarea entra en `NOW` solo si completa el vertical de Research V2, hace
explícito un supuesto cuantitativo, elimina look-ahead, mejora provenance o
produce evidencia reproducible. El resto espera.
