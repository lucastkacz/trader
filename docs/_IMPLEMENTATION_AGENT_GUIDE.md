# V2 Implementation Agent Guide

**Purpose:** permanent entrypoint for every implementation chat and frozen
dependency-ordered checklist for the V2 rebuild.

## Immutability Contract

This document is intentionally frozen after its initial acceptance.

Agents may make exactly one kind of edit here: replace the two characters
`[ ]` with `[x]` on one existing route-task line.

That checkbox transition is allowed only after the whole task satisfies the
completion rule below. Agents must not add, remove, rename, reorder, split,
merge, rewrite, annotate, date, or uncheck tasks. They must not edit any other
text in this file.

A blocker leaves the checkbox unchecked. The blocker and any accepted decision
belong in the relevant migration guide, canonical module documentation, or
`docs/current-roadmap.md`, never as a note here.

If this route becomes materially wrong, stop. Only Lucas may explicitly
authorize an in-place revision. Never create a second or version-suffixed
implementation guide.

## Authority and Document Roles

Use this order when sources disagree:

1. Lucas's explicit instruction for the current task.
2. Durable implementation and safety rules in `.agents/AGENTS.md`.
3. The ordering and completion state in this guide.
4. Canonical behavior, ownership, and dependency direction in the relevant
   module documents.
5. `docs/current-roadmap.md` for current status and near-term scope.
6. The relevant temporary `*_MIGRATION.md` guide for source inventory, open
   decisions, detailed slices, and completion gates.
7. V1 as historical evidence only.

Canonical module documents explain the accepted system. Migration guides hold
temporary questions and implementation detail, and are deleted at their stated
completion gate. The roadmap may evolve as work advances. This guide does not.

## Master Prompt for a New Implementation Chat

Give the agent this file, or tell it to begin here. The following prompt governs
the implementation session:

```text
You are implementing the V2 statistical-arbitrage platform in this repository.

Read docs/_IMPLEMENTATION_AGENT_GUIDE.md completely before changing anything.
Select the first unchecked task in route order whose predecessors are complete.
By default, complete one route task in this chat/change; do more only when Lucas
explicitly asks.

Before designing or coding:
1. Read .agents/AGENTS.md, docs/current-roadmap.md, and docs/index.md.
2. Read the canonical module documents and temporary migration guides named by
   the selected route task.
3. Inspect the current V2 tree, tests, configuration, and git diff. Preserve all
   unrelated user work.
4. Inspect only the relevant implementation, tests, configs, and artifacts in
   /Users/lucastkacz/Documents/quant-v1-reference.

V1 is evidence, not an API or code dependency. Do not import it, copy its shape
automatically, preserve compatibility by default, or pursue feature parity.
Understand the behavior, retain what is sound, and correct documented defects.

Implement the smallest cohesive behavior that passes the selected task's exit
gate. Prefer composition over inheritance for application behavior. Pydantic or
other framework base models are not the inheritance problem by themselves.
Keep domain math, I/O, orchestration, state mutation, and rendering separate
when they have distinct reasons to change. Add a protocol/adapter seam only for
a real external dependency or when two useful implementations prove the seam.
Do not scaffold future folders merely because they appear in architecture docs.

Use typed configuration at entrypoints. Do not leak raw YAML dictionaries,
paths, exchanges, timeframes, clocks, credentials, or storage assumptions into
domain logic. Research, reporting, pair recalculation, and promotion must never
mutate exchange state. Pair-set replacement affects future entries only and
must preserve natural exit for already-open positions.

Resolve blocking decisions with Lucas; never treat a migration guide's
recommended answer as authorization. Record accepted behavior in the canonical
module document and keep temporary migration detail in its migration guide.
Update docs/current-roadmap.md when the active milestone materially advances.

Test complete behavior through public interfaces and protect material financial
invariants. The default suite must be deterministic; explicitly marked online
and Demo integration tests may use external systems when the selected gate
requires them. Run every configured, relevant test, lint, packaging, and static
check. A file, class, or test existing is not completion; the behavior and exit
gate must pass.

Only after the completion rule in this guide is satisfied, change the selected
line from [ ] to [x]. Make no other edit to this guide. In the final handoff,
report the task ID, behavior delivered, important design decisions, files
changed, verification run, and the next unchecked task or concrete blocker.
```

## Completion Rule for Every Checkbox

A task may be checked only when all of the following are true:

- its complete behavior exists, not just scaffolding or types;
- every referenced slice exit gate and applicable module completion invariant
  passes;
- focused behavior tests exist and pass through public interfaces;
- all configured relevant lint, packaging, static, deterministic acceptance, and
  test checks pass, including online or Demo suites when the task requires them;
- dependency direction, import side effects, configuration, and safety rules
  remain valid;
- canonical docs describe the accepted behavior and the roadmap reflects the
  actual active milestone;
- no unresolved decision can change the meaning of the delivered behavior; and
- the change contains no unrelated rewrite or speculative future package.

Deletion/consolidation tasks additionally require transferring accepted facts
to permanent docs before deleting the named migration guide. Git preserves the
migration history.

## Frozen Implementation Route

The order below is a dependency spine, not a demand to build every conceptual
folder in advance. A task's detailed work and gate live in the named migration
slices. Later phases are not authorization to start them early.

### 0. Accepted V2 foundation

- [x] V2-000 — Establish the clean `stat_arb` rebuild, module ownership docs,
  migration guides, consolidated agent rules, architecture decision, and frozen
  V1 reference.

### 1. Deterministic offline Research V2

Read `RESEARCH.md`, `RESEARCH_MIGRATION.md`, `MARKET_DATA.md`,
`MARKET_DATA_MIGRATION.md`, `PAIRS.md`, `PAIRS_MIGRATION.md`, `CORE.md`, and
`CORE_MIGRATION.md` for this phase.

- [ ] V2-101 — Resolve Research M0 plus the shared MD0/PR0 decisions and freeze
  one executable offline acceptance story without silently accepting defaults.
- [ ] V2-102 — Implement MD1 canonical closed-observation behavior and its pure
  validation contract with deterministic fixture tests.
- [ ] V2-103 — Implement MD2 validated dataset identity, quality/provenance, a
  semantic hash, and an in-memory storage contract.
- [ ] V2-104 — Implement PR1 canonical instrument/pair identity, orientation,
  and one complete fitted-spread specification contract.
- [ ] V2-105 — Complete Research M1 typed config, temporal plan, stage outcomes,
  rejection evidence, and the integrated cross-module fixture contract; enforce
  Core CO0's admission and dependency rule before shared primitives appear.
- [ ] V2-106 — Implement Research M2 so every consumer uses one intercept-aware,
  orientation-specific canonical fitted spread.
- [ ] V2-107 — Implement Research M3 explicit cointegration, residual ADF,
  half-life, hypothesis-family accounting, and multiple-testing behavior.
- [ ] V2-108 — Implement Research M4 exact universe manifests and deterministic
  discovery without ambient path scans or network access.
- [ ] V2-109 — Implement Research M5 causal formation, validation, embargo or
  warm-up, and final out-of-sample boundaries with a frozen model.
- [ ] V2-110 — Implement Research M6 causal pair backtesting with explicit
  holdings, next-event fills, turnover, costs, funding semantics, and net/gross
  evidence.
- [ ] V2-111 — Implement Research M7 and Pairs PR2 typed candidate acceptance,
  stress response surfaces, stability gates, and machine-readable rejection
  reasons.
- [ ] V2-112 — Implement Pairs PR3 deterministic versioned JSON persistence,
  canonical bytes/hash, atomic publication, and corruption/collision tests.
- [ ] V2-113 — Implement Research M8 and Pairs PR5 as one public offline API that
  returns and persists a typed candidate plus a reproducible report; admit only
  the Core CO1/CO5 clock and build primitives proven by this vertical.
- [ ] V2-114 — Pass every Research completion gate, reconcile permanent docs,
  roadmap and index, remove obsolete tests/scaffolding, and complete M9 by
  deleting `RESEARCH_MIGRATION.md`.

### 2. Real readonly Market Data

Read `MARKET_DATA.md`, `MARKET_DATA_MIGRATION.md`, `EXCHANGE.md`, and
`EXCHANGE_MIGRATION.md`. This phase has no private account reads, credentials,
or order mutation.

- [ ] V2-201 — Implement MD3 local persistent storage behind the proven dataset
  contract with collision-safe identity and validated atomic publication.
- [ ] V2-202 — Complete EX0 and EX1 for one explicit venue/market profile using
  provider payload fixtures, capability/error semantics, and deterministic
  session ownership.
- [ ] V2-203 — Implement EX2's minimum public readonly adapter and prove raw
  provider payloads cannot escape into Market Data or Research.
- [ ] V2-204 — Implement MD4 bounded, progressive, cutoff-safe, idempotent
  backfill with observable per-symbol and partial outcomes.
- [ ] V2-205 — Implement MD5 overlap refresh, source-revision handling,
  interior-gap detection/repair, and recomputed quality evidence.
- [ ] V2-206 — Complete MD7 and EX3: the same Market Data contract passes for
  fakes and normalized exchange fixtures; any live probe is bounded, opt-in,
  readonly, redacted, and excluded from default tests.
- [ ] V2-207 — Implement MD6 freshness and provenance-safe lifecycle behavior
  required by actual local consumers, including dry-run destructive actions.
- [ ] V2-208 — Pass all Market Data completion gates, transfer accepted behavior
  to permanent docs, complete MD8, and delete `MARKET_DATA_MIGRATION.md`.

### 3. Manual operation and candidate promotion

Read `PAIRS.md`, `PAIRS_MIGRATION.md`, `OPERATIONS.md`,
`OPERATIONS_MIGRATION.md`, `INTERFACES.md`, `INTERFACES_MIGRATION.md`, `CORE.md`,
and `CORE_MIGRATION.md`.

- [ ] V2-301 — Implement Pairs PR4 immutable versions, promoted pointer, audit
  history, compare-and-set promotion, conflicts, and rollback-as-new-event.
- [ ] V2-302 — Complete Operations OP0 vocabulary, authority, command/query, and
  principal/permission decisions for local workflows.
- [ ] V2-303 — Implement OP1 and OP4 local Research composition, typed run
  lifecycle, audit, liveness/readiness distinction, and terminal outcomes.
- [ ] V2-304 — Implement OP2 typed backfill, refresh, and gap-repair use cases
  with idempotent retry and observable partial outcomes.
- [ ] V2-305 — Implement OP3 and Pairs PR6 explicit, authenticated, audited,
  conflict-aware manual candidate review and promotion.
- [ ] V2-306 — Complete Interfaces IF0 and IF1 with one local CLI over Operations,
  stable human/JSON results, explicit exit codes, and no direct store access.
- [ ] V2-307 — Complete IF2 Research run, candidate inspection, and promotion
  commands only through the mature Operations APIs.
- [ ] V2-308 — Complete the remaining Core CO2-CO4 capabilities now justified by
  real callers—strict entrypoint settings, side-effect-free logging, and minimal
  correlation/errors—and reverify all CO0-CO5 gates.
- [ ] V2-309 — Pass the complete deterministic local Research-to-manual-promotion
  acceptance path and Core gates; complete CO6 and delete
  `CORE_MIGRATION.md`.

### 4. Observe and deterministic Paper Trading

Read `TRADING.md`, `TRADING_MIGRATION.md`, `PAIRS.md`, `PAIRS_MIGRATION.md`,
`OPERATIONS.md`, and `OPERATIONS_MIGRATION.md`. Production credentials and
exchange mutation remain forbidden throughout this phase.

- [ ] V2-401 — Complete TR0 runtime vocabulary and decisions for deployment
  environment, Observe/Paper/Exchange routing, Demo/Production exchange target,
  signals, positions, intents, fills, and accounting.
- [ ] V2-402 — Implement TR1 deterministic Observe processing from an exact
  promoted pair set and closed data, with typed validity, queue, signal, and
  risk decisions and zero trading mutation.
- [ ] V2-403 — Implement TR2 transactional state with explicit events,
  idempotency, clock, single-writer lease, and interchangeable in-memory/local
  adapters.
- [ ] V2-404 — Implement TR3 persist-before-route order intents, legal lifecycle,
  immutable fills, ambiguous outcomes, replay, and restart behavior.
- [ ] V2-405 — Implement TR4 deterministic stateful Paper brokerage with fills,
  partials, rejects, cancels, latency, slippage, fees, funding, balances, and
  outstanding-order restart.
- [ ] V2-406 — Implement TR5 portfolio/risk policy with explicit units, exposure,
  leverage, concentration, liquidity, entry blocks, and kill-switch behavior.
- [ ] V2-407 — Implement TR6 fail-closed reconciliation and idempotent recovery
  for orders, fills, balances, positions, and ambiguous submissions.
- [ ] V2-408 — Implement TR7, Operations OP5/OP6, and Pairs PR7 typed commands,
  read models, composition, and the Trading consumer contract; prove artifact
  replacement affects future entries while natural exit survives pause,
  replacement, and restart.
- [ ] V2-409 — Pass every Observe and Paper completion gate in deterministic
  local acceptance and complete Pairs PR8 by deleting `PAIRS_MIGRATION.md`.

### 5. Automation and operator safety paths

Read `OPERATIONS.md`, `OPERATIONS_MIGRATION.md`, `INTERFACES.md`,
`INTERFACES_MIGRATION.md`, and `.agents/AGENTS.md`.

- [ ] V2-501 — Implement OP7 scheduling only over deterministic public use cases,
  with leases, idempotency, explicit cancellation, and no embedded domain logic.
- [ ] V2-502 — Implement IF3 channel-neutral notifications and the first required
  delivery adapter with bounded failure behavior, durable outcome, redaction,
  and offline fake-adapter tests.
- [ ] V2-503 — Close the remote readonly decision: implement the justified IF4
  adapter only through Operations, or record in permanent docs why CLI plus
  notifications satisfies the approved operating model.
- [ ] V2-504 — Deliver authenticated, authorized, idempotent, and audited
  pause/resume and kill-switch actions through the approved operator paths,
  while preserving an independent local emergency path; this covers IF5 without
  authorizing liquidation.
- [ ] V2-505 — Close IF6 from actual use cases: implement a versioned HTTP/UI
  adapter only if justified, otherwise record its explicit deferral in permanent
  docs without speculative framework scaffolding.

### 6. Demo Exchange integration and recovery

Read `EXCHANGE.md`, `EXCHANGE_MIGRATION.md`, `TRADING.md`,
`TRADING_MIGRATION.md`, and `.agents/AGENTS.md`. Credentials must target an
exchange Demo account and must not authorize Production.

- [ ] V2-601 — Implement EX4 private readonly account snapshots only after the
  Trading reconciliation contract exists, preserving units and fail-closed
  malformed/missing outcomes.
- [ ] V2-602 — Implement EX5's narrow order-mutation gateway with precision,
  limits, client identity, reduce-only/position mode, distinct outcomes, and
  lookup/reconcile-before-retry semantics proven offline.
- [ ] V2-603 — Implement TR8 Demo routing through the Exchange broker adapter,
  with authorization independent of credential presence and no Production
  credential path.
- [ ] V2-604 — Complete EX6 bounded Demo recovery drills for partial legs,
  ambiguous submissions, disconnects, restart, reconciliation, kill switch, and
  audit; treat this as integration evidence, not alpha evidence.
- [ ] V2-605 — Pass Exchange readonly and mutation completion gates, complete
  EX7, transfer permanent operator behavior, and delete
  `EXCHANGE_MIGRATION.md`.

### 7. Production-capital gate

This phase is never implied by prior checkboxes. It requires Lucas's separate,
explicit authorization and every capital gate in `TRADING_MIGRATION.md`.

- [ ] V2-701 — Assemble and verify the production-readiness evidence: offline
  tests/checks, strict config, risk limits, kill switch, reconciliation, complete
  order audit, scoped secrets, observability, quantitative evidence, Paper
  soak, and Demo recovery, with every remaining gap fail-closed.
- [ ] V2-702 — Obtain Lucas's explicit, audited authorization for a precisely
  bounded minimal-capital canary, including venue/account, capital, duration,
  loss/stop limits, credentials, monitoring, rollback, and responsible operator.
- [ ] V2-703 — Run and review the authorized canary without expanding its scope;
  reconcile every order/fill/position and close all safety or operational
  findings before any continued Production use.
- [ ] V2-704 — Complete TR9 only after all readiness and canary evidence passes;
  keep any capital increase a separate future authorization rather than an
  automatic consequence of this checkbox.

### 8. Migration closure

- [ ] V2-801 — Complete TR10, OP8, and IF7; transfer accepted behavior to
  permanent docs, remove obsolete facades/scaffolding, and delete
  `TRADING_MIGRATION.md`, `OPERATIONS_MIGRATION.md`, and
  `INTERFACES_MIGRATION.md` after their individual gates pass.
- [ ] V2-802 — Reconcile agent rules, architecture, module/operator docs,
  documentation index, and current roadmap with verified behavior; confirm no
  permanent document depends on a deleted migration guide and every required
  deterministic, online, or Demo suite has the expected result.

## What “Ready to Implement” Means Now

The repository is ready to begin implementation when this guide exists and the
foundation task is checked. It is not yet ready to run a bot or trade.

The first implementation chat starts at `V2-101`. Its job is to inspect the
relevant V1 evidence, present the genuinely blocking decisions to Lucas, and
freeze one concrete offline acceptance story. It must not begin by implementing
all of Core, scaffolding the full package tree, contacting an exchange, or
creating a trading runtime.
