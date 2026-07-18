# Documentation Index

These documents are the canonical description of the V2 rebuild. The legacy V1
implementation and its historical documentation remain available at tag
`legacy-v1-before-rewrite` and in
`/Users/lucastkacz/Documents/quant-v1-reference`.

## Current Product Status

The active branch contains setup and documentation only. There is no executable
research flow, trader, CLI, deployment, paper broker, or live-capital path.

The active target is a deterministic offline Research V2 flow that produces a
typed, auditable candidate pair-set artifact.

## Document Roles

| Document | Role | Authority |
|---|---|---|
| `.agents/AGENTS.md` | Durable implementation, architecture, environment, testing, and safety rules for agents | Normative working rules |
| `docs/_IMPLEMENTATION_AGENT_GUIDE.md` | Required entrypoint, master prompt, frozen dependency order, and implementation checklist | Normative route; only checkbox transitions are editable |
| `docs/current-roadmap.md` | Active and near-term work | Canonical plan |
| `docs/RESEARCH.md` | Research ownership, components, contracts, mathematics, and runtime behavior | Canonical module documentation |
| `docs/RESEARCH_MIGRATION.md` | Frozen-source inventory, open decisions, completion gates, and implementation sequence | Temporary; delete when Research migration completes |
| `docs/PAIRS.md` | Pair identity, fitted specifications, pair sets, artifact integrity, and lifecycle | Canonical module documentation |
| `docs/PAIRS_MIGRATION.md` | Frozen pair/artifact inventory, corrections, open decisions, and implementation sequence | Temporary; delete when Pairs migration completes |
| `docs/MARKET_DATA.md` | Canonical observations, datasets, validation, synchronization, provenance, and storage behavior | Canonical module documentation |
| `docs/MARKET_DATA_MIGRATION.md` | Frozen data inventory, corrections, open decisions, and implementation sequence | Temporary; delete when Market Data migration completes |
| `docs/EXCHANGE.md` | Venue adapters, capabilities, translation, session, account, order, and safety behavior | Canonical module documentation |
| `docs/EXCHANGE_MIGRATION.md` | Frozen exchange inventory, readonly/mutation phases, open decisions, and gates | Temporary; delete when Exchange migration completes |
| `docs/TRADING.md` | Runtime, eligibility, signals, portfolio, risk, brokers, state, reconciliation, and accounting | Canonical module documentation |
| `docs/TRADING_MIGRATION.md` | Frozen trader inventory, safety corrections, staged implementation, and capital gates | Temporary; delete when Trading migration completes |
| `docs/OPERATIONS.md` | Cross-module use cases, composition, runs, scheduling, commands, queries, and monitoring | Canonical module documentation |
| `docs/OPERATIONS_MIGRATION.md` | Frozen orchestration/CLI inventory, ownership corrections, and implementation sequence | Temporary; delete when Operations migration completes |
| `docs/INTERFACES.md` | CLI, HTTP, Telegram, UI, authentication, DTO, and notification adapter behavior | Canonical module documentation |
| `docs/INTERFACES_MIGRATION.md` | Frozen CLI/Telegram inventory, security corrections, and delivery-adapter sequence | Temporary; delete when Interfaces migration completes |
| `docs/CORE.md` | Minimal clock, settings, errors, correlation, logging, and foundational rules | Canonical module documentation |
| `docs/CORE_MIGRATION.md` | Frozen core/utils inventory, ownership corrections, and foundational migration sequence | Temporary; delete when Core migration completes |
| `ARCHITECTURE_REFACTOR.md` | Rebuild decision, package ownership, and dependency direction | Architecture decision |

## Read By Task

Before any V2 implementation work:

- `.agents/AGENTS.md`
- `docs/_IMPLEMENTATION_AGENT_GUIDE.md`
- select the first eligible unchecked task and follow its required reading;
- do not edit that guide except to check a fully completed task.

Before implementing Research V2:

- `ARCHITECTURE_REFACTOR.md`
- `docs/RESEARCH.md`
- `docs/RESEARCH_MIGRATION.md`
- `.agents/AGENTS.md`
- `docs/current-roadmap.md`

For pair identity, candidate artifacts, or promotion:

- `docs/PAIRS.md`
- `docs/PAIRS_MIGRATION.md`
- `docs/RESEARCH.md` for candidate production
- `docs/TRADING.md` for promoted-set consumption

For Market Data behavior or migration:

- `docs/MARKET_DATA.md`
- `docs/MARKET_DATA_MIGRATION.md`
- `.agents/AGENTS.md`
- `docs/current-roadmap.md`

For Exchange adapters or venue integration:

- `docs/EXCHANGE.md`
- `docs/EXCHANGE_MIGRATION.md`
- `docs/MARKET_DATA.md` for readonly observation contracts
- `.agents/AGENTS.md`, especially before any mutation capability

For Trading runtime, paper behavior, or risk:

- `docs/TRADING.md`
- `docs/TRADING_MIGRATION.md`
- `docs/PAIRS.md`, `docs/MARKET_DATA.md`, and `docs/EXCHANGE.md`
- `.agents/AGENTS.md` and the implementation route's capital gates

For cross-module workflows, commands, or scheduling:

- `docs/OPERATIONS.md`
- `docs/OPERATIONS_MIGRATION.md`
- the canonical documents of every participating domain

For CLI, HTTP, Telegram, UI, or notifications:

- `docs/INTERFACES.md`
- `docs/INTERFACES_MIGRATION.md`
- `docs/OPERATIONS.md`

For clocks, settings, errors, logging, or foundational primitives:

- `docs/CORE.md`
- `docs/CORE_MIGRATION.md`
- `.agents/AGENTS.md`

For package ownership or structural changes:

- `.agents/AGENTS.md`
- `ARCHITECTURE_REFACTOR.md`
- the canonical module document and temporary migration guide for the affected
  owner

Before any future trading, demo, or real-capital work:

- `.agents/AGENTS.md`;
- the production-capital phase in `_IMPLEMENTATION_AGENT_GUIDE.md`;
- `docs/TRADING.md`;
- `docs/TRADING_MIGRATION.md` while that migration remains active;
- `docs/EXCHANGE.md`;
- `docs/OPERATIONS.md` and `docs/INTERFACES.md` for operator safety paths;
- `docs/current-roadmap.md`.

## Documentation Policy

- `_IMPLEMENTATION_AGENT_GUIDE.md` is the only route: agents may only change a
  completed task's checkbox from `[ ]` to `[x]`. Only Lucas may authorize an
  in-place route revision; never create a parallel or version-suffixed guide.
- Distinguish **CURRENT**, **TARGET**, and **LEGACY REFERENCE**.
- Do not copy legacy operational instructions into V2 without re-verifying them.
- Commands enter documentation only after their implementation and arguments are
  tested.
- Keep canonical docs focused on current and near-term behavior; Git stores
  history.
- Planned packages, adapters, and modes must not be described as implemented.
- Update an existing canonical document instead of creating overlapping plans.
- A `*_MIGRATION.md` file is temporary: transfer accepted behavior to the
  canonical module document and delete the migration guide at completion.
