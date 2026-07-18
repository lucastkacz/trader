# Repository Agent Rules

These are the durable implementation rules for every human or AI agent working
on this Python statistical-arbitrage platform. This file deliberately does not
describe the current milestone or implementation status.

## Sources of Truth

Use each document for one purpose:

- `docs/_IMPLEMENTATION_AGENT_GUIDE.md` defines task order and completion state.
- `docs/current-roadmap.md` describes what matters now and next.
- `ARCHITECTURE_REFACTOR.md` defines package ownership and dependency direction.
- Canonical module documents under `docs/` define accepted domain behavior.
- Temporary `*_MIGRATION.md` guides contain V1 inventories, open decisions, and
  slice-specific gates; delete each one when its migration completes.
- Current code and behavior tests prove what is actually implemented.
- `/Users/lucastkacz/Documents/quant-v1-reference` is historical evidence only.

Do not repeat changing project status in this file. When sources disagree in a
way that changes financial meaning, persisted contracts, external side effects,
or task scope, stop and ask Lucas instead of choosing silently.

## Required Workflow

Before changing production behavior:

1. Read `docs/_IMPLEMENTATION_AGENT_GUIDE.md` and select the first eligible
   unchecked task unless Lucas explicitly narrows the work to review or docs.
2. Read the current roadmap and only the canonical/migration documents owned by
   the affected modules.
3. Inspect current code, tests, config, call sites, and `git diff` before
   designing the change.
4. Inspect only the relevant V1 implementation, tests, configs, and artifacts.
5. Resolve blocking financial or product decisions with Lucas; recommended
   migration defaults are hypotheses, not authorization.
6. Implement the smallest cohesive behavior that satisfies the route task.
7. Verify through public behavior, update canonical docs and roadmap when their
   truth changes, and only then mark the route checkbox.

Never import V1, add it to `PYTHONPATH`, preserve its interfaces automatically,
or pursue feature parity without an explicit requirement. Retain sound behavior
and correct documented defects rather than copying file shapes.

## Durable Product Boundaries

- Research may read historical or readonly market data and produce candidate
  evidence. It never creates, modifies, or cancels exchange orders.
- Promotion is an explicit, audited transition outside Research. A candidate is
  not approved merely because Research produced it.
- Trading consumes an exact promoted pair-set version and owns signals,
  positions, risk, order intents, fills, accounting, and reconciliation.
- Pair recalculation or pair-set replacement affects future entries only. It
  must not rebalance, reinterpret, or force-close an open position.
- Every open position retains the fitted specification required for its natural
  exit across pause, artifact replacement, and restart.
- Reporting, inspection, validity diagnostics, and health queries are readonly.
- Operations composes cross-module use cases. Interfaces call Operations and do
  not open domain stores or exchange adapters directly.
- Core admits only primitives with multiple real consumers. It never becomes a
  `utils`, `common`, or product-policy package.

## Architecture and Code Shape

- Give each concept one owner and one canonical import path.
- Prefer deep modules: a small public interface should hide meaningful behavior
  and reduce what callers must know.
- Separate pure mathematics, external I/O, state mutation, orchestration, and
  rendering when they have different reasons to change.
- Prefer composition for application behavior. Use inheritance only when the
  subtype relationship is real and useful; framework inheritance such as
  Pydantic `BaseModel` is not itself a design smell.
- Use functions for stateless transformations and classes for stateful
  collaborators or stable value concepts.
- Add a protocol or adapter seam for a real external dependency or when useful
  interchangeable implementations prove the seam. Do not build speculative
  factories, repositories, or abstraction ladders.
- Avoid pass-through wrappers, broad compatibility facades, duplicate models,
  and catch-all modules.
- Do not create folders or files merely because they appear in an architecture
  diagram. Physical structure follows cohesive implemented behavior.
- Use type hints for production interfaces and explicit error outcomes at
  module boundaries.

Operational paths, exchanges, timeframes, clocks, credentials, stores,
notification channels, and runtime policies enter through typed config,
explicit parameters, or adapters. Domain logic must not hardcode them.

## Pydantic and Domain Types

Use Pydantic at validation boundaries:

- typed configuration and settings;
- commands, queries, and external API DTOs;
- persisted artifacts and schema-versioned payloads;
- provider payload normalization when strict validation adds value.

Use `extra="forbid"` for owned configuration and fail precisely on missing or
unknown operational fields. Do not use Pydantic for every internal record or in
numeric hot paths. Dataclasses, enums, NumPy arrays, pandas objects, and simple
typed values are preferable when runtime validation is unnecessary.

JSON, YAML, database rows, and provider dictionaries are adapter formats, not
domain interfaces. Convert them at the edge and do not pass raw mappings through
the system.

## Configuration and Environments

Configuration is parsed once at an entrypoint into strict typed objects. Domain
modules never locate YAML files, read environment variables, construct global
settings, or use `.get("key", default)` for config-origin values. Defaults are
acceptable only for non-operational values whose meaning is unambiguous.

Keep algorithm implementation in code. Put strategy policy, thresholds,
timeframes, storage choices, environment selection, and operational limits in
typed configuration when a real use case needs variation. Do not make every
internal constant configurable.

Deployment environment and trading behavior are independent axes:

```text
environment = local | dev | prod
routing_mode = observe | paper | exchange
exchange_target = demo | production
```

- `local` is the workstation environment for development, deterministic flows,
  replay, Observe, Paper, and explicitly selected readonly integrations.
- `dev` is non-production cloud infrastructure for scheduling, integration,
  recovery drills, and exchange Demo accounts.
- `prod` is production cloud infrastructure. Running there does not authorize
  exchange mutation or imply that `routing_mode=exchange`.
- `exchange_target` applies only to Exchange routing and identifies the external
  account/venue target; it is not a deployment environment.

Invalid combinations fail at boot. Production exchange mutation requires
`environment=prod`, `routing_mode=exchange`, `exchange_target=production`, the
corresponding completed implementation-route gate, correctly scoped
credentials, and Lucas's explicit authorization. No single field or available
secret grants that authority.

Secrets stay outside versioned strategy config, are loaded through typed
settings at composition, and must never appear in logs, reports, exceptions, or
test snapshots.

## Numerical and Data Processing

- Prefer vectorized pandas/NumPy operations for historical transformations,
  returns, indicators, rolling calculations, and matrix work.
- Avoid row-by-row DataFrame iteration for numerical pipelines.
- Use loops when they model state machines, event order, positions, pairs,
  bounded pagination, retries, or order lifecycle more clearly.
- Do not force vectorization when it obscures causal ordering or auditability.
- Measure representative workloads before introducing complexity for speed.
- Make information cutoffs, temporal windows, seeds, units, and missing-data
  behavior explicit. Never hide look-ahead, silent row loss, or unit conversion.
- Long numeric work inside async code must not block the event loop.

## Testing Strategy

Prefer fewer high-value tests over a large suite coupled to implementation
details. Test public behavior, financial invariants, external contracts, and
failure recovery. Do not write trivial tests for framework behavior, getters,
or arithmetic already guaranteed by a dependency.

The primary test layers are:

1. **Vertical acceptance:** run a complete public use case with representative
   fixtures and real local adapters such as temporary files, Parquet, or SQLite.
2. **Quantitative invariants:** focused synthetic examples for orientation,
   look-ahead, causal fills, hedge holdings, FDR, costs, funding, and PnL.
3. **Contract tests:** run one behavior suite against in-memory/local adapters,
   captured provider payloads, and external adapters when selected.
4. **Scenario and recovery:** invalid/incomplete data, interruption, restart,
   partial fills, rejects, timeouts, gaps, corruption, and ambiguous outcomes.
5. **Online integration:** explicit network tests for real readonly providers or
   delivery channels.
6. **Demo integration:** explicit tests allowed to mutate only an authorized
   sandbox/testnet account with Dev-scoped credentials.

Network access is allowed in explicitly marked online or Demo tests. The
default suite must be deterministic and must not depend on uncontrolled
external availability. Production mutation is never an ordinary test.

Prefer faithful fakes, captured payloads, and real temporary local persistence
over extensive mocking. Mock only a narrow external edge or failure that cannot
be reproduced faithfully. Tests must use timeouts and bounded progress; stop and
report a design blockage if a test loops without progress.

## External Mutation and Operational Safety

- Public market-data reads may use the network when the selected workflow or
  test explicitly owns that integration.
- Demo exchange mutation belongs only behind Trading, an Exchange adapter, Demo
  credentials, explicit authorization, and Demo-marked tests/workflows.
- Production exchange mutation belongs only behind the production-capital route
  gate and an independently authorized run.
- An ambiguous submission is reconciled or looked up before any retry.
- Risk blocks may prevent new exposure but must not silently remove natural
  exits or corrupt accounting.
- Kill-switch, reconciliation, order lifecycle, and audit behavior must be
  independently observable before they can support real capital.

## Change Discipline and Completion

- Preserve unrelated user work and never reset, revert, or delete it to simplify
  a task.
- Avoid broad rewrites inside a behavior slice. Refactor only what the selected
  behavior requires or what creates a demonstrated safety/maintainability block.
- Do not add migration wrappers or duplicate canonical import paths.
- Keep generated artifacts, credentials, local databases, and logs out of Git.
- Update tests and canonical docs when production behavior changes.
- Run every relevant configured format, lint, package, static, local acceptance,
  and test check. Run online/Demo suites when the task's gate requires them.
- A task is complete only when behavior exists, its exit gate passes, docs match
  reality, and no unresolved decision can change its meaning.
- Final handoffs name the route task, delivered behavior, decisions, changed
  files, verification, and the next task or blocker.

Only the existing checkbox of a fully completed route task may be changed in
`docs/_IMPLEMENTATION_AGENT_GUIDE.md`. No agent may add, remove, reorder, or
rewrite route tasks unless Lucas explicitly authorizes an in-place route
revision. Never create a parallel implementation guide.
