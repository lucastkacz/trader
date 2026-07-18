# Interfaces Migration Guide

> **TEMPORARY DOCUMENT**
>
> This guide maps the frozen CLI and Telegram implementation into transport
> adapters over Operations contracts. Delete it after migration and retain
> accepted behavior in `docs/INTERFACES.md`.

## 1. Purpose and Authority

Frozen evidence lives at tag `legacy-v1-before-rewrite` and in
`/Users/lucastkacz/Documents/quant-v1-reference`. Telegram is useful evidence
for operator needs, not the permanent application API or mandatory first UI.

Authority order:

1. Lucas's explicit instruction for the current task.
2. `.agents/AGENTS.md` for durable implementation and safety rules.
3. `docs/_IMPLEMENTATION_AGENT_GUIDE.md` for route order and completion state.
4. `ARCHITECTURE_REFACTOR.md` and the relevant canonical module documents.
5. `docs/current-roadmap.md` for current status and near-term scope.
6. This guide for migration traceability, open decisions, slices, and gates.
7. Frozen tests as clues about intended V1 behavior.
8. Frozen implementation and config as clues about actual V1 behavior.

No delivery adapter is implemented before the corresponding Operations command
or query exists.

Path convention: Telegram source paths are relative to
`src/interfaces/telegram/`; CLI, command, state, and Trading-runtime paths are
relative to `src/engine/trader/`; test paths follow the same areas under
`tests/`.

## 2. Working Capability Map

```text
interfaces
├── cli
├── http
├── telegram
├── webhooks
└── outbound notification adapters
```

CLI is the smallest first adapter. HTTP, Telegram, and UI are added from actual
remote/operator requirements.

## 3. Migration Actions

Use **KEEP**, **ADAPT**, **SPLIT**, **MERGE**, **MOVE**, **REPLACE**, **DROP**,
**DEFER**, and **OPEN** as in the other guides.

## 4. Existing Interface Flow

The frozen Telegram daemon:

```text
global .env token/chat id + YAML globals
-> python-telegram-bot handlers
-> direct SQLite manager and artifact file reads
-> rendering inside Telegram package
-> string command rows polled by trader
```

Outbound notifications are called directly from Trading code using a concrete
Telegram class. CLI modules similarly load config, open state, invoke domain
helpers, render, and export in one file.

## 5. Source Inventory: Telegram Context and Process

| Frozen source | Evidence | Action |
|---|---|---|
| `interfaces/telegram/daemon.py` | Polling application and route registration | ADAPT only after Operations API; remove domain imports |
| `telegram/context.py` | YAML-to-process globals and direct state manager factory | DROP; inject typed adapter config and Operations client |
| `telegram/handlers/auth.py` | Chat-id guard decorator | ADAPT as Telegram authentication; authorization remains Operations |
| `interfaces/telegram/__init__.py` | Package marker | DROP/RECREATE only with real adapter |
| `configs/telegram/*.yml` | DB path, artifact path, holding period, stale threshold | REPLACE; adapter config contains only transport/auth/presentation policy |

Process globals and reset hooks exist mainly to make tests possible. Composition
with an explicit context/client removes those hidden seams.

## 6. Source Inventory: Telegram Queries

| Frozen source | Evidence | Action |
|---|---|---|
| `handlers/runtime.py` | status, health, run-status commands | REPLACE direct state access with Operations queries |
| `handlers/positions.py` | position list, inspection, callbacks, plots | SPLIT handler translation from delivery rendering; query typed projections |
| `handlers/pairs.py` | validates artifact and queries latest signals | REPLACE with one pair-set Operations query |
| `handlers/menu.py` | discoverable operator menu/help | ADAPT after supported command set is fixed |
| `plots.py` | builds and renders z-score position plot | ADAPT as presentation adapter from typed time-series DTO |
| `rendering/runtime.py` | run-status rendering | ADAPT from delivery DTO |
| `rendering/positions.py` | position summary/keyboards | ADAPT; remove dict and SQLite assumptions |
| `rendering/pairs.py` | legacy artifact row rendering | REPLACE with typed pair-set DTO |
| `rendering/menu.py`, `formatting.py` | Telegram-specific presentation | KEEP selectively after contract tests |

Handlers must not calculate equity, holding time, staleness, or latest signal
selection. Those meanings belong in domain/application read models.

## 7. Source Inventory: Telegram Commands

| Frozen source | Evidence | Action |
|---|---|---|
| `handlers/controls.py` | `/pause`, `/resume`, `/stop`, `/stop_all` | REPLACE with explicit Operations commands |
| `handlers/auth.py` | Rejects non-configured chat | ADAPT to typed principal |
| `state/commands.py` | String queue written by handlers | MOVE/REPLACE under Operations command contract |
| `commands/processor.py` | Executes polled strings | REPLACE with typed idempotent command handling |

`/stop` currently means different things in message text, local state, and
operator expectation. The new adapter exposes precise actions and confirmation
flows; liquidation remains unavailable until Trading implements it safely.

## 8. Source Inventory: Outbound Notifications

| Frozen source | Evidence | Action |
|---|---|---|
| `telegram/notifier.py` | Prefix, timeout, sync request in executor | ADAPT as one notification adapter |
| direct calls in `trader_runner.py` | boot/fatal/reconciliation alerts | REPLACE with Operations notification policy |
| direct calls in `signal_transition.py` | entry/exit/blocked messages | REPLACE with domain events and channel-neutral templates |
| direct calls in `commands/processor.py` | command outcomes | REPLACE with durable command result notifications |

The adapter catches all request exceptions and ignores HTTP response status. V2
returns a typed delivery outcome, uses an async client or bounded worker, handles
rate limits, and never exposes the bot token in errors.

## 9. Source Inventory: CLI

| Frozen source | Evidence | Action |
|---|---|---|
| `cli/promote_pairs.py` | Parser, application action, output | SPLIT; keep only parsing/rendering under Interfaces |
| `cli/refresh_pair_data.py` | Async action plus table/JSON output | SPLIT |
| `cli/report_generator.py` | Config/path resolution, queries, rendering, export | REPLACE with Operations query/export use cases |
| `cli/risk_kill_switch.py` | Subcommands and JSON/human output | ADAPT over authorized Operations command |
| top-level run-profile command | Loads many configs and chooses flow | REPLACE with explicit use-case subcommands |

CLI commands should support stable JSON schemas and exit codes so local
automation does not parse decorative text.

## 10. HTTP and UI Evidence

There is no frozen HTTP API or UI backend to migrate. Do not invent a framework,
ORM-shaped REST API, login database, or frontend contract now.

The canonical requirement is an Operations API that can later be delivered via
HTTP. Authentication provider, web framework, session/token model, CORS, and UI
technology remain open until remote interaction becomes a milestone.

## 11. Test Inventory

| Frozen tests | Useful behavior | Action |
|---|---|---|
| `interfaces/telegram/test_daemon.py` | Auth, menus, status, positions, pair views, plot, controls | SPLIT into small handler/renderer contract tests over fake Operations |
| `telegram/test_notifier.py` | success, missing credentials, timeout, environment prefix | ADAPT with HTTP status/rate-limit/dedup outcomes |
| `trader/test_promote_pairs.py` | CLI promotion result | Move domain/use-case assertions out; retain parser/output mapping |
| `trader/test_risk_kill_switch_cli.py` | subcommands and JSON output | Adapt to fake Operations client |
| `trader/test_report_generator_config.py` | config-based report inputs | DROP path/config coupling; query by scope |

The 723-line daemon test proves too much through monkeypatched global context.
V2 tests public handler translation and rendering separately from Operations
behavior.

## 12. Security Findings

### High

1. Telegram handlers authenticate by one chat id but application commands do
   not persist principal or authorization evidence.
2. Delivery code opens the Trading database and pair artifacts directly.
3. High-impact `/stop_all` is a single message command with ambiguous economics.
4. Process-global config and secrets couple tests and runtime.
5. Notification responses are not checked, so failed delivery can appear
   successful.

### Medium

1. Direct rendering from dicts leaks persistence/artifact shapes.
2. Telegram-specific HTML is constructed near domain queries.
3. Synchronous HTTP is delegated to the default executor without bounded
   concurrency.
4. No durable deduplication or delivery result exists for notifications.
5. CLI outputs and exit semantics are inconsistent across commands.

## 13. Implementation Slices

### IF0 — Resolve external contract and security

- Answer blocking questions.
- Define principal, permissions, command confirmation, DTO, error, and version
  conventions.

### IF1 — Local CLI foundation

- Implement a small adapter over one Operations use case.
- Support human and JSON output with explicit exit codes.
- Keep critical kill-switch access independent of network interfaces.

### IF2 — Research and pair-set CLI

- Add run/inspect/promote commands only as their Operations APIs mature.
- Never expose storage paths as domain identity.

### IF3 — Notification seam and Telegram sender

- Define channel-neutral message/delivery result.
- Add bounded timeout, response validation, rate-limit, and fake-adapter tests.

### IF4 — Telegram read-only adapter

- Start with health, runs, candidate/promoted set, and position summaries.
- Consume only Operations queries.

### IF5 — Telegram low-risk commands

- Add authenticated pause/resume and kill-switch actions with typed principal,
  reason, idempotency, and durable outcome.
- Keep liquidation unavailable until its independent gate passes.

### IF6 — HTTP/API and UI

- Add only when remote/UI use cases justify them.
- Version contracts and reuse Operations commands/queries.

### IF7 — Consolidate

- Remove global daemon context, direct stores, legacy dict renderers, and direct
  notifier calls.
- Delete this guide after canonical docs contain accepted behavior.

## 14. Questions for Lucas

- **IFQ-001 (blocking):** Is CLI the first supported interface, with Telegram
  deferred until the domain/use-case vertical works? Recommended: yes.
- **IFQ-002:** Which read-only views are actually valuable remotely first?
- **IFQ-003:** Which commands, if any, should Telegram be allowed to execute?
- **IFQ-004 (blocking before remote mutation):** What authentication provider
  should HTTP/UI use when introduced?
- **IFQ-005:** Is one owner/operator role sufficient initially, or are viewer,
  researcher, operator, and admin roles required?
- **IFQ-006:** Which high-impact commands require two-step confirmation or a
  second channel?
- **IFQ-007:** Should Telegram be notifications-only for the first production
  canary?
- **IFQ-008:** Which notification classes are mandatory and which should be
  rate-limited/digested?
- **IFQ-009:** What data may be visible in remote notifications if the account
  contains real capital?
- **IFQ-010:** Is a web UI a real near-term requirement or merely an architectural
  option?

## 15. Scope Exclusions During Migration

- selecting a web framework before HTTP is a milestone;
- building a frontend before stable read/command contracts;
- direct database or artifact access from adapters;
- Telegram-only domain models;
- exposing raw exchange payloads;
- liquidation commands before Trading safety gates;
- storing authentication secrets in normal config or logs;
- treating UI availability as a safety control.

## 16. Completion Gates

- Every adapter calls Operations only through typed commands/queries.
- No interface opens a Trading database, pair artifact, or exchange client.
- Authentication produces a typed principal; Operations authorizes actions.
- High-impact commands are explicit, confirmed, idempotent, and audited.
- CLI has documented exit codes and stable JSON output.
- Notification adapters return delivery outcomes and never block Trading.
- Telegram outage cannot remove independent kill-switch access.
- Renderers consume delivery DTOs, not persistence dictionaries.
- Unit tests run without network or process globals.
- Accepted behavior is in `docs/INTERFACES.md`, and this guide is deleted.
