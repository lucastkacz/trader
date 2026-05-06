# Current Roadmap

This file tracks only active or near-term work. It is intentionally short.

## Now: Artifact Versioning And Promotion

Goal:

```text
make eligible pair artifact replacement explicit, validated, and auditable
before execution can load it
```

Required behavior:

- Research writes a candidate artifact.
- Validator checks schema, metadata, freshness, and pair contents.
- Promotion atomically replaces the promoted artifact used by execution.
- Execution loads only the promoted artifact on boot.
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

Future pair refresh automation needs an explicit operator cadence and traceable
research runs before scheduled mode:

```text
operator chooses cadence
-> research run writes candidate artifact
-> validator and promotion publish a new promoted artifact
-> operator restarts trader
```

This should be designed before any scheduled refresh implementation.

## Later: Scheduled Refresh

Scheduled mode may run research on a configured cadence, but only after artifact
versioning, validation, promotion, and traceability are complete.

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
