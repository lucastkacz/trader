# Operations Migration Guide

> **TEMPORARY DOCUMENT**
>
> This guide maps frozen orchestration, command, monitoring, and CLI behavior
> into the Operations application layer. Delete it after migration and retain
> accepted behavior in `docs/OPERATIONS.md`.

## 1. Purpose and Authority

Frozen evidence lives at tag `legacy-v1-before-rewrite` and in
`/Users/lucastkacz/Documents/quant-v1-reference`. Prefect flows, CLIs, daemon
launches, and state commands are reference behavior, not target interfaces.

Authority order:

1. Lucas's explicit instruction for the current task.
2. `.agents/AGENTS.md` for durable implementation and safety rules.
3. `docs/_IMPLEMENTATION_AGENT_GUIDE.md` for route order and completion state.
4. `ARCHITECTURE_REFACTOR.md` and the relevant canonical module documents.
5. `docs/current-roadmap.md` for current status and near-term scope.
6. This guide for migration traceability, open decisions, slices, and gates.
7. Frozen tests as clues about intended V1 behavior.
8. Frozen implementation and config as clues about actual V1 behavior.

Do not create Operations until a cross-module use case exists. Research can
begin behind its own API without a generic application framework.

Path convention: abbreviated `runtime/`, `reporting/`, `state/`, `commands/`,
and `cli/` source paths are relative to `src/engine/trader/`; abbreviated test
paths are relative to `tests/engine/trader/` unless another root is explicit.

## 2. Working Capability Map

```text
operations
├── use cases
├── composition roots
├── run lifecycle
├── scheduling and leases
├── commands and authorization
├── queries and monitoring
└── notification policy
```

## 3. Migration Actions

Use **KEEP**, **ADAPT**, **SPLIT**, **MERGE**, **MOVE**, **REPLACE**, **DROP**,
**DEFER**, and **OPEN** consistently with the other migration guides.

## 4. Existing Orchestration

The frozen `pipeline/master_flow.py` mixes:

- credential selection;
- clock and candle-boundary calculations;
- store and exchange construction;
- universe selection and backfill;
- Research internals;
- artifact path construction;
- stress filtering;
- Prefect task decoration;
- subprocess launch of Telegram;
- trader startup.

It creates two broad flows called research and live execution, but neither is a
small stable application interface. V2 replaces direct stage orchestration with
one public API per owning module and keeps framework integration at the edge.

## 5. Source Inventory: Workflow Orchestration

| Frozen source | Evidence | Action |
|---|---|---|
| `pipeline/master_flow.py` | End-to-end Research and execution flow | SPLIT across use cases and composition; DROP direct internal-stage calls |
| `main.py` | Selects config bundles and dispatches research/execute flows | ADAPT only when a supported CLI exists |
| `configs/runs/dev_1m_research.yml` | Named config references and skip-fetch | ADAPT into typed run request; no dirty-run language |
| `configs/pipelines/*.yml` | Cross-module wiring and paths | SPLIT into typed module policies and application adapter config |
| Prefect decorators/dependency | Scheduling/retry metadata | DEFER until local use cases are deterministic; adapter only |

`skip_fetch` is a valid explicit choice to consume an existing exact dataset,
but it must identify that dataset rather than silently reuse whatever files are
present.

## 6. Source Inventory: CLI Use Cases

| Frozen source | Evidence | Action |
|---|---|---|
| `engine/trader/cli/promote_pairs.py` | Explicit candidate validation and promotion | SPLIT domain transition to Pairs, use case to Operations, parsing to Interfaces |
| `cli/refresh_pair_data.py` | Readonly refresh with human/JSON output | SPLIT Market Data behavior, Operations orchestration, Interface rendering |
| `cli/report_generator.py` | Resolves config, opens DB, assembles/renders/exports | REPLACE with Operations query and renderer adapters |
| `cli/risk_kill_switch.py` | Inspect/activate/clear durable switch | SPLIT Trading command, Operations authorization/audit, CLI parsing |

Command functions accepting `argparse.Namespace` are delivery-coupled and do not
become application APIs.

## 7. Source Inventory: Runtime and Process Lifecycle

| Frozen source | Evidence | Action |
|---|---|---|
| `runtime/trader_runner.py` | Resource wiring, boot, tick loop, shutdown | SPLIT composition/process policy to Operations; runtime state machine to Trading |
| `runtime/scheduler.py` | Sleep to next candle | MOVE to Operations scheduler adapter; Trading receives boundaries |
| `runtime/monitoring/run_status.py` | Persisted observer run markers and classification | ADAPT into Operations run lifecycle plus Trading health query |
| `runtime/monitoring/health.py` | Trading-domain snapshot | KEEP under Trading read model; Operations composes application readiness |
| `pipeline/task_execute_telegram` | Detached subprocess with discarded output | DROP; deployment/process supervisor owns daemon process |

Detached `Popen` from a Prefect task provides no ownership, restart, readiness,
shutdown, or audit. Delivery processes must be supervised outside a domain flow.

## 8. Source Inventory: Commands

| Frozen source | Evidence | Action |
|---|---|---|
| `engine/trader/commands/processor.py` | Claim/dispatch/complete string commands | REPLACE with typed command bus/use cases |
| `state/commands.py` | Durable pending/claimed/terminal queue | ADAPT behind Operations/Trading contract |
| `interfaces/telegram/handlers/controls.py` | Writes `/pause`, `/resume`, `/stop` strings | MOVE parsing to Interfaces; call typed Operations commands |
| `runtime/risk/kill_switch.py` | Durable Trading safety state | KEEP domain ownership; Operations authorizes invocation |
| `execution/liquidation.py` | Emergency close behavior | REPLACE before exposing a liquidation command |

The command vocabulary must separate process stop, entry pause, reduce-only,
order cancel, local repair, and exchange liquidation.

## 9. Source Inventory: Queries, Reports, and Monitoring

| Frozen source | Evidence | Action |
|---|---|---|
| `reporting/assembler.py` | Composes Trading metrics and runtime diagnostics | SPLIT Trading projection from Operations query |
| `reporting/export.py` | Writes JSON/Markdown to fixed layout | MOVE to adapter with configured destination |
| `runtime/monitoring/run_status.py` | Mixes run, health, open ids, mode safety, report serialization | SPLIT by owners |
| Telegram status/positions/pairs handlers | Direct DB and artifact queries | REPLACE with Operations query interfaces |

Operations read models must not depend on SQLite row dictionaries, JSON artifact
shape, or Telegram formatting.

## 10. Source Inventory: Notifications

| Frozen source | Evidence | Action |
|---|---|---|
| `interfaces/telegram/notifier.py` | Best-effort async wrapper with fixed timeout | MOVE to Interfaces channel adapter |
| direct notifier calls in runner, transitions, commands | Operational events and error alerts | REPLACE with channel-neutral event/notification policy |
| Telegram environment prefixes | Helps prevent mode confusion | ADAPT from typed routing/environment context |

Domain code should emit outcomes. Operations decides which merit notification,
and an adapter performs delivery.

## 11. Configuration Inventory

Frozen configuration centralizes many unrelated policies in `PipelineConfig`
and duplicates paths in Telegram config.

Migration rules:

- each domain receives its own strict typed policy;
- composition config selects adapters and connects their scopes;
- paths exist only at the adapter/application boundary;
- run profiles reference validated config identities, not raw dictionaries;
- credentials and authorization remain separate;
- `null` is modeled only when intentional;
- no loader silently supplies operational defaults.

## 12. Test Inventory

| Frozen tests | Useful behavior | Action |
|---|---|---|
| `pipeline/test_master_flow_config.py` | Typed configs passed to stages; optional Telegram | REPLACE with public use-case composition tests |
| `test_run_profile_command.py` | Profile selection and command invocation | ADAPT when supported CLI exists |
| `trader/test_promote_pairs.py` | Validation, preservation, audit | SPLIT by domain/use case/interface |
| `test_risk_kill_switch_cli.py` | Typed state and config path resolution | SPLIT authorization/use-case/CLI tests |
| `runtime/test_trader_runner_shutdown.py` | run markers and interruption | ADAPT to Operations run lifecycle |
| `runtime/test_scheduler.py` | timeframe boundary math | MOVE to scheduler adapter behavior |
| Telegram daemon tests | end-to-end command/query delivery | Retain only after Operations contracts exist |

## 13. Quality Audit Findings

### High

1. One Prefect file owns credentials, time, storage, adapters, Research stages,
   trader launch, and daemon process management.
2. Delivery handlers bypass an application API and write/query SQLite directly.
3. String commands are authenticated at Telegram but lack durable principal,
   permission, reason, and expected-state semantics.
4. A daemon is launched detached with stdout/stderr discarded and no lifecycle
   control.
5. Global settings and paths leak into orchestration and domain construction.

### Medium

1. Run status conflates persisted markers, process liveness, Trading health, and
   report serializability.
2. Rendering and export paths are mixed with query assembly.
3. Retry policy is framework-oriented rather than use-case/idempotency-oriented.
4. Config models are centralized around a historical pipeline shape rather than
   current domain ownership.

## 14. Implementation Slices

### OP0 — Name use cases and authorities

- Answer blocking questions.
- Freeze command/query vocabulary and principal/permission model.

### OP1 — Local Research use case

- Compose fixture store, Research API, Pairs store, clock, and run audit.
- Produce one typed outcome without Prefect.

### OP2 — Market Data use cases

- Add backfill/refresh/gap-repair entrypoints around existing domain APIs.
- Prove partial outcome and idempotent retry.

### OP3 — Candidate review and promotion

- Add explicit principal, reason, expected version, and audit.
- Expose a typed result consumable by CLI/HTTP.

### OP4 — Run store and monitoring

- Separate run lifecycle, process liveness, readiness, and domain health.
- Use explicit heartbeats and terminal outcomes.

### OP5 — Typed operator commands

- Implement pause/resume and kill-switch commands first.
- Defer cancellation/liquidation until Trading supports their economics safely.

### OP6 — Trading composition

- Compose Observe, then Paper, then Demo Exchange routing after their gates.
- Keep authorization independent of credential availability.

### OP7 — Scheduler adapter

- Add only when manual local use cases are deterministic.
- Invoke public use cases with leases and idempotency.

### OP8 — Consolidate

- Remove direct domain-stage orchestration, path duplication, string command
  queues, and process spawning.
- Delete this guide after canonical docs absorb accepted decisions.

## 15. Questions for Lucas

- **OPQ-001 (blocking):** Which use cases must be available first through a
  local CLI: run research, inspect candidate, promote, refresh data?
- **OPQ-002 (blocking before promotion):** What identifies the local operator
  before login exists: OS user, configured name, or explicit CLI value?
- **OPQ-003:** Is manual promotion always required, or may a separately approved
  automation principal promote under a strict policy later?
- **OPQ-004:** Should local run audit use the same database as Trading or a
  separate operations store? Recommended: separate logical ownership even if
  one physical SQLite database is initially used.
- **OPQ-005:** Which scheduler, if any, is actually needed after local manual
  workflows work?
- **OPQ-006:** What cancellation behavior is required for long Research or
  Market Data runs?
- **OPQ-007:** Which notifications are mandatory versus best-effort?
- **OPQ-008:** What is the independent emergency path if Telegram/UI is down?
- **OPQ-009:** Should HTTP/UI and Telegram share the same authentication provider
  or only the same authorization contract?
- **OPQ-010:** Which audit retention and export requirements matter for a first
  production canary?

## 16. Scope Exclusions During Migration

- workflow engine before local use cases are proven;
- microservices or distributed queues;
- cloud-specific process management;
- automatic promotion or rebalancing;
- direct exchange mutation from Operations;
- generic dependency-injection framework;
- UI-specific application contracts;
- commands whose Trading behavior is not safely implemented.

## 17. Completion Gates

- Every supported workflow invokes one typed public use case.
- Domain modules do not import Operations.
- Interfaces never open domain stores or exchange adapters directly.
- Config, paths, clocks, credentials, and adapters are composed explicitly.
- Material commands are authenticated, authorized, idempotent, and audited.
- Promotion is distinct from Research and cannot mutate Trading/exchange state.
- Run lifecycle, liveness, readiness, and health are distinct.
- Schedules contain no domain logic and cannot grant authorization.
- Notification channels are replaceable adapters.
- Local behavior tests run without network.
- Accepted behavior is in `docs/OPERATIONS.md`, and this guide is deleted.
