# Current Roadmap

This file tracks only active or near-term work. It is intentionally short.

## Now: Research Math Consistency And Dev Dry-Run Traceability

Goal:

```text
make research artifacts mathematically consistent and auditable enough for
simulated dev dry runs before designing scheduled refresh behavior
```

Required behavior:

- Align spread, hedge-ratio, raw-price, and log-price semantics across
  cointegration discovery, pair stress filtering, artifact output, and live
  signal evaluation.
- Reject non-positive or non-finite market data at explicit research boundaries
  with behavior tests instead of flow crashes or double-log surprises.
- Add traceable dev/research stress reporting that can reconstruct the tested
  pairs, source data window, stress parameters, simulated entries and exits,
  gross/net returns, and friction drag.
- Keep development-only 1m universe and stress tuning separate from canonical
  alpha configuration.
- Preserve the research-to-candidate, operator-promotion, promoted-on-boot
  lifecycle.
- Keep artifact, audit, market-data, exchange, clock, and runtime policy
  supplied through typed config, explicit parameters, or adapters.
- Keep execution loading only the promoted artifact on boot.
- Keep the current `pair_refresh` policy manual, on-boot, and natural-exit.

Do not implement:

- automatic rebalancing
- forced closes from pair-set changes
- scheduled refresh
- hot reload
- exchange mutation from research
- increased real-capital exposure

## Standing Gate: No Capital Increase

Do not increase real-capital exposure while the active work is artifact
lifecycle. Production readiness is a separate gate defined in
`docs/engineering-rules.md`.

## Next: Scheduled Refresh Preparation

```text
design scheduled pair refresh from the traceable manual artifact lifecycle
without changing live execution reload behavior
```

Preparation must define the operator cadence and traceable research-run
expectations before scheduled mode is implemented.

## Later: Scheduled Refresh

```text
operator chooses cadence
-> research run writes candidate artifact
-> validator and promotion publish a new promoted artifact
-> operator restarts trader
```

Scheduled mode may run research on a configured cadence, but only after the
cadence contract and traceable research-run contract are designed.

Scheduled mode must still preserve natural exit for existing positions.

## Later: Hot Reload

Hot reload is higher risk and requires explicit safe reload points in the runtime
loop. It must never interrupt:

- entry execution
- exit execution
- flip handling
- command processing
- reconciliation writes

Do not implement hot reload until the runtime loop exposes safe boundaries.
