# Current Roadmap

**Actualizado:** 2026-07-17

**Objetivo activo:** llegar a un paper trader local, determinista y creíble,
sin habilitar capital real.

**Diagnóstico y evidencia:**
[`PROJECT_REENTRY_AUDIT.md`](PROJECT_REENTRY_AUDIT.md)

Este archivo contiene sólo trabajo activo y próximo. El changelog vive en Git.

## North star

```text
cold start reproducible
-> paper local con fills y costos
-> research walk-forward/OOS
-> demo exchange con recovery
-> gate separado para capital real
```

## Estado actual

### Preservar

- Research separado de exchange mutation; todos los pipelines usan
  `state_only`.
- Configuración tipada, candidate/promoted con promoción manual.
- SQLite transaccional, motivos de bloqueo y reconciliación readonly visibles.
- Replay determinista comparte la política de señal.
- Baseline offline verificado durante la auditoría del 2026-07-17; los números y
  comandos exactos quedan en `PROJECT_REENTRY_AUDIT.md` como evidencia fechada.

### No confundir con paper

- `state_only` no simula fills, partials, fees, funding ni slippage.
- Su PnL es teórico bruto, no execution PnL.
- Reconciliación detecta deltas pero no bloquea ejecución.
- Stop/kill switch son local-state o entry-only; no hacen flatten de exchange.
- Los artifacts/data de los drills anteriores ya no están en el workspace.

## NOW — Milestone 1: cold start local confiable

Objetivo:

```text
workspace vacío
-> market data válido
-> universe manifest
-> candidate STRESS_EVALUATED
-> promoción manual
-> bounded state_only
-> restart seguro
-> reporte auditable
```

### 1A. Identidad y lifecycle de datos

- [ ] Leer el símbolo CCXT canónico desde metadata; cubrir
  `BTC/USDT:USDT` y quotes USDT/USDC.
- [ ] Persistir el manifest exacto de símbolos aceptados en cada research run.
- [ ] Hacer que discovery consuma sólo ese manifest, no Parquet históricos.
- [ ] Implementar reuse + gap/tail refresh idempotente.
- [ ] Excluir vela abierta y validar continuidad, cobertura y freshness.
- [ ] Escribir data/metadata mediante temp + atomic replace.
- [ ] Resolver lifecycle por ambiente: UAT/prod piden 365 días y el default
  retiene 5.

Salida: el símbolo hace round-trip exacto, un archivo viejo no reingresa y una
segunda corrida descarga sólo gaps/tail.

### 1B. Semántica segura de runtime

- [ ] Crear `NO_DATA/UNAVAILABLE`, distinto de la señal económica `FLAT`.
- [ ] Ante data inválida: no abrir/cerrar, preservar posición y emitir reason.
- [ ] Validar última vela cerrada, gaps, cantidad y freshness en runtime.
- [ ] Hacer que `pause` bloquee entries, no MTM/exits.
- [ ] En flip bloqueado: permitir close y omitir replacement entry.
- [ ] Implementar `stop_loss_z_score` en la policy compartida o retirarlo.
- [ ] Hacer fail-closed el kill switch corrupto y validar el DB target.

Salida: una falla de data nunca parece una reversión y las posiciones abiertas
conservan salida natural bajo pause.

### 1C. Artifacts y restart

- [ ] Modelar `DISCOVERED -> STRESS_EVALUATED -> OPERATOR_PROMOTED`.
- [ ] Rechazar promotion sin stress/provenance completo.
- [ ] Validar finitud, rangos, símbolos, baseline y hashes del artifact.
- [ ] Hacer promoción + audit recuperables como una transición lógica.
- [ ] Persistir el contrato inmutable de entry: orientación, beta, lookback,
  thresholds, sizing convention y hashes de artifact/config.
- [ ] En boot, unir promoted actual para entries con open-position contracts
  para exits.

Salida: retirar o recalibrar un par nunca deja huérfana ni reinterpreta una
posición abierta.

### 1D. Baseline reproducible

- [ ] Declarar Python soportado —mínimo 3.11; preferir 3.11/3.12— y alinear CI.
- [ ] Eliminar referencias a `ci_1m.yml`/`ci_4h.yml` inexistentes.
- [ ] Separar dependencias runtime/dev y agregar lock o constraints.
- [ ] Corregir health: DB vacía no es fresh y drawdown no termina en `|| true`.
- [ ] Añadir CI offline research → promote → bounded execute con fixtures.
- [ ] Reemplazar el bloqueo actual del runbook por un único cold-start drill
  probado de punta a punta.

### Definition of done

- Tres cold starts completan sin edición manual de data/artifacts.
- No se usan credenciales live ni se crean exchange/client order IDs.
- El segundo run reutiliza datos y trae sólo lo faltante.
- Candidate/promoted contienen provenance verificable.
- Restart preserva el contrato y natural exit de posiciones abiertas.
- Tests, lint, config validation y e2e pasan en CI y local.

## NEXT — Milestone 2: paper local stateful

- [ ] Clock y event ordering explícitos: decisión después del candle close; fill
  en el siguiente evento ejecutable.
- [ ] Order/fill lifecycle simulado: pending, partial, filled, rejected,
  canceled y unknown/timeout.
- [ ] Failure de segunda pierna y compensación.
- [ ] Una sola convención hedge/exposure; weights congelados o rebalanceo con
  turnover explícito.
- [ ] Fees, slippage y funding por tiempo/settlement.
- [ ] PnL/equity derivados de fills.
- [ ] Queue, risk, pause, kill switch, restart y natural exit compartidos con el
  runtime online.

Gate de salida: la misma fixture produce los mismos intents, fills, costos,
posiciones y equity, incluso interrumpiendo y reiniciando en cualquier evento.

## THEN — Milestone 3: baseline cuantitativo

- [ ] Elegir un spread/orientación canónico y testear ese mismo residual.
- [ ] Engle-Granger con trend/autolag/maxlag y evidencia explícitos.
- [ ] Control FDR por corrida; fijar `random_state` de Louvain.
- [ ] Beta, weights y features causales por fold.
- [ ] Alinear `[1, -beta]` con notionals, quantities y PnL.
- [ ] Formation → validation → OOS final, con parámetros congelados.
- [ ] Reportar trades, turnover, costos, search count y estabilidad temporal.
- [ ] Corregir funding por tiempo y usar histórico por símbolo cuando exista.

Gate de salida: el spread testeado, señalizado, simulado y contabilizado es el
mismo; ningún dato OOS selecciona parámetros.

Después pueden evaluarse EWMA, KPSS/PP, robust regression y DOLS/FM-OLS. GARCH
queda fuera hasta existir una hipótesis y benchmark concretos.

## LATER — Demo y capital real

Demo/testnet requiere antes:

- sizing equity → quote notional → contracts/qty;
- límites y precisión reales del mercado;
- idempotent submission/recovery, partial-leg compensation y reduce-only;
- reconciliación agregada, periódica y fail-closed;
- single-writer lease y migraciones versionadas;
- drills de restart, timeout, reject, partial, stale data y cancel/flatten.

Demo valida API/recovery; no demuestra alpha.

## Standing gate: sin aumento de capital

No cambiar `order_execution.mode` a `live`, cargar credenciales live ni aumentar
exposición durante estos milestones. Capital real requiere además el gate de
`docs/engineering-rules.md`, PnL por fills, límites de pérdida, secrets por
ambiente, alertas, backup/restore y aprobación manual con capital mínimo.

## Fuera de alcance por ahora

- Refactor general o dividir archivos sólo por líneas.
- Auto-promoción, hot reload o rebalanceo automático.
- Forced close por cambios del pair set.
- Scheduled research antes del lifecycle idempotente.
- Dashboard web, nuevo login, microservicios o nueva base.
- FM-OLS, DOLS, GARCH o baterías de tests antes del baseline causal/OOS.

## Regla de entrada al roadmap

Una tarea entra en `NOW` sólo si elimina un riesgo del milestone, desbloquea un
flujo completo, hace reproducible un resultado, repara una divergencia
demostrada o aporta evidencia para cruzar el siguiente gate. El resto espera.
