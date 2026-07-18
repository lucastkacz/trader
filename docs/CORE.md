# Core Module

## 1. Purpose

Core provides the minimal foundational primitives required consistently across
the package without belonging to a specific product domain.

It owns mechanisms such as explicit time, foundational error metadata, typed
settings boundaries, correlation identities, and logging configuration. It does
not own “shared business logic” and is never a destination chosen merely because
two modules currently use similar code.

Core stays small enough that every item has an obvious reason to be foundational.

## 2. Admission Rule

A concept belongs in Core only when all of these are true:

1. at least two domain modules genuinely require the same semantics;
2. the concept contains no Research, pair, market-data, exchange, Trading,
   Operations, or interface policy;
3. Core can define it without importing a product module;
4. placing it in the owning domain would create duplicated foundational
   semantics rather than healthy domain-specific behavior;
5. its interface hides or centralizes meaningful complexity.

Code does not enter Core because it is convenient, generic, reusable, a helper,
or difficult to classify. No `utils`, `common`, `shared`, or catch-all constants
surface exists.

## 3. Responsibilities and Boundaries

### 3.1 Core owns

- explicit clock and sleep capabilities;
- timezone-aware UTC time primitives and parsing rules;
- foundational error envelope and correlation metadata;
- typed environment/secrets settings boundary;
- application logging setup and structured context mechanism;
- run/request/correlation identity generation;
- process-level version/build metadata;
- minimal redaction primitives for secrets and sensitive values.

### 3.2 Core does not own

- canonical symbols, timeframes, candles, or dataset semantics;
- pair identity, artifacts, schema, or lifecycle;
- quantitative math, statistics, or simulation;
- exchange configuration, capabilities, or credentials policy;
- Trading state, risk, orders, accounting, or reconciliation;
- application use cases, commands, scheduling, or health;
- CLI, HTTP, Telegram, or UI concerns;
- generic storage, repository, serializer, retry, or client abstractions.

### 3.3 Dependency direction

```text
research, pairs, market_data, exchange, trading, operations, interfaces
                              -> core
core -> standard library and narrowly justified foundational libraries
```

Core imports no product package. A dependency cycle through Core is an
architecture error.

### 3.4 Logical package shape

```text
core/
├── clock.py
├── errors.py
├── ids.py
├── logging.py
├── settings.py
├── redaction.py
└── version.py
```

Core remains a small flat package. The tree records the complete categories
admitted by its foundational contract, but a file is created only when at least
two real callers require the same stable meaning. Core has no `api.py` because
callers import the narrow primitive they need.

It never gains `utils.py`, `helpers.py`, generic repositories, domain models,
or backend clients. If one of these files begins accumulating product policy,
that behavior moves to its concept owner rather than creating more Core
subpackages.

## 4. Clock Contract

Time is an injected capability whenever behavior depends on “now”, sleeping, or
timeouts. The clock provides:

- current timezone-aware UTC instant;
- monotonic elapsed time for durations/timeouts;
- controlled sleep for asynchronous orchestration when needed.

Wall-clock instants and monotonic durations are different values. Duration
logic does not subtract naive datetimes or depend on local timezone.

Tests use a manually advanced clock. Domain constructors and imports do not
read the system clock implicitly.

Market Data owns candle/timeframe semantics. Core only owns general time
mechanics; it cannot decide the last closed candle or bars between timestamps.

## 5. Time Representation

Persistent instants are timezone-aware UTC values. External strings use one
documented ISO 8601 representation. Parsing rejects ambiguous or malformed
values unless an adapter explicitly normalizes a known external format.

Core does not silently assign UTC to an unknown naive timestamp. The caller must
provide the missing timezone context at the adapter boundary.

Durations carry explicit units or typed duration values. Bare numbers named
`timeout`, `age`, or `interval` without units are invalid public contracts.

## 6. Identity and Correlation

Core can generate opaque, globally unique identifiers for application runs,
requests, commands, events, and correlations. It defines generation and string
representation, not domain identity semantics.

Pair ids, dataset ids, order ids, position ids, and artifact ids remain owned by
their domains even if they use a Core identifier mechanism internally.

Identifiers are deterministic only when the domain explicitly derives them from
content or an idempotency scope. Random run ids and content hashes are not
interchangeable.

## 7. Foundational Errors

Core defines a small error envelope with:

- stable category/code;
- safe message;
- correlation id;
- retryability indication only when knowable;
- structured non-secret context;
- original cause chaining.

Domain modules define their own meaningful error types and codes. Core does not
centralize a giant enum of every business failure.

Exceptions preserve causes. Expected outcomes such as rejected hypotheses,
risk blocks, or order rejections remain typed domain results where appropriate.

## 8. Settings Boundary

Core provides the mechanism for strict settings loading and validation. The
composition root declares the complete typed application settings assembled
from explicit sources.

Rules:

- required operational values fail when missing;
- unknown keys are rejected unless an external provider requires a narrowly
  documented exception;
- secrets use dedicated secret types and are redacted by representation;
- environment variables and secret stores are read only at composition;
- domain modules receive typed policies or explicit dependencies, never a
  global settings singleton;
- strategy hyperparameters do not share a secret-settings model;
- credentials and execution authorization are separate concepts;
- effective non-secret configuration can be hashed for audit.

Core does not know which exchange, timeframe, strategy, or path the application
chooses.

## 9. Logging

Logging is configured explicitly once by an application entrypoint. Importing a
module never adds handlers, creates files, starts threads, or reads settings.

The logging mechanism supports:

- human local output;
- structured machine-readable events;
- correlation/run/request ids;
- domain-provided typed context;
- level and sink configuration;
- bounded rotation/retention at the adapter boundary;
- redaction of secrets and sensitive payloads;
- safe exception rendering.

Core defines foundational context fields, while domains attach their own typed
event data. Arbitrary formatted strings are useful diagnostics but do not
replace durable domain audit events.

## 10. Secrets and Redaction

Secret values never appear in `repr`, logs, exceptions, audit payloads,
notifications, CLI output, or HTTP responses. Redaction covers tokens,
credentials, authorization headers, signed URLs, and raw provider configuration.

Core offers narrowly scoped redaction utilities for logging/error adapters. It
does not attempt to sanitize arbitrary domain dictionaries after they have been
logged; safe structured data is selected before emission.

## 11. Build and Version Metadata

Application runs and generated artifacts may record package version, source
revision, build identity, and schema/tool versions when available.

Metadata lookup is side-effect free and does not require Git to be present at
runtime. Missing build information is represented explicitly rather than
invented.

## 12. What Remains Local to Domains

Similar-looking behavior remains local when semantics differ:

- Exchange retry follows provider/idempotency rules; notification retry follows
  delivery semantics.
- Market Data timeframe math understands candle availability; Trading holding
  periods understand position policy.
- Pairs canonical serialization understands pair-set semantics; Trading event
  serialization understands state evolution.
- Research and Trading may both calculate a z-score, but the owning quantitative
  contract determines its inputs and purpose.

Premature deduplication across domains is less maintainable than two clear local
functions with different meanings.

## 13. Error and Side-Effect Boundaries

Core has no import-time filesystem, environment, logging, network, clock, or
thread side effects.

Settings loading, logging setup, and build metadata discovery are explicit
entrypoint actions with precise failure modes. Clocks and identity generators
are constructed and injected.

Core never catches domain errors merely to log and continue.

## 14. Determinism and Testability

Behavior tests prove:

- manual clocks make time-dependent domains deterministic;
- UTC parsing rejects ambiguous timestamps;
- settings reject missing and unknown operational values;
- secrets are redacted from representations and errors;
- importing Core does not configure logging or create files;
- logging context preserves correlation without leaking secrets;
- ids satisfy their documented uniqueness/determinism properties;
- Core imports no product module.

## 15. Maintenance Invariants

- Core never becomes a `utils` package.
- Product vocabulary stays with its concept owner.
- No global mutable settings, logger configuration, clock, client, or store is
  constructed at import time.
- Domain packages depend inward on Core; Core never depends outward.
- Adding a Core abstraction requires at least two real callers and a stable
  shared meaning.
- Foundational convenience cannot weaken explicit configuration, auditability,
  or live-trading safety.
