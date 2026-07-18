# Clean Architecture Rebuild

**Status:** accepted architecture decision; setup only, no V2 implementation.

**Active branch:** `refactor/package-architecture`

**Legacy reference:** tag `legacy-v1-before-rewrite`, worktree
`/Users/lucastkacz/Documents/quant-v1-reference`

**Date:** 2026-07-18

## 1. Decision

The project will be rebuilt as a new Python package. The previous implementation
is evidence and reference material, not an API to preserve and not a feature-parity
checklist.

This is intentionally different from an incremental migration:

- V1 remains frozen and recoverable through Git and a separate worktree;
- V2 has one canonical import namespace, `stat_arb`;
- V2 never imports V1;
- code, tests, configs, workflows, and operator instructions are reintroduced
  only when the new implementation actually needs them;
- the first product milestone is a deterministic research flow, not a trader.

The rebuild keeps the safety lessons learned in V1. Research must never mutate
exchange orders or positions, a candidate artifact is not automatically approved
for execution, and no document or package name implies real-capital readiness.

## 2. Repository Layout

```text
quant/
├── pyproject.toml
├── README.md
├── ARCHITECTURE_REFACTOR.md
├── src/
│   └── stat_arb/
├── tests/
├── configs/
└── docs/
```

`src/` is the container for installable Python code. `stat_arb` is the only
top-level Python namespace:

```python
from stat_arb.research import ...
```

Tests, operator configuration, documentation, generated data, and deployment
assets do not belong inside the importable package.

The distribution name will be `stat-arb`; the Python import name will be
`stat_arb`.

## 3. Product Model

The target product has two primary flows separated by an explicit handoff:

```text
RESEARCH FLOW
historical market data
-> explicit universe
-> statistical discovery and validation
-> candidate pair-set artifact
-> operator review and promotion

EXECUTION FLOW — deferred
promoted pair-set artifact
-> trading policy and risk
-> simulated routing
-> exchange routing only after separate readiness gates
```

Research determines which pairs may be considered for future entries. Trading
will eventually decide what to do now with an approved pair set. Research,
reporting, pair recalculation, and artifact inspection cannot submit, modify, or
cancel exchange orders.

## 4. Target Package Map

The long-term namespace may contain:

```text
src/stat_arb/
├── research/
├── pairs/
├── market_data/
├── exchange/
├── trading/       # deferred until Research V2 is stable
├── operations/    # added only when cross-package workflows justify it
├── interfaces/
└── core/
```

This is an ownership map, not a request to create eight empty packages. A
subpackage is created only when concrete behavior gives it a clear concept
owner and a useful interface.

### 4.1 Conceptual Internal Shape

The following tree records the expected homes for known concepts. It is a
navigation map, not the physical tree that must exist on day one. Names marked
as future are created only when their milestone begins.

```text
src/stat_arb/
├── research/
│   ├── api.py
│   ├── config.py
│   ├── models.py
│   ├── universe/
│   ├── discovery/
│   ├── validation/
│   ├── stress/
│   ├── backtest/
│   └── reporting/
├── pairs/
│   ├── api.py
│   ├── models.py
│   ├── identity.py
│   ├── specification.py
│   ├── spread.py
│   └── artifacts/
│       ├── models.py
│       ├── validation.py
│       ├── lifecycle.py
│       ├── promotion.py
│       └── stores/
│           ├── memory.py
│           ├── json_file.py
│           └── object_store.py
├── market_data/
│   ├── api.py
│   ├── config.py
│   ├── models.py
│   ├── validation.py
│   ├── ohlcv/
│   ├── funding/                      # later, when required
│   ├── lifecycle/
│   ├── sync/
│   └── storage/
│       ├── memory.py
│       ├── parquet.py
│       └── database.py
├── exchange/
│   ├── config.py
│   ├── models.py
│   ├── capabilities.py
│   └── adapters/
│       └── ccxt/
│           ├── session.py
│           ├── mapping.py
│           ├── market_data.py
│           ├── account.py
│           └── orders.py
├── trading/                          # deferred
│   ├── api.py
│   ├── config.py
│   ├── models.py
│   ├── runtime/
│   ├── eligibility/
│   │   ├── validity.py
│   │   └── queue.py
│   ├── signals/
│   ├── portfolio/
│   ├── risk/
│   ├── orders/
│   ├── brokers/
│   │   └── paper/
│   ├── state/
│   │   └── adapters/
│   ├── accounting/
│   ├── reconciliation/
│   └── reporting/
├── operations/                       # deferred until justified
│   ├── api.py
│   ├── config.py
│   ├── models.py
│   ├── use_cases/
│   ├── runs/
│   ├── commands/
│   ├── queries/
│   ├── scheduling/
│   ├── monitoring/
│   ├── notifications/
│   └── wiring/
├── interfaces/
│   ├── cli/
│   ├── http/
│   ├── telegram/
│   ├── webhooks/
│   └── notifications/
└── core/
    ├── clock.py
    ├── errors.py
    ├── ids.py
    ├── logging.py
    ├── settings.py
    ├── redaction.py
    └── version.py
```

This shape is deliberately allowed to deepen as behavior appears. For example,
`research/universe.py` may begin as one cohesive module and become
`research/universe/` only after selection policy, manifests, and diagnostics no
longer fit behind a small interface. Folder count is not an architecture goal.

### 4.2 Smallest Physical Shape For The First Vertical

The first implementation should create only the files required by the offline
Research V2 flow:

```text
src/stat_arb/
├── market_data/
│   ├── models.py          # canonical symbol, timeframe, candle, dataset
│   └── validation.py      # closed candles, continuity, finiteness, coverage
├── pairs/
│   ├── models.py          # pair identity and orientation
│   ├── spread.py          # one canonical spread contract
│   └── artifacts/
│       ├── models.py      # typed CandidatePairSet
│       └── json_file.py   # JSON persistence adapter
└── research/
    ├── api.py             # one public research use case
    ├── config.py          # typed research policy
    ├── models.py          # run result and stage evidence
    ├── universe.py        # exact manifest from explicit inputs
    ├── discovery.py       # baseline pair search and cointegration
    ├── validation.py      # temporal validation and acceptance evidence
    └── reporting.py       # report model/rendering seam
```

Test fixtures live under `tests/`, not in the production package. A local
fixture supplies deterministic market data through the same behavior expected
from a future readonly adapter.

This first shape may still shrink during implementation. A file should not be
created merely because it appears in this diagram; it must own concrete
behavior and reduce what callers need to understand.

### `research`

Owns the question:

> Which pairs may be worth trading, under which assumptions and evidence?

It will own universe selection, discovery, statistical validation, stress and
out-of-sample evidence, and research-run reporting. It returns typed results and
candidate pair sets. It does not know how orders are routed.

### `pairs`

Owns the shared language between research and future trading: pair identity,
orientation, canonical spread definition, immutable calibrated parameters,
candidate/promoted pair-set models, artifact validation, and artifact lifecycle.

Research discovers pairs. Future trading acts on promoted pairs. `pairs` owns
the stable contract shared by both.

Its canonical identity, specification, artifact, and lifecycle contract is
`docs/PAIRS.md`.

### `market_data`

Owns venue-independent symbols, candles, funding observations, dataset
validation, closed-candle semantics, continuity, freshness, and local storage
contracts. Neither research nor trading should understand CCXT dictionaries or
recover symbols from filenames.

Its canonical capability and behavior contract is `docs/MARKET_DATA.md`.

### `exchange`

Owns concrete external-venue adapters. During the Research V2 milestone it may
eventually provide readonly market discovery and historical-data access. Order
mutation adapters are out of scope.

Its canonical capability and safety contract is `docs/EXCHANGE.md`.

### `interfaces`

Owns delivery mechanisms such as a CLI and, later, HTTP, Telegram, or a UI
backend. Delivery mechanisms translate input and output; they do not implement
quantitative policy or access persistence directly.

Its canonical delivery, authentication, DTO, command, query, and notification
contract is `docs/INTERFACES.md`.

### `core`

Owns only genuinely foundational primitives such as shared errors or an
explicit clock contract. It must not become a `utils` or `shared` junk drawer.

Its admission rule and foundational capability contract is `docs/CORE.md`.

### `trading` and `operations`

These are valid future owners but are intentionally absent from the first
implementation slice. Their shape will be designed from actual research output
and paper-trading requirements, not copied from V1.

Their canonical behavior and safety boundaries are documented in
`docs/TRADING.md` and `docs/OPERATIONS.md`. Their migration guides remain
planning inputs, not authorization to implement them during Research V2.

## 5. Research V2 Boundary

The first complete vertical is:

```text
typed research configuration
-> deterministic local historical dataset
-> normalized, validated, closed OHLCV
-> exact universe manifest
-> pair discovery
-> canonical spread and cointegration evaluation
-> minimal validation/stress evidence
-> typed CandidatePairSet
-> versioned JSON artifact
-> reproducible report
```

The permanent module behavior and quantitative design live in
`docs/RESEARCH.md`. Open decisions, completion gates, and the source-by-source
implementation sequence live temporarily in `docs/RESEARCH_MIGRATION.md`, which
is deleted when that module migration finishes.

The first vertical is offline. A readonly exchange adapter is introduced only
after the same flow succeeds deterministically with local fixtures.

## 6. Dependency Direction

Target dependency direction:

```text
interfaces  -> operations
operations  -> research, pairs, market_data, trading, core
research    -> pairs, market_data, core
exchange    -> contracts required by market_data
pairs       -> core
market_data -> core
trading     -> pairs, market_data, exchange contracts, core
core        -> standard library and minimal foundational dependencies
```

Forbidden directions:

- research importing future trading implementation;
- pairs or market data importing research orchestration;
- quantitative code importing CLI, Telegram, HTTP, or UI code;
- research importing exchange order mutation;
- domain calculations reading raw YAML or environment variables;
- `core` importing any product package;
- V2 importing files from the V1 worktree.

## 7. Configuration And Operational Seams

Raw YAML or another external format is parsed once at a config boundary into
typed objects. Lower-level modules receive typed values or explicit parameters.

The following concerns enter through operational seams rather than hidden
constants:

- exchange and market profile;
- timeframe and research window;
- filesystem or object-store location;
- clock and generated-at time;
- credentials;
- notification channel;
- persistence backend.

Configuration files will be added only after their typed contract exists.

## 8. Artifact Contract

JSON remains an appropriate persisted representation for small, immutable,
human-inspectable pair-set artifacts. JSON is not the in-process interface.

```text
typed CandidatePairSet
-> JSON adapter
-> versioned JSON document
```

After reading JSON, callers receive validated typed models rather than raw
dictionaries. The candidate artifact must eventually contain schema version,
lifecycle stage, run identity, generation time, universe and data provenance,
statistical assumptions, immutable pair orientation, calibrated parameters,
and a content hash.

Promotion remains an explicit later transition. Producing a candidate does not
authorize trading or alter open positions.

## 9. Composition And Interfaces

Prefer composition for external or replaceable dependencies such as data
providers, artifact stores, clocks, and notification channels. Use simple
functions or cohesive value objects for stateless mathematics.

Do not create inheritance trees, factories, repositories, protocols, or adapter
packages merely to anticipate future needs. A seam becomes concrete when there
is real variation or an external dependency that needs a deterministic test
substitute.

The module interface is the behavior test surface. Internal helper names should
remain private and replaceable.

## 10. Testing Strategy

V1 tests are reference material, not a suite to port wholesale. V2 tests will be
introduced with implementation and organized by behavior:

```text
tests/
├── unit/
├── contracts/
├── integration/
├── online/            # explicitly selected external reads/integrations
└── demo/              # explicitly authorized sandbox/testnet mutation
```

Initial critical invariants include:

- research cannot mutate an exchange;
- candle availability cannot introduce look-ahead;
- canonical symbols survive storage round-trips;
- the spread tested is the spread reported and serialized;
- research results are deterministic for identical inputs;
- artifact JSON round-trips through typed models;
- invalid or incomplete data fails explicitly;
- the deterministic default suite never depends on external availability;
- online and Demo behavior is verified in explicitly selected suites.

Test count is not a quality target. Durable behavior coverage is.

## 11. Rebuild Rules

1. V1 remains frozen in its worktree and Git history.
2. No V1 compatibility imports or facades are added to V2.
3. Before reusing an algorithm, document its inputs, formula, assumptions,
   side effects, known failure modes, and focused behavior test.
4. Port only behavior that remains conceptually correct and useful.
5. Every implementation slice must end in a runnable, verified vertical.
6. Do not pursue feature parity before Research V2 is complete.
7. Do not introduce trading, UI, cloud deployment, PostgreSQL, Telegram, or
   Production Exchange routing during the first research milestone.

## 12. Setup Definition Of Done

- V1 is recoverable by tag and separate worktree.
- The active branch has no V1 production code, tests, configs, workflows, or
  operator runbooks.
- `pyproject.toml` owns package and tool configuration.
- `src/stat_arb` is the only intended import namespace.
- No production Python module has been written yet.
- Canonical docs describe the rebuild honestly.
- The canonical Research specification and active roadmap agree.

## 13. Decisions Deferred

The rebuild does not yet choose:

- statistical extensions and unresolved migration decisions tracked in
  `docs/RESEARCH_MIGRATION.md`;
- a remote data or artifact store;
- a scheduler or workflow engine;
- an HTTP or UI framework;
- Telegram integration;
- a database or ORM;
- paper broker architecture;
- cloud provider;
- order-routing or Production Exchange implementation.

Those decisions must be justified by a concrete milestone rather than included
because V1 happened to contain them.
