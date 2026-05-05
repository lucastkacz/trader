# Current Roadmap

This file tracks only active or near-term work. It is intentionally short.

## Now: Pair Recalculation And Artifact Lifecycle

Goal:

```text
make pair artifacts observable, auditable, validated, and safe for future
manual recalculation
```

Required behavior:

- Add explicit `pair_refresh` config under pipeline execution.
- Start with `mode: manual`.
- Use `reload_policy: on_boot`.
- Use `stale_open_position_policy: natural_exit`.
- Validate artifact metadata before execution accepts it.
- Reject legacy list-only artifacts.
- Keep pair recalculation separate from live position mutation.

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

## Next: Artifact Versioning And Promotion

Future pair refresh automation needs candidate artifacts before promotion:

```text
research writes candidate artifact
-> validator checks schema, metadata, freshness, and pair contents
-> promotion atomically replaces accepted artifact
-> execution loads accepted artifact on boot
```

This should be implemented before any scheduled refresh.

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
