# Current Roadmap

This file tracks only active or near-term work. It is intentionally short.

## Now: Scheduled Refresh Preparation

Goal:

```text
design scheduled pair refresh from the now-traceable manual artifact lifecycle
without changing live execution reload behavior
```

Required behavior:

- Define the operator cadence and traceable research-run expectations before
  implementing scheduled mode.
- Preserve the research-to-candidate, operator-promotion, promoted-on-boot
  lifecycle.
- Keep artifact, audit, market-data, exchange, clock, and runtime policy seams
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

## Next: Scheduled Refresh

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
