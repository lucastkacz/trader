# Current Roadmap

This file tracks only active or near-term work. It is intentionally short.

## Now: Quantified Pair Validity And Refresh Policy Design

Goal:

```text
design how promoted pair validity, data refresh, and candidate regeneration are
measured and surfaced before any scheduled refresh or entry gating is automated
```

Required behavior:

- Define quantified pair validity diagnostics rather than vague freshness
  labels. Required diagnostics should include artifact/data age in bars and
  time, hedge-ratio drift, spread distribution drift, correlation drift,
  cointegration drift, half-life drift, and execution behavior drift where data
  is available.
- Define the refresh cycle as a read-only/operator-governed loop:
  fetch or append recent market data, recompute diagnostics or a candidate
  artifact, write audit evidence, and require operator promotion before
  execution uses a new promoted artifact.
- Decide cadence semantics without hardcoding operational assumptions. Candidate
  options include every `N` closed candles, every `N * median_half_life`, a
  wall-clock schedule per timeframe, or a hybrid policy.
- Preserve research-to-candidate, operator-promotion, promoted-on-boot loading,
  and natural exit for existing positions.
- Keep artifact, audit, market-data, exchange, clock, storage, cadence, and
  runtime policy supplied through typed config, explicit parameters, or adapters.
- Implement read-only visibility first in reports and Telegram before changing
  entry behavior.

Do not implement:

- automatic rebalancing
- forced closes from pair-set changes
- automatic scheduled refresh before the quantified policy is designed and
  tested
- hot reload
- exchange mutation from research
- automatic promotion
- hidden entry blocking without operator-visible diagnostics and tests
- increased real-capital exposure

## Standing Gate: No Capital Increase

Do not increase real-capital exposure while the active work is artifact
lifecycle. Production readiness is a separate gate defined in
`docs/engineering-rules.md`.

## Next: Read-Only Pair Validity Diagnostics

```text
compute and display quantified pair validity diagnostics from recent fetched
data and persisted state-only execution behavior
```

Diagnostics should be available through reporting and Telegram, but should not
block entries until the operator has reviewed the metrics and thresholds.

## Later: Scheduled Candidate Regeneration

```text
configured cadence triggers read-only market-data refresh
-> research run writes candidate artifact plus validity diagnostics
-> operator reviews audit evidence
-> operator promotes when acceptable
-> trader restarts and loads promoted artifact on boot
```

Scheduled mode may run research on a configured cadence, but promotion remains
operator-controlled unless a separate audited policy is designed and tested.

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
