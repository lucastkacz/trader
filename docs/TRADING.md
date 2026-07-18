# Trading Module

## 1. Purpose

The Trading module converts approved pair specifications and closed market
observations into auditable portfolio decisions, order intents, fills,
positions, risk state, and natural exits.

It owns the complete runtime state machine from signal evaluation through
reconciliation. The same domain behavior runs against a simulated broker or an
authorized exchange router; changing the router does not change signal, risk,
position, or accounting semantics.

Trading is fail-closed. Missing data, invalid artifacts, ambiguous exchange
outcomes, unresolved reconciliation deltas, or unavailable safety controls
block new risk rather than being interpreted as a flat market.

## 2. Responsibilities and Boundaries

### 2.1 Trading owns

- boot validation and runtime readiness;
- promoted-pair consumption for future entries;
- current pair-validity diagnostics and entry queue policy;
- signal evaluation from closed observations;
- portfolio exposure, capital slots, and sizing;
- pre-trade and continuous risk controls;
- order intents and multi-leg execution coordination;
- paper-broker order, fill, cost, and funding simulation;
- positions, orders, fills, equity, and lifecycle state;
- exchange/local reconciliation and recovery decisions;
- pause, reduce-risk, and kill-switch semantics;
- natural exits under the position's original specification;
- immutable trading events and read models.

### 2.2 Trading does not own

- universe discovery, cointegration selection, or candidate acceptance;
- pair-set serialization or promotion;
- venue-specific payloads, precision rules, or credentials;
- historical dataset synchronization or storage;
- schedules, process supervision, CLI, Telegram, HTTP, or UI behavior;
- infrastructure-specific database choice;
- secret loading or global logging setup.

Research produces candidates. Pairs owns the promoted contract. Trading decides
what may happen now. Exchange translates authorized intents to a venue.
Operations starts and supervises the use cases. Interfaces present queries and
submit operator commands.

### 2.3 Dependency direction

```text
operations -> trading
interfaces -> operations
trading    -> pairs, market_data, exchange contracts, core
exchange   -> venue SDKs and external systems
```

Trading does not import delivery adapters or concrete database implementations
into domain policy. Persistence, clocks, brokers, notifications, and market
observation sources enter through explicit seams.

## 3. Conceptual Components

- **Runtime**: deterministic boot, tick/event processing, shutdown, and
  readiness.
- **Eligibility**: promoted universe, pair validity, ranking, and capacity.
- **Signals**: current spread state and desired exposure transition.
- **Portfolio**: positions, capital slots, sizing, and exposure.
- **Risk**: entry gates, continuous limits, pause, and kill switch.
- **Orders**: durable intents, leg coordination, lifecycle, and recovery.
- **Brokers**: simulated fills or authorized exchange routing.
- **State**: transactional event and projection persistence.
- **Reconciliation**: local/external truth comparison and fail-closed recovery.
- **Reporting**: typed operational and performance read models.

Physical files deepen around these behaviors only when their interfaces remain
smaller than the complexity they hide.

### 3.1 Logical package shape

```text
trading/
├── api.py
├── config.py
├── models.py
├── runtime/
├── eligibility/
│   ├── validity.py
│   └── queue.py
├── signals/
├── portfolio/
├── risk/
├── orders/
├── brokers/
│   └── paper/
├── state/
│   └── adapters/
├── accounting/
├── reconciliation/
└── reporting/
```

The tree is a logical ownership map. It does not authorize Exchange routing or
require every package before the corresponding behavior exists. `api.py` is the
small runtime-facing interface; internal packages hide state machines and
side-effect coordination from callers.

Eligibility can block and rank future entries but cannot own exits. Signals are
pure calculations; orders own durable intents and lifecycle; brokers own Paper
or injected routing behavior; accounting derives economic state from fills;
and state adapters keep SQLite or PostgreSQL outside domain policy. Reporting
owns typed projections, while transport rendering remains in Interfaces.

## 4. Runtime Inputs and Outputs

One runtime instance receives:

- a validated promoted pair-set id and content hash;
- typed strategy and risk policy;
- a declared deployment environment, routing mode, and Exchange target when
  applicable;
- closed-candle and current market-fact providers;
- a broker capability;
- account snapshots when exchange routing is enabled;
- a transactional state store;
- an explicit clock and run identity;
- an operator-command source and event sink.

It produces durable domain events, state projections, order/fill outcomes,
health/readiness snapshots, reconciliation reports, and performance reports.

All input identities are recorded at boot. A process restart must reconstruct
the same effective state from durable facts and fresh external snapshots.

## 5. Deployment Environment, Routing Mode, and Exchange Target

Deployment location, routing behavior, and the external Exchange account target
are separate dimensions.

### 5.1 Deployment environments

- **Local**: workstation development, deterministic replay, Observe, Paper, and
  explicitly selected readonly integrations.
- **Dev**: non-production cloud operation, scheduling, integration, and Demo
  recovery drills.
- **Prod**: production cloud operation. This label alone never authorizes
  exchange mutation.

### 5.2 Routing modes

- **Observe**: compute and persist market observations, diagnostics, signals,
  and decisions without creating orders, fills, or positions.
- **Paper**: create durable intents and simulate order acknowledgements, partial
  fills, fills, rejects, cancels, fees, slippage, funding, and positions.
- **Exchange**: route authorized intents through an Exchange mutation gateway.

### 5.3 Exchange targets

- **Demo**: exchange routing against a testnet, sandbox, or explicitly
  non-capital account.
- **Production**: exchange routing that can affect real capital.

An ambiguous local-only mode is not supported: observing decisions and running
a paper broker are different behaviors, and local positions cannot exist
without economic fills. Every run declares its deployment environment and
routing mode; Exchange runs additionally declare the Exchange target. Invalid
combinations fail at boot.

Production-target routing requires `Prod`, Exchange mode, separate explicit
authorization, and correctly scoped credentials. Credentials never select the
mode or authorize mutation implicitly.

## 6. Boot Sequence

Boot is a state machine, not a constructor side effect:

```text
parse typed configuration
-> validate mode and authorization
-> open and migrate state store
-> acquire single-writer lease
-> load exact promoted pair set
-> restore open position specifications
-> initialize broker and market-data capabilities
-> obtain account/order/position snapshots when applicable
-> reconcile durable and external state
-> verify risk controls and kill switch
-> publish readiness
-> begin event processing
```

New entries remain disabled until every required step succeeds. Existing
positions remain visible and manageable even when the current promoted pair set
no longer contains them.

Boot failure records a typed terminal run outcome and releases resources without
claiming readiness.

## 7. Runtime Processing Model

Trading processes one logical information boundary at a time. For candle-based
strategies, a boundary is the availability of a newly closed candle for the
configured timeframe.

For each boundary:

1. determine the exact information cutoff;
2. fetch shared observations once per instrument;
3. validate freshness, closure, and alignment;
4. refresh runtime diagnostics and queue decisions;
5. evaluate natural exits before new entries;
6. evaluate risk and capacity for proposed entries;
7. create durable intents before external mutation;
8. route or simulate orders;
9. ingest outcomes and reconcile state;
10. mark positions and publish typed snapshots.

The processing key makes replay idempotent. Reprocessing the same boundary does
not duplicate signals, intents, orders, fills, or lifecycle transitions.

## 8. Promoted Pair Consumption

The runtime loads one exact promoted pair-set version for its declared scope.
The pair set defines the approved universe for future entries; Trading must not
apply an undocumented extra Sharpe filter that changes it.

Every position records the immutable pair specification used at entry. When a
new pair set is promoted:

- new entry evaluation uses the new version after an explicit reload boundary;
- removed or changed pairs cannot open under the old version;
- open positions retain their original specification;
- no position is force-closed, resized, or rebalanced solely because promotion
  changed.

## 9. Pair Validity and Entry Queue

Runtime validity measures whether current evidence still resembles the
assumptions under which a promoted pair was accepted. Measurements include:

- artifact and data age in wall time and bars;
- bars since research cutoff and promotion;
- hedge-ratio, spread-distribution, correlation, and cointegration drift;
- half-life drift;
- observed holding-time multiples;
- execution-versus-research behavior;
- missing, stale, or incomplete market data.

Validity produces measurements, threshold evidence, warnings, and entry-block
reasons. It does not rewrite the promoted specification or close a position.

The dynamic queue combines approved-universe membership, current validity,
opportunity evidence, open exposure, and capital-slot policy. Ranking controls
only the order in which future entries compete for capacity. Existing positions
remain eligible for natural exit regardless of queue rank or validity failure.

## 10. Signal Contract

A signal evaluation uses:

- one immutable pair specification;
- aligned closed observations available at the information cutoff;
- current position side;
- an explicit evaluation policy.

For the canonical fitted model:

$$
s_t = \log(P^X_t) - \alpha - \beta\log(P^Y_t),
$$

and a configured causal normalization produces $z_t$. The result includes the
information cutoff, pair/specification id, spread, z-score, desired exposure
state, inputs used, and a stable reason.

Missing or insufficient observations produce `UNEVALUABLE`, not `FLAT`. `FLAT`
means the strategy intentionally desires no exposure based on valid evidence.

Signal evaluation is pure. It cannot persist state, notify an operator, or call
an exchange.

## 11. Exposure Transitions

The desired pair state is explicit: flat, long spread, or short spread. A
transition planner compares desired and actual state and emits zero or more
intents:

- flat to long/short: entry intent;
- long/short to flat: exit intent;
- same side: hold or resize only if an approved policy permits it;
- opposite side: close first, confirm the close, re-evaluate risk, then create a
  separate entry intent.

A flip is never an indivisible optimistic state change. Failure to open the
replacement after closing leaves the pair flat and auditable.

## 12. Portfolio and Sizing

Sizing starts from real account or paper-ledger equity in explicit currency
units. It produces target quantities and notionals for each leg after applying:

- pair risk budget;
- hedge and portfolio weighting policy;
- instrument contract size and multiplier;
- price and quantity precision;
- minimum/maximum order quantity and notional;
- maximum gross and net exposure;
- maximum leverage;
- per-pair, per-asset, cluster, and portfolio limits;
- liquidity and concentration constraints;
- available balance and margin.

Weights, quantities, notionals, percentages, and currency amounts are different
types or carry explicit units. A normalized research weight is never sent to an
exchange as a quantity.

## 13. Risk Controls

Pre-trade risk runs immediately before every new or increased exposure and uses
the latest durable state and market facts. It returns an auditable allow/block
decision with measured values and thresholds.

Continuous controls monitor exposures, drawdown, stale data, reconciliation,
broker health, order age, and operational authorization.

Risk actions are ordered:

- **entry block** prevents new/increased risk;
- **pause** prevents new entries while natural exits remain active;
- **reduce-only** permits only risk-reducing intents;
- **kill switch** blocks new risk and activates an explicit operator-approved
  emergency policy;
- **emergency liquidation** is a separate high-authority workflow, never an
  implicit consequence of recalculation or a generic stop command.

Every risk state is durable and operator-visible. A malformed or unavailable
kill-switch state fails closed for entries.

## 14. Order Intent and Multi-Leg Coordination

An order intent is persisted before submission and contains:

- intent id and idempotency key;
- run, pair-set, specification, position, and signal identities;
- instrument, side, order type, quantity, price constraints, and time-in-force;
- reduce-only and position-mode semantics;
- risk-decision reference;
- deployment environment, routing mode, and Exchange target;
- creation cutoff and lifecycle state.

A spread entry or exit coordinates two leg intents but does not pretend the
venue provides atomic two-leg execution. The coordinator explicitly handles:

- one leg rejected before the other submits;
- one leg filled and the other rejected;
- partial fills;
- timeouts with unknown submission outcome;
- cancel failures;
- quantity drift after precision rounding;
- compensation or operator escalation.

Recovery policy prioritizes bounded risk and truthful state over completing the
original signal at any price.

## 15. Order and Fill Lifecycle

Order state transitions are finite, validated, monotonic where applicable, and
idempotent. They distinguish requested, submitted, acknowledged, partially
filled, filled, cancel requested, cancelled, rejected, failed, expired, and
unknown/ambiguous outcomes.

Fills are immutable economic facts. Cumulative fill quantity cannot decrease,
cannot exceed the accepted order quantity, and includes price, fee, fee asset,
liquidity role, venue ids, and event time.

Position and PnL state derive from fills. An acknowledgement is not a fill, and
a local target is not a position.

## 16. Paper Broker

The paper broker satisfies the same Trading-facing broker contract as exchange
routing. It models:

- order acceptance and rejection;
- deterministic latency;
- market/limit eligibility;
- partial fills and unfilled remainder;
- spread/slippage and liquidity constraints;
- maker/taker fees;
- funding transfers;
- cancel/expire behavior;
- insufficient balance and margin;
- restarts with outstanding orders.

Its clock, fill model, and random seed are explicit. Paper results never use a
theoretical signal price as an automatic fill.

## 17. Positions and Accounting

A spread position aggregates actual filled leg exposure and references its
original pair specification. Lifecycle states distinguish opening, open,
closing, closed, impaired, and reconciliation-required conditions.

Realized and unrealized PnL are computed in explicit valuation currency from
fills, marks, fees, funding, and contract multipliers:

$$
\text{Equity}_t = \text{Cash}_t + \text{RealizedPnL}_t
+ \text{UnrealizedPnL}_t - \text{Fees}_t + \text{Funding}_t.
$$

Accounting does not mix fractional returns with currency amounts. Price marks
record source and time. Reports disclose when marks are stale or unavailable.

## 18. Persistence and Transactions

Trading depends on a state-store contract, not SQLite or PostgreSQL. The store
provides:

- atomic event and projection updates;
- unique idempotency constraints;
- optimistic concurrency or single-writer enforcement;
- schema evolution with explicit ordered versions;
- immutable orders, fills, lifecycle, risk, command, and reconciliation events;
- consistent snapshots for operator queries;
- restart and replay support.

SQLite is a valid local adapter and PostgreSQL a valid remote adapter when each
satisfies the same behavioral contract. Domain code contains no SQL or backend
paths.

## 19. Reconciliation and Recovery

Reconciliation compares local orders, fills, balances, and positions with fresh
broker/account snapshots. Deltas distinguish missing local/external records,
quantity or side mismatches, unexpected positions, stale orders, unknown
submission outcomes, and snapshot failures.

Unresolved material deltas block new entries. The system never fabricates an
exchange position id from a local spread id. Automatic corrective mutation is
limited to explicitly approved, idempotent recovery policies; otherwise the
runtime enters reduce-only or operator-review state.

After a timeout during submission, recovery queries by client order id before
any retry. Blind resubmission is forbidden.

## 20. Commands and Operator Control

Trading accepts authenticated, authorized domain commands through Operations.
Commands have ids, requested/authorized times, principal, reason, expected
state version, lifecycle status, and result.

Pause/resume, kill-switch activation, cancel, and liquidation are distinct
commands with different authority. Commands are claimed and completed
idempotently. A delivery adapter writing arbitrary strings into a database is
not the command interface.

## 21. Reporting and Observability

Trading exposes typed read models for:

- readiness and health;
- current promoted pair-set identity;
- queue and validity decisions;
- positions, orders, fills, and reconciliation deltas;
- risk state and blocked decisions;
- cash, exposure, equity, PnL, fees, and funding;
- run lifecycle and last successful information boundary;
- per-pair and portfolio performance.

Renderers do not query internal repositories or recompute business metrics.
Logs support diagnosis but do not replace the durable event ledger.

## 22. Shutdown and Restart

Shutdown stops accepting new work, records interruption intent, allows bounded
in-flight persistence, releases the writer lease, and publishes a terminal run
state. It does not liquidate positions implicitly.

Restart restores outstanding intents/orders, original position specifications,
risk controls, and last processed boundary before reconciling. Processing
resumes only after readiness succeeds.

## 23. Error Semantics

Errors distinguish invalid configuration, unavailable data, unevaluable
signals, blocked risk, persistence conflict, broker rejection, ambiguous
submission, partial execution, reconciliation mismatch, stale state,
authorization failure, and invariant violation.

Expected business outcomes such as risk blocks or order rejects are typed
results, not generic exceptions. Unexpected invariant violations stop the
affected workflow and preserve evidence.

## 24. Determinism and Testability

Offline behavior tests use explicit clocks, fixture market data, in-memory or
temporary state stores, and deterministic paper brokers. They prove:

- no routing occurs in Observe;
- Paper creates economic fills rather than synthetic local positions;
- signals use only available closed observations;
- retries and replays do not duplicate intents or fills;
- risk and capital-slot decisions are enforced;
- invalid pair/data state fails closed;
- pair replacement affects future entries only;
- pause and validity failures preserve natural exits;
- partial-leg and ambiguous-order recovery is bounded;
- reconciliation blocks unsafe continuation;
- restart reproduces durable state;
- Exchange/Production mutation requires explicit authorization.

## 25. Safety Invariants

- Trading is the only domain owner allowed to request exchange mutation.
- Exchange mutation occurs only through an explicit gateway and authorization.
- Research, reporting, promotion, and delivery interfaces cannot route orders.
- No local target, signal, or acknowledgement is treated as a fill.
- PnL and equity derive from economic facts in explicit units.
- Pair recalculation never force-closes or rebalances open positions.
- Natural exits remain evaluable through pause, artifact replacement, and
  restart.
- Unresolved material reconciliation or ambiguous submission blocks new risk.
- A kill switch is durable, tested, and accessible independently of the primary
  UI.
