# Trading Migration Guide

> **TEMPORARY DOCUMENT**
>
> This guide maps the frozen trader implementation into the Trading module. It
> contains open design decisions and staged safety gates. Delete it when the
> migration is complete and retain accepted behavior in `docs/TRADING.md`.

## 1. Purpose and Authority

The frozen implementation at tag `legacy-v1-before-rewrite` and worktree
`/Users/lucastkacz/Documents/quant-v1-reference` is reference evidence only.
It is not production proof and its interfaces are not preserved automatically.

Authority order:

1. Lucas's explicit instruction for the current task.
2. `.agents/AGENTS.md` for durable implementation and safety rules.
3. `docs/_IMPLEMENTATION_AGENT_GUIDE.md` for route order and completion state.
4. `ARCHITECTURE_REFACTOR.md` and the relevant canonical module documents.
5. `docs/current-roadmap.md` for current status and near-term scope.
6. This guide for migration traceability, open decisions, slices, and gates.
7. Frozen tests as clues about intended V1 behavior.
8. Frozen implementation and config as clues about actual V1 behavior.

Trading implementation remains deferred until Research produces a stable
promoted contract. Documentation now prevents that later work from copying
unsafe runtime assumptions.

Path convention: unless a path begins with `src/`, `configs/`, or `tests/`,
Trading source paths are relative to `src/engine/trader/`. Test filenames named
without their full prefix refer to the matching area under
`tests/engine/trader/`.

## 2. Working Capability Map

```text
trading
├── runtime and readiness
├── eligibility and signals
├── portfolio and risk
├── intents, orders, fills, and brokers
├── positions and accounting
├── state and reconciliation
└── typed reporting projections
```

`operations` owns process/use-case orchestration. `interfaces` owns delivery.
`exchange` owns venue translation. `pairs` owns artifacts and specifications.

## 3. Migration Actions

- **KEEP**, **ADAPT**, **SPLIT**, **MERGE**, **MOVE**, **REPLACE**, **DROP**,
  **DEFER**, and **OPEN** have the meanings used by the other migration guides.

## 4. Existing Runtime Flow

```text
pipeline config and globals
-> load promoted JSON and apply runtime Sharpe filter
-> open SQLite manager
-> optional readonly boot reconciliation
-> loop at candle boundary
-> fetch recent candles
-> evaluate signal and queue/risk gates
-> write local position and leg targets
-> optionally submit CCXT orders
-> snapshot theoretical PnL/equity
-> process string commands and notify Telegram
```

The frozen runtime contains several valuable invariants and extensive tests,
but it mixes application wiring, domain decisions, direct state persistence,
venue adapters, notification, and scheduling. `state_only` writes positions and
leg targets without a paper order/fill model, so it is not paper trading.

## 5. Source Inventory: Configuration and Boot

| Frozen source | Evidence | Action |
|---|---|---|
| `engine/trader/config/models.py` | Strict Pydantic models for execution, queue, risk, strategy | SPLIT by concept owner; remove monolithic config surface |
| `engine/trader/config/loader.py` | Strict top-level YAML loading | MOVE to Core config boundary/application composition |
| `runtime/trader_runner.py` | Boot, wiring, reconciliation, ticks, shutdown, notifications | SPLIT into Operations wiring and Trading runtime API |
| `pipeline/master_flow.py` | Starts trader and Telegram through Prefect | REPLACE; workflow framework cannot own domain boot |
| `core/config.py` | Global settings and credentials | REPLACE with injected typed secrets/authorization |
| `configs/pipelines/*.yml` | Full runtime wiring and `state_only` mode | REPLACE with typed mode/environment contracts |
| `configs/strategy/*.yml` | Entry/exit/lookback policy | ADAPT after Research/Trading alignment decisions |
| `configs/risk/alpha_v1.yml` | Exposure and basic order/liquidity thresholds | ADAPT; values are development placeholders, not production limits |

The global settings instance, logger side effects, direct adapter construction,
and Telegram construction make boot hard to isolate. V2 application wiring must
construct dependencies outside the Trading domain API.

## 6. Source Inventory: Signals and Runtime Decisions

| Frozen source | Evidence | Action |
|---|---|---|
| `signals/evaluator.py` | Timestamp alignment, canonical hedged log spread, side-aware exits | ADAPT; return `UNEVALUABLE` instead of synthetic finite flat results |
| `signals/models.py` | Small signal result | REPLACE with typed cutoff/specification/reason contract |
| `runtime/signal_transition.py` | Open/close/flip planning plus I/O | SPLIT pure transition planning from persistence/routing/notification |
| `runtime/tick.py` | Shared candle fetch, queue order, signal/risk/transition loop | SPLIT into deterministic boundary processor and injected capabilities |
| `runtime/scheduler.py` | Candle-boundary timing | MOVE to Operations; retain timeframe math in Market Data/Core as appropriate |
| `execution/market_data.py` | Bounded readonly fetch/retry | MOVE to Market Data/Exchange seam |

The frozen evaluator drops invalid prices and returns `FLAT` with zeros for
insufficient data. That can turn data failure into an exit instruction. V2 must
distinguish unevaluable data from a valid flat target.

## 7. Source Inventory: Pair Validity and Queue

| Frozen source | Evidence | Action |
|---|---|---|
| `runtime/pair_validity/models.py` | Detailed typed drift and age measurements | ADAPT |
| `pair_validity/statistics.py` | Recent regression/correlation/cointegration diagnostics | ADAPT after canonical math alignment |
| `pair_validity/artifact.py` | Extracts optional baseline values from raw rows | REPLACE with typed Pairs specification |
| `pair_validity/market_data.py` | Loads recent local observations | MOVE to Market Data consumer seam |
| `pair_validity/time.py` | Age/bars calculations | MERGE into cohesive validity behavior with explicit clock |
| `pair_validity/state.py` | Open-position and observed-exit evidence | ADAPT through Trading state query contract |
| `pair_validity/report.py` | 332-line mixed assembler | SPLIT calculation result from rendering/projection |
| `pair_validity/refresh.py` | 390-line artifact-driven data refresh | MOVE synchronization to Market Data; retain Trading use case trigger in Operations |
| `runtime/pair_queue/models.py` | Typed scoring, thresholds, exposure and decisions | ADAPT |
| `pair_queue/ranking.py` | 442-line scoring/block/rank logic | SPLIT or deepen behind one queue interface |
| `pair_queue/execution.py` | Connects opportunities/signals to queue | ADAPT after signal contract |

The strongest frozen invariant is that validity and queue failures block future
entries only and do not close open positions. Preserve it with cross-module
behavior tests.

## 8. Source Inventory: Risk and Portfolio

| Frozen source | Evidence | Action |
|---|---|---|
| `runtime/risk/models.py` | Typed policy, decision, liquidity, kill-switch state | ADAPT with explicit units and venue limits |
| `runtime/risk/pre_trade.py` | Exposure, leverage, quantity, notional, liquidity gates | REPLACE calculations that treat normalized weights as order quantities |
| `runtime/risk/liquidity.py` | Recent quote-volume snapshot | ADAPT through Market Data facts |
| `runtime/risk/kill_switch.py` | Durable active/inactive state | ADAPT; malformed/missing state must fail closed |
| `risk/position_sizer.py` | Inverse-vol allocation and leverage exception | MERGE only validated sizing concepts; drop duplicate standalone owner |

Frozen pre-trade sizing scales signal weights to percentage exposure, then
checks those percentages against exchange quantity/notional fields. It lacks
account equity currency, contract multipliers, instrument precision/limits,
margin mode, balance, and realistic available liquidity. This is a blocker for
any exchange-routing milestone.

## 9. Source Inventory: Orders and Position Lifecycle

| Frozen source | Evidence | Action |
|---|---|---|
| `execution/orders.py` | Per-leg submit/poll/cancel and client ids | SPLIT venue payload to Exchange; coordination and intents to Trading |
| `execution/liquidation.py` | Explicit close workflow using current prices | REPLACE; separate local close intent from confirmed economic liquidation |
| `execution/pnl.py` | Theoretical position/per-pair returns | REPLACE with fill/cash/mark accounting |
| `state/order_lifecycle.py` | Explicit legal leg transitions and idempotency | KEEP intent; add ambiguous/expired states and durable versioning |
| `state/lifecycle.py` | Opens/closes spread rows, legs, events, PnL | REPLACE target-price lifecycle with fill-derived positions |
| `state/legs.py` | Leg target and execution rows | ADAPT to typed order/fill aggregates |
| `state/events.py` | Idempotent order events | ADAPT into immutable domain event ledger |
| `state/positions.py` | Spread position CRUD | ADAPT behind state-store contract |

The frozen open workflow inserts a position before exchange submission. In
`state_only`, it remains a local position with no fills. In live mode, one leg
can complete while the other fails without a complete compensation state
machine. Both behaviors must be replaced before paper or exchange routing.

## 10. Source Inventory: State and Persistence

| Frozen source | Evidence | Action |
|---|---|---|
| `state/schema.py` | SQLite tables for positions, events, legs, equity, signals, commands, runtime, reconciliation | ADAPT schema concepts; do not preserve SQL as domain model |
| `state/connection.py` | SQLite connection and pragmas | MOVE to SQLite adapter |
| `state/migrations.py` | Idempotent schema alterations | REPLACE with explicit ordered schema versions |
| `state/repositories.py` | Repository bundle | SPLIT into a deeper transactional state-store interface |
| `state/services.py` | Timestamped operations and transitions | SPLIT clock, transaction, lifecycle, commands, reconciliation |
| `state/manager.py` | 404-line facade over all state concerns | DROP after callers use cohesive module interfaces |
| `state/equity.py`, `signals.py`, `commands.py`, `runtime.py`, `reconciliation.py` | Narrow SQL repositories | MOVE behind adapter; merge shallow surfaces where one transaction owns behavior |
| `state/serialization.py` | JSON helpers | MOVE to adapter and make versions explicit |

SQLite remains suitable locally. The issue is domain coupling to SQLite rows and
one broad manager, not SQLite itself.

## 11. Source Inventory: Reconciliation

| Frozen source | Evidence | Action |
|---|---|---|
| `reconciliation/service.py` | Readonly snapshot, delta taxonomy, stale/partial detection, scheduled audit | ADAPT and split calculation from persistence/scheduling |
| `exchange/execution/account.py` | Account/position snapshot provider | ADAPT under Exchange account contract |
| `state/reconciliation.py` | Run/delta persistence | MOVE behind Trading state store |

The frozen reconciliation is deliberately read-only, which is safe. It compares
local target quantity with exchange quantity and sometimes expects a local
`spread_id` in exchange snapshots, which is not a valid venue identity. V2 must
reconcile by canonical instrument, venue account/position mode, client order id,
exchange order id, and fills.

## 12. Source Inventory: Reporting and Monitoring

| Frozen source | Evidence | Action |
|---|---|---|
| `reporting/models.py` | Typed report aggregates | ADAPT into stable read models |
| `reporting/assembler.py` | Portfolio report plus pair queue/validity | SPLIT projections from formatting and storage access |
| `reporting/metrics.py` | Sharpe, Sortino, drawdown, trade stats | ADAPT with units, sampling, cash accounting, and validity rules |
| `reporting/per_pair.py`, `risk.py`, `signal_quality.py`, `state_ledger.py` | Section-specific calculations | MERGE behind one query/projection interface where cohesive |
| `reporting/backtest_lookup.py` | Direct artifact JSON access | DROP; use Pairs typed contract |
| `reporting/position_inspector.py` | Position deep-dive | ADAPT from stable read models |
| `reporting/render_*`, `export.py` | Terminal/Markdown/JSON presentation | MOVE to Interfaces or Operations reporting adapter |
| `runtime/monitoring/health.py` | Typed persisted health | ADAPT |
| `runtime/monitoring/run_status.py` | Run markers, health and report probes in 278 lines | SPLIT Operations run status from Trading projections |

Reports currently derive performance from theoretical local positions and
equity percentage snapshots. They cannot substantiate paper or live economic
performance until accounting is fill-based.

## 13. Source Inventory: Commands and Notifications

| Frozen source | Evidence | Action |
|---|---|---|
| `commands/processor.py` | Claims string commands and invokes liquidation/pause/resume | REPLACE with typed authorized commands through Operations |
| `state/commands.py` | Durable command queue | ADAPT with principal, authorization, expected version, result |
| `interfaces/telegram/notifier.py` | Best-effort outbound notification | MOVE to Interfaces adapter behind event/notification seam |

The frozen `/stop` and `/stop_all` descriptions imply liquidation while tests
prove only local state close in `state_only`. V2 names local pause, reduce-only,
cancel, and actual liquidation separately.

## 14. Test Inventory

### Preserve as behavioral intent

- signal side/exit behavior and research/runtime spread alignment;
- pair queue applies only to future entries;
- global, pair, and asset capacity gates;
- kill switch blocks entry but preserves natural exit;
- leg lifecycle validates transitions and duplicate events;
- reconciliation surfaces deltas without hidden mutation;
- bounded retry/timeout behavior;
- candidate replacement does not affect open positions;
- shutdown records interrupted state.

### Replace or deepen

- `test_tick_queue.py` has 1,141 lines and verifies many layers through one
  orchestration surface; split by signal, queue, risk, transition, broker, and
  boundary-processing behavior.
- `test_manager.py` has 734 lines coupled to one broad SQLite facade; move to
  state-store contracts plus focused aggregate tests.
- reporting tests rely on synthetic percentage positions; replace with fill,
  cash, fee, funding, and mark fixtures.
- `state_only` order tests prove absence of routing but not paper economics;
  replace with Observe and Paper broker contracts.
- all unit tests remain offline; venue probes are explicit and separately
  selected.

## 15. Quality Audit Findings

### Blockers before Paper

1. Local positions are opened without orders or fills.
2. PnL/equity use signal prices and normalized percentages rather than a cash
   ledger and economic fills.
3. Data failure can become a synthetic `FLAT` signal.
4. Quantity/notional checks operate on values without explicit currency or
   contract units.

### Blockers before Exchange routing

1. Multi-leg partial execution and compensation are incomplete.
2. Ambiguous submission outcome recovery is incomplete.
3. Reconciliation uses local target quantities and invalid local ids as exchange
   identity.
4. Credential tier and execution authorization are conflated.
5. Venue precision, limits, contract size, margin/position mode, and reduce-only
   semantics are incomplete.

### High maintainability findings

1. `trader_runner`, `tick`, `signal_transition`, `reconciliation/service`,
   `pair_queue/ranking`, `pair_validity/refresh`, `manager`, and reporting
   surfaces each mix multiple reasons to change.
2. Domain behavior depends on dict-shaped SQLite rows and legacy artifact rows.
3. Global settings/logger/notifier construction hides external dependencies.
4. Scheduling and delivery concerns live inside the trader package.

## 16. Implementation Slices

### TR0 — Resolve runtime semantics

- Answer blocking questions.
- Freeze routing mode/environment, signal outcome, position, intent, fill, and
  accounting vocabulary.

### TR1 — Observe-mode boundary processor

- Load a typed promoted pair set and closed fixture data.
- Produce typed validity, queue, signal, and risk decisions without positions or
  orders.
- Prove deterministic replay and no mutation.

### TR2 — Transactional state contract

- Define event/idempotency/transaction expectations.
- Implement in-memory and local SQLite adapters.
- Add explicit clock and writer lease.

### TR3 — Order intents and lifecycle

- Persist intent before routing.
- Model legal lifecycle including ambiguous outcomes and immutable fills.
- Add restart/replay tests.

### TR4 — Deterministic paper broker

- Model acknowledgement, partials, rejects, cancels, latency, slippage, fees,
  funding, balance, and outstanding-order restart.
- Derive positions and accounting from fills.

### TR5 — Portfolio and risk

- Convert explicit account currency and pair risk into venue-neutral targets.
- Apply exposure, leverage, concentration, liquidity, and kill-switch gates.
- Prove natural exits under every entry block.

### TR6 — Reconciliation and recovery

- Compare paper/local or exchange/local order, fill, balance, and position truth.
- Block on unresolved deltas and recover ambiguous submissions idempotently.

### TR7 — Operations and reporting integration

- Expose typed commands and read models.
- Keep schedulers, CLI, Telegram, and renderers outside Trading.

### TR8 — Demo exchange routing

- Add Exchange broker adapter only after Paper gates pass.
- Run explicit testnet recovery drills with no production credentials.

### TR9 — Production-capital gate

- Satisfy every production readiness rule.
- Require separate manual authorization and minimal-capital canary.

### TR10 — Consolidate

- Remove legacy facades, dict row APIs, `state_only`, and direct adapter wiring.
- Transfer accepted decisions to canonical docs and delete this guide.

## 17. Questions for Lucas

- **TRQ-001 (blocking):** Accept `local`, `dev`, and `prod` as deployment
  environments; `observe`, `paper`, and `exchange` as routing modes; and `demo`
  or `production` as the separate Exchange account target?
- **TRQ-002 (blocking):** Which account/valuation currency is canonical for the
  first paper vertical?
- **TRQ-003 (blocking):** Is position sizing based on fixed equity fraction,
  volatility target, maximum loss, or another explicit risk budget?
- **TRQ-004 (blocking):** Which exact entry, exit, stop, and maximum holding
  policy crosses from Research into the first promoted specification?
- **TRQ-005 (blocking):** On missing/invalid current data, should existing
  positions hold and alert while new risk is blocked? Recommended: yes.
- **TRQ-006 (blocking before Paper):** What deterministic fill/slippage model is
  sufficient for the first paper broker?
- **TRQ-007:** Can Paper use bar data initially, or must it consume bid/ask/order
  book facts before claiming realistic fills?
- **TRQ-008:** Which fees and funding settlement timing apply to the first market
  profile?
- **TRQ-009:** Is resizing existing positions allowed at all, or are positions
  entry-to-exit fixed-size initially?
- **TRQ-010:** What is the policy after a one-leg fill and other-leg rejection?
- **TRQ-011:** Which reconciliation deltas are automatically recoverable and
  which always require operator review?
- **TRQ-012:** What actions does kill-switch activation authorize: entry block,
  reduce-only, cancel open orders, or liquidation?
- **TRQ-013:** Which datastore adapters are required before cloud deployment?
- **TRQ-014:** How is a single writer elected locally and remotely?
- **TRQ-015:** What exact evidence completes Demo before a small-capital canary?

## 18. Scope Exclusions During Initial Trading Migration

- real-capital routing;
- automatic artifact hot reload;
- auto-rebalancing after research changes;
- portfolio optimization beyond explicit first sizing policy;
- cross-venue arbitrage;
- high-frequency/order-book strategy assumptions;
- UI-specific state models;
- PostgreSQL until the local state contract and paper recovery are proven;
- deployment or scheduling before deterministic local operation.

## 19. Observe Completion Gates

- Same promoted inputs and closed data produce the same decisions.
- Invalid/missing data is unevaluable and cannot create exits or entries.
- No orders, fills, positions, credentials, or network calls exist.
- Validity and queue blocks apply to future entries only.
- All decisions record information cutoff and specification identity.

## 20. Paper Completion Gates

- Orders, fills, positions, cash, fees, funding, and PnL form a consistent ledger.
- Partials, rejects, cancels, latency, slippage, and outstanding-order restart are
  tested.
- Every lifecycle is idempotent and replay-safe.
- Risk uses explicit quantities, currency, contract units, and account equity.
- Natural exits survive pause, artifact replacement, and restart.
- Reconciliation and kill switch are durable and operator-visible.

## 21. Exchange and Production Gates

- Exchange adapter contract, limits, precision, and account units are verified.
- Ambiguous submission and partial-leg recovery drills pass on Demo.
- Unresolved reconciliation fails closed.
- Production credentials are absent from Local, Dev, and Demo-targeted
  configuration.
- Every evidence item in route task `V2-701` is satisfied.
- Production authorization is separate, manual, audited, and uses minimal
  initial capital.
