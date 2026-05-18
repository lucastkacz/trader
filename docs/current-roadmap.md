# Current Roadmap

This file tracks only active or near-term work. It is intentionally short.

## Now: Pair Validity Operator Visibility And Architecture Cleanup

Goal:

```text
surface read-only promoted-pair validity diagnostics to operators and finish the
remaining runtime/trader package cleanup before any entry gating is automated
```

Already available locally:

- Report CLI computes read-only pair validity diagnostics from the promoted
  artifact, refreshed local parquet data, and persisted runtime state.
- Refresh CLI fetches/appends recent OHLCV only for symbols in the promoted
  artifact, using readonly credentials and local parquet writes.
- Diagnostics include artifact/data age in bars and time, hedge-ratio drift,
  correlation drift, cointegration drift, half-life drift, execution behavior,
  and explicit review reasons such as stale market data or an open position
  beyond configured half-life multiples.
- Runtime internals now group eligible-pair artifact lifecycle, monitoring, and
  pair-validity modules under dedicated subpackages.

Required next behavior:

- Add Telegram visibility for pair-validity diagnostics, preferably a detailed
  `/pair_validity <PAIR>` path before crowding `/pairs`.
- Add missing research baseline fields to candidate/promoted artifacts:
  research window start/end, bars used, baseline correlation, spread mean/std,
  and z-score distribution stats.
- Remove or replace remaining root-level compatibility facades in
  `src/engine/trader/` so each concept has one canonical import path.
- Keep refresh cadence and thresholds explicit in typed config or CLI/runtime
  policy rather than hidden constants.

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

## Next: Research Baseline Fields

```text
write and validate the research baseline fields needed for complete drift
comparisons in candidate/promoted eligible pair artifacts
```

Current report diagnostics intentionally emit `missing_research_*` notes because
the artifact does not yet contain every baseline needed for spread distribution
and research-window comparisons.

## Next: Trader Package Canonical Imports

```text
move CLI entrypoints under a trader CLI package and remove remaining root-level
facade modules once callers use canonical package paths
```

Canonical paths should favor `state.manager`, `signals`, `runtime.trader`,
`reporting`, and `cli` over long-lived compatibility wrappers.

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
