# Core Migration Guide

> **TEMPORARY DOCUMENT**
>
> This guide identifies which frozen foundational behavior belongs in Core and
> which superficially shared behavior must return to a domain owner. Delete it
> after migration and retain accepted behavior in `docs/CORE.md`.

## 1. Purpose and Authority

Frozen evidence lives at tag `legacy-v1-before-rewrite` and in
`/Users/lucastkacz/Documents/quant-v1-reference`.

Authority order:

1. Lucas's explicit instruction for the current task.
2. `.agents/AGENTS.md` for durable implementation and safety rules.
3. `docs/_IMPLEMENTATION_AGENT_GUIDE.md` for route order and completion state.
4. `ARCHITECTURE_REFACTOR.md` and the relevant canonical module documents.
5. `docs/current-roadmap.md` for current status and near-term scope.
6. This guide for migration traceability, open decisions, slices, and gates.
7. Frozen tests as clues about intended V1 behavior.
8. Frozen implementation and config as clues about actual V1 behavior.

Core is created from demonstrated foundational needs, not by copying the frozen
`core` and `utils` directories.

Path convention: paths beginning with `src/`, `tests/`, or `configs/` are
repository-relative. Abbreviated Trading paths are relative to
`src/engine/trader/`.

## 2. Working Capability Map

```text
core
├── clock and UTC primitives
├── foundational errors/correlation
├── strict settings mechanism
├── logging configuration/redaction
└── build/version metadata
```

There is intentionally no generic repository, HTTP client, retry, serializer,
math, or utility bucket.

## 3. Migration Actions

Use **KEEP**, **ADAPT**, **SPLIT**, **MERGE**, **MOVE**, **REPLACE**, **DROP**,
**DEFER**, and **OPEN** as in the other guides.

## 4. Source Inventory: Settings

| Frozen source | Evidence | Action |
|---|---|---|
| `src/core/config.py` | Pydantic settings for log level, exchange keys, Telegram credentials | REPLACE global singleton with strict injected settings |
| `engine/trader/config/loader.py` | YAML loading and top-level key validation | ADAPT mechanism at config boundary; domain models move to owners |
| `engine/trader/config/models.py` | All pipeline/domain configs in one 314-line file | SPLIT among Research, Market Data, Exchange, Trading, Operations, Interfaces |
| `exchange/config/venue.py` | Venue/market config models and loader | KEEP ownership in Exchange |
| `data/*/config.py` | Data policies and loaders | KEEP ownership in Market Data |
| config YAML trees | Explicit operator values | Reintroduce only after each typed contract exists |

Frozen `Settings` uses `extra="ignore"`, default log level, optional credentials,
and a module-global instance. Those choices make typos invisible and cause
imports to read `.env`. V2 settings construction is explicit; missing values are
validated for the selected capability rather than tolerated globally.

## 5. Source Inventory: Logging

| Frozen source | Evidence | Action |
|---|---|---|
| `src/core/logger.py` | Console/JSON sinks, rotation, retention, queue, typed context | ADAPT mechanism |
| module-level `logger = _logger` | Shared concrete Loguru object | REPLACE with configured application logger/context |
| import-time `configure_logger()` | Automatic handlers/file/thread side effects | DROP |
| `LogContext` | Pair/trade/signal context with extra forbid | SPLIT foundational correlation from domain-specific typed fields |
| `tests/core/test_logger.py` | Silent mode and structured context behavior | ADAPT with import side-effect/redaction tests |

The frozen default path `logs/engine.jsonl`, daily rotation, 30-day retention,
and sink levels are operational configuration, not Core constants.

## 6. Source Inventory: Time and Clocks

Frozen clock access is scattered:

| Frozen source area | Behavior | Action |
|---|---|---|
| artifact build/promotion | `datetime.now()` for generation/promotion | Inject Core clock through Operations/Pairs |
| Market Data metadata/sync | acquisition and boundary times | Inject clock; candle semantics stay Market Data |
| Trading lifecycle/services | open/close/event timestamps | Inject clock into Trading transaction behavior |
| reconciliation/monitoring | age, stale, run times | Inject clock; domain classification remains Trading/Operations |
| Telegram/UI rendering | current age | Consume read-model as-of time; avoid hidden now |
| `utils/timeframe_math.py` | parse timeframe, closed-candle math, bar counts | MOVE to Market Data; Trading holding semantics use Market Data value types |
| `runtime/scheduler.py` | seconds until candle | MOVE to Operations scheduler using Market Data timeframe contract |

One Core clock capability replaces hidden wall-clock calls. It does not absorb
candle or schedule policy.

## 7. Source Inventory: Errors and Identity

The frozen code mainly uses `ValueError`, `RuntimeError`, broad `Exception`, and
formatted strings. Some domain-specific errors exist for order transitions,
Market Data fetch, plots, and risk.

Actions:

- KEEP domain-specific errors with their owners;
- ADAPT a minimal Core error metadata/correlation mechanism;
- DROP any idea of one global exception hierarchy that knows every module;
- introduce run/request/correlation ids at Operations/Interfaces composition;
- retain pair, dataset, artifact, order, and position identity in their owners.

## 8. Source Inventory: Utilities and Serialization

| Frozen source | Evidence | Action |
|---|---|---|
| `src/utils/timeframe_math.py` | Timeframe parsing and closed-candle calculations | MOVE to Market Data |
| `state/serialization.py` | JSON encoding datetimes | MOVE to Trading state adapter |
| `runtime/artifacts/*` JSON/hash helpers | Pair artifact canonicalization | MOVE to Pairs |
| reporting formatting helpers | Percent/price/duration rendering | MOVE to Interfaces |
| exchange symbol helpers | Native symbol conversion | KEEP in Exchange |
| repeated `_parse_timestamp` helpers | Domain-specific permissive parsing | Replace external parsing at adapters and typed UTC values internally |

Do not recreate `src/utils` in V2.

## 9. Caller Inventory

Frozen modules import `src.core.config.settings` or `src.core.logger.logger`
directly from Exchange, pipeline, Trading, and Telegram. This creates hidden
runtime dependencies and makes tests monkeypatch globals.

Target correction:

- entrypoints construct typed settings and logging once;
- Operations resolves secrets and builds adapters;
- domain modules receive explicit clocks/policies/capabilities;
- domain functions emit typed outcomes/events and accept a logger only when
  diagnostic logging materially belongs at that layer;
- tests construct fakes rather than reset global contexts.

## 10. Test Inventory

| Frozen tests | Useful behavior | Action |
|---|---|---|
| `tests/core/test_logger.py` | structured context and configured sinks | ADAPT; add no-import-side-effect and redaction assertions |
| config loader tests | missing/extra field failures | SPLIT into owner config contracts plus shared loader mechanism tests |
| scheduler/timeframe tests | parsing and boundary math | MOVE to Market Data/Operations |
| tests monkeypatching global settings | Shows dependency need | REPLACE with explicit dependency construction |

Core test count remains small. Most verification occurs through domain behavior
using a fake clock or test settings source.

## 11. Quality Audit Findings

### High

1. Importing `core.config` reads environment and creates a global settings
   object.
2. Importing `core.logger` can create file sinks and background logging work.
3. `extra="ignore"` can hide misspelled or stale environment fields.
4. Secrets, strategy config, operational paths, and authorization are resolved
   through scattered globals/callers.

### Medium

1. Logging defaults hardcode path, retention, clock, and sink policy.
2. `LogContext` contains Trading-specific fields in foundational code.
3. Hidden `datetime.now()` calls make artifact, lifecycle, monitoring, and audit
   behavior nondeterministic.
4. Timestamp parsing silently assumes UTC in several runtime/report paths.
5. The existing `utils` package owns meaningful Market Data time semantics.

## 12. Implementation Slices

### CO0 — Enforce admission and dependency rule

- Answer blocking questions.
- Add an import/dependency check preventing Core from importing product modules.

### CO1 — Explicit clock

- Introduce system and manual clocks.
- Migrate the first Research/Pairs timestamp vertical.
- Keep candle/timeframe policy outside Core.

### CO2 — Strict settings composition

- Define settings-source mechanism and secret types.
- Construct settings only in entrypoints.
- Move typed policies to owning modules.

### CO3 — Logging setup

- Remove import-time configuration.
- Configure sinks at composition with redaction and correlation.
- Separate diagnostic logs from durable audit.

### CO4 — Error/correlation primitives

- Add only the small metadata proven necessary by at least two module APIs.
- Preserve domain error ownership.

### CO5 — Build metadata

- Add side-effect-free version/revision lookup when artifact/run provenance uses
  it.

### CO6 — Consolidate

- Remove global settings/logger construction and `utils`.
- Delete unused foundational abstractions.
- Transfer accepted decisions and delete this guide.

## 13. Questions for Lucas

- **COQ-001 (blocking):** Should missing/unknown `.env` fields be rejected
  globally, or should only a selected entrypoint's strict settings model parse
  its allowed fields? Recommended: entrypoint-scoped strict models.
- **COQ-002:** Keep Loguru or prefer standard-library logging/structlog during
  implementation? Choose from actual structured-context/test needs.
- **COQ-003:** Which log destinations are required locally: console only or
  console plus JSONL?
- **COQ-004:** What retention belongs in local logging config rather than code?
- **COQ-005:** Which identifier format is preferred for runs/events: UUIDv7,
  ULID, or opaque UUID? Domain content hashes remain separate.
- **COQ-006:** Is source revision required in every artifact locally, and how
  should dirty worktrees be represented?
- **COQ-007:** Which values count as sensitive beyond credentials and tokens?
- **COQ-008:** Should config sources include a secret manager only when cloud
  deployment begins? Recommended: yes.

## 14. Scope Exclusions During Migration

- generic `utils`, `common`, or `shared` packages;
- universal repositories, serializers, retry clients, or result monads;
- domain-specific error enums in Core;
- a dependency-injection framework;
- cloud secret manager before deployment requires it;
- implicit timezone correction;
- import-time environment, filesystem, clock, or logging side effects.

## 15. Completion Gates

- Core imports no product module and contains no product policy.
- Every Core concept passes the admission rule with real callers.
- System and manual clocks support deterministic domain tests.
- Settings are strict, explicit, entrypoint-scoped, and secrets are redacted.
- Domain modules receive typed config/dependencies rather than global settings.
- Logging is configured explicitly and importing modules creates no sinks/files.
- Operational log paths and retention are external configuration.
- No V2 `utils` or catch-all shared package exists.
- UTC/time parsing is explicit and ambiguous timestamps fail.
- Accepted behavior is in `docs/CORE.md`, and this guide is deleted.
