# Operations Module

## 1. Purpose

The Operations module is the application layer of the platform. It composes
domain modules and adapters into explicit operator-facing use cases without
moving quantitative, risk, artifact, or exchange policy out of their owners.

It coordinates research runs, market-data maintenance, pair-set review and
promotion, trading runtime lifecycle, reconciliation, reports, and safety
commands. The same use cases can be invoked by a local CLI, an HTTP API,
Telegram, a scheduler, or another authorized interface.

Operations is where cross-module workflow belongs. It is not a generic service
layer and does not duplicate behavior already hidden behind a domain interface.

## 2. Responsibilities and Boundaries

### 2.1 Operations owns

- application use cases spanning multiple modules;
- dependency composition and process-scoped resource lifecycle;
- typed command and query contracts for delivery interfaces;
- scheduling policies and overlap control;
- run identity, lifecycle, cancellation, and outcome recording;
- operator authorization checks for sensitive use cases;
- pair-set review and promotion orchestration;
- startup readiness and shutdown coordination;
- notification policy and routing of domain events to delivery adapters;
- application-level health and workflow status projections.

### 2.2 Operations does not own

- statistical calculations or research acceptance;
- candle, dataset, pair, signal, risk, order, fill, or position semantics;
- venue-specific API calls or credential interpretation;
- storage-backend internals;
- CLI flags, Telegram handlers, HTTP routes, or UI rendering;
- deployment manifests, cloud resources, or operating-system supervision;
- business rules hidden in scheduler callbacks.

### 2.3 Dependency direction

```text
interfaces -> operations
operations -> research, pairs, market_data, trading, core
operations -> injected exchange and storage adapters during composition
domain modules never import operations
```

Operations can instantiate concrete adapters at a composition root. A use-case
implementation depends on the narrow capabilities it needs, not on one global
application container.

## 3. Conceptual Components

- **Use cases**: one explicit application action with typed input and result.
- **Wiring**: composition roots that construct configured adapters and domains.
- **Runs**: lifecycle and audit of long- or short-running work.
- **Scheduling**: when a use case is requested and how overlap is controlled.
- **Commands**: authenticated and authorized operator intent.
- **Queries**: stable read models for operational visibility.
- **Monitoring**: application readiness, liveness, freshness, and run status.
- **Notifications**: policy that maps important outcomes to channel-neutral
  messages.

These capabilities may remain together while small. New subpackages require
real behavior and a clear concept owner.

### 3.1 Logical package shape

```text
operations/
├── api.py
├── config.py
├── models.py
├── use_cases/
├── runs/
├── commands/
├── queries/
├── scheduling/
├── monitoring/
├── notifications/
└── wiring/
```

This tree describes application-layer homes, not a framework to scaffold in
advance. A use case may begin as one module and deepen only when its interface
continues to hide meaningful orchestration.

`use_cases` coordinates public domain APIs; `runs` owns application invocation
lifecycle; `commands` and `queries` expose delivery-neutral contracts; and
`wiring` is the only home for composition roots that select concrete adapters.
Scheduling, monitoring, and notifications remain outside domain calculations
and cannot grant exchange authority.

## 4. Use-Case Contract

Every use case has:

- a typed request;
- an authenticated principal or explicit system principal;
- a unique request/idempotency key;
- validated authorization and preconditions;
- injected capabilities;
- a typed result with stable status and failure reason;
- a durable audit record for material state changes;
- explicit cancellation and timeout semantics when long-running.

Use cases do not accept raw YAML dictionaries, environment globals, argparse
namespaces, Telegram updates, or HTTP request objects. Delivery-specific data is
translated before invocation.

Expected domain outcomes are returned as typed results. Unexpected invariant or
infrastructure failures retain their causes and run identity.

## 5. Composition and Configuration

Composition roots:

1. parse external configuration into strict typed settings;
2. validate environment, authorization, and capability combinations;
3. construct clocks, stores, exchange adapters, brokers, and notification
   adapters;
4. invoke one public use case;
5. close resources deterministically.

Domain code never locates config files or reads environment variables. A local
filesystem store, SQLite store, PostgreSQL store, CCXT adapter, or Telegram
channel is selected during composition.

A run records the effective non-secret configuration identity. Secrets are
referenced by scope/version, never included in audit payloads.

## 6. Research Run

The research-run use case coordinates:

```text
validated request
-> acquire/read exact market dataset
-> invoke Research public API
-> persist report and candidate pair set
-> record identities and outcome
```

It does not call Research stages one by one from a scheduler. Research owns its
internal flow and returns one complete result. Operations supplies stores,
clock, paths/backend configuration, and run identity.

Research completion never promotes a candidate automatically unless a separate
explicit promotion policy and authorization exist. The default workflow ends at
candidate publication.

## 7. Market-Data Maintenance

Market-data backfill, refresh, gap repair, validation, and retention are
independent use cases with explicit scopes and dry-run behavior where
destructive changes are possible.

Operations coordinates an Exchange readonly adapter, Market Data service, data
store, clock, and run audit. It does not implement pagination, candle closure,
normalization, or retention calculations.

Partial outcomes name every successful and failed symbol/window. Retrying a run
does not duplicate valid observations or conceal unresolved gaps.

## 8. Pair-Set Review and Promotion

Promotion is a distinct high-integrity use case:

1. identify the exact candidate and expected current promoted version;
2. load its report and validation evidence;
3. verify scope, integrity, compatibility, and freshness policy;
4. authorize the principal;
5. record review reason;
6. execute the Pairs lifecycle transition atomically;
7. publish an outcome notification.

The use case cannot submit exchange orders or alter Trading positions. Rollback
is another promotion event pointing to an immutable older version; it never
rewrites audit history.

## 9. Trading Runtime Lifecycle

Operations starts Trading with fully constructed dependencies and an explicit
deployment environment, routing mode, Exchange target when applicable, and
authorization. It owns process-level
coordination around:

- start requests and duplicate-run prevention;
- readiness and boot failure publication;
- cancellation and graceful shutdown;
- writer-lease acquisition/release;
- restart policy;
- terminal run outcome;
- independent health and kill-switch access.

Trading owns its internal boot, reconciliation, boundary processing, and state
machine. Operations does not reach into Trading repositories to simulate
control.

## 10. Scheduling

A schedule requests a named use case with a typed scope. It contains calendar,
timezone, misfire, jitter, retry, concurrency, and overlap policy.

Schedulers do not contain business logic or import private domain functions.
At-least-once invocation is made safe by use-case idempotency. Long-running work
uses distributed or local leases appropriate to the deployment.

Research, refresh, promotion, and Trading schedules are independent. A research
schedule cannot imply promotion, deployment, or rebalancing.

## 11. Commands and Authorization

Operator commands use stable domain-oriented names such as:

- pause new entries;
- resume new entries;
- activate or inspect kill switch;
- enter reduce-only state;
- cancel a specific order;
- request reconciliation;
- request emergency liquidation;
- promote a pair set;
- stop a runtime process gracefully.

Each command declares required authority, target scope, reason requirements,
expected state/version, and idempotency key. Authentication establishes who the
principal is; Operations authorization establishes what that principal may do.

Emergency liquidation has higher authority and stronger confirmation than
pause or process shutdown. Ambiguous strings such as `stop` are not accepted.

## 12. Queries and Read Models

Queries expose stable delivery-neutral models for:

- research and data-maintenance runs;
- candidate/promoted pair sets and review evidence;
- Trading readiness, health, and run lifecycle;
- queue/validity/risk decisions;
- positions, orders, fills, balances, PnL, and reconciliation;
- configuration identity and active environment;
- audit events and command outcomes.

Queries may compose read projections from multiple owners but do not mutate
state or recalculate quantitative policy. Interfaces never open a database or
artifact file directly.

## 13. Run Lifecycle

A run has an immutable id and explicit states such as requested, starting,
running, cancelling, succeeded, partially succeeded, failed, interrupted, and
timed out.

Run records contain:

- use-case and request identity;
- principal;
- effective configuration hash;
- code version;
- started, heartbeat, and terminal times;
- progress summary and last safe checkpoint;
- produced artifact/dataset ids;
- failure category and sanitized detail;
- parent or trigger identity.

A stale `running` record never proves a process exists. Liveness and persisted
run state are reported separately.

## 14. Concurrency and Idempotency

Every mutating use case defines its idempotency scope. Operations prevents
overlap where concurrent work would corrupt state or publish conflicting
results:

- one writer per Trading account/scope;
- one promoted-pointer transition per scope/version expectation;
- coordinated Market Data writes per dataset partition;
- independently versioned Research runs;
- command claim/complete semantics.

Retries inspect durable outcome before repeating external or destructive work.
Timeout never means failure when the result may be ambiguous.

## 15. Monitoring and Readiness

Operations distinguishes:

- **liveness**: the process can respond;
- **readiness**: the use case may safely accept work;
- **freshness**: required data or heartbeat is recent enough;
- **domain health**: no unresolved safety state blocks intended behavior;
- **run status**: persisted lifecycle of a specific invocation.

Health models contain evidence and timestamps, not only `healthy/unhealthy`.
Monitoring is read-only. It cannot repair, promote, restart, or liquidate as a
side effect.

## 16. Notifications

Domain and application outcomes are mapped to channel-neutral notification
messages with severity, scope, deduplication key, event time, and structured
evidence.

Delivery adapters send those messages to console, email, Telegram, Slack, or
another channel. Notification failure does not roll back a completed domain
transaction, but it is recorded and retried according to policy.

Secrets, full exchange payloads, and unbounded stack traces are excluded.

## 17. Audit

Material operations produce append-only audit events, including:

- principal and authorization decision;
- request and idempotency identity;
- exact target and expected version;
- before/after state identities;
- outcome and reason;
- timestamps from an explicit clock;
- correlation with domain events and external requests.

Application logs are diagnostic output, not the authoritative audit store.

## 18. Error and Retry Semantics

Errors distinguish validation, authentication, authorization, conflict,
not-found, not-ready, domain rejection, partial success, timeout, cancellation,
external unavailable, and internal invariant failure.

Retry policy belongs to the layer that understands idempotency. Operations does
not wrap every exception in generic retries. Exchange and Market Data retain
their own bounded request semantics; Operations retries whole use cases only
when their durable outcome permits it.

## 19. Determinism and Testability

Use-case tests construct fakes/in-memory adapters and prove observable outcomes:

- one Research request produces one auditable candidate result;
- promotion is separate, authorized, and conflict-aware;
- schedules invoke public use cases without containing domain logic;
- retries do not duplicate artifacts, commands, or external mutation;
- Trading start refuses invalid mode/authorization combinations;
- interface choice does not change application behavior;
- monitoring remains read-only;
- notification failure is visible without corrupting domain state;
- cancellation and terminal run state are consistent.

## 20. Safety Invariants

- Operations never bypasses a domain safety decision.
- Research, reporting, monitoring, and promotion cannot mutate an exchange.
- Scheduling cannot grant authorization.
- Credentials do not imply permission to route orders.
- Interfaces cannot reach stores or exchange adapters around Operations.
- Process stop is not position liquidation.
- Every sensitive command is authenticated, authorized, scoped, and audited.
- Real-capital routing remains impossible unless Trading and Exchange production
  gates are satisfied explicitly.
