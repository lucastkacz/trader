# Current Roadmap

This file tracks only active or near-term work. It is intentionally short.

## Now: Dev State-Only Dry Run From Promoted Candidate Artifact

Goal:

```text
prove the execution flow can safely consume a manually promoted dev candidate
artifact in state-only mode before designing scheduled refresh behavior
```

Required behavior:

- Rerun dev 1m research from the dev run profile, fetching fresh data when
  local parquet data is absent, and write a candidate artifact plus pair stress
  report.
- Inspect the stress report for source data windows, tested pairs, simulated
  entries and exits, gross/net returns, friction drag, and rejection reasons
  before promotion.
- Manually promote only an inspected dev candidate artifact for state-only
  execution loading.
- Run a bounded state-only execution dry run that loads the promoted artifact on
  boot and records signal/position state without exchange mutation.
- Compare execution signal behavior against the research stress report for the
  promoted pairs.
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
design scheduled pair refresh only after the manual dev dry-run lifecycle is
traceable from research report through state-only execution behavior
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
