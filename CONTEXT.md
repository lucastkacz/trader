# Quant Platform Context

This file defines shared domain language for humans and AI agents working on the repository. Use these terms in architecture reviews, plans, tests, and code comments.

Canonical system documentation lives in `docs/`.

## Domain Terms

**Research flow**: the offline or operator-run process that fetches or reads historical data, builds returns matrices, discovers clusters, finds cointegrated pairs, runs stress filters, and writes eligible pair artifacts.

**Execution flow**: the live trader process that loads validated artifacts on boot, evaluates eligible pairs, manages positions, processes commands, and reconciles state.

**Eligible pair artifact**: the JSON artifact at `data/universes/{timeframe}/surviving_pairs.json` that declares which pairs may be considered for future entries.

**Pair recalculation**: re-running research/discovery/stress logic to produce a new eligible pair artifact for future entries.

**Rebalancing**: actively changing, reducing, closing, or replacing open positions because eligibility changed. This is not part of pair recalculation.

**Natural exit**: production-safe policy where an open position continues under normal exit logic even if its pair is absent from a newer eligible pair artifact.

**Candidate artifact**: a newly generated artifact that has not yet been validated and promoted for execution.

**Promoted artifact**: the artifact version accepted for execution loading.

**Pair validity**: quantified evidence that a promoted pair still resembles the
research assumptions that made it eligible. This should be expressed with
measurements such as artifact/data age, bars since research, hedge-ratio drift,
spread distribution drift, correlation drift, cointegration drift, observed
holding-time multiples, and execution-vs-research behavior. Avoid vague labels
without the underlying numbers.

**Refresh cycle**: the operator-governed loop that fetches or appends recent
market data, recomputes pair validity diagnostics or a candidate artifact,
records audit evidence, and asks an operator to decide whether to promote. A
refresh cycle must not imply rebalancing or hidden forced closes.

**Config boundary**: the layer where YAML dictionaries are parsed into typed configuration objects. Raw YAML dicts must not leak below this layer.

**Live exchange mutation**: any operation that can create, modify, or cancel real orders or positions on an exchange.

**Runtime state**: in-memory and persisted trading state used by live execution, including positions, orders, reconciliation results, commands, and lifecycle events.

**Operational seam**: a place where environment-specific behavior enters the
system, such as filesystem layout, exchange adapter, clock, credentials,
notification channel, or state store. Production modules should receive these
through typed config, explicit parameters, or adapters rather than hardcoding
them.

## Engineering Priorities

- Reliability over cleverness.
- Auditability over hidden convenience.
- Typed config over permissive defaults.
- Offline tests over live integration assumptions.
- Agnostic, modular seams over hardcoded paths or environment assumptions.
- Focused slices over broad rewrites.
