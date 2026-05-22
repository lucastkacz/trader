# Current Roadmap

This file tracks only active or near-term work. It is intentionally short.

## Now: Queue-Driven Future Entry Selection

Goal:

```text
make execution consume the audited dynamic promoted-pair queue for future
entries only, while preserving natural exit for existing positions
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
- Trader CLI entrypoints live under `src/engine/trader/cli/`, and callers use
  canonical imports for state, signals, runtime trader, reporting, and CLI
  modules.
- `runtime/pair_queue/` can build a ranked decision snapshot from promoted
  pairs, pair-validity snapshots, opportunity evidence, open-position exposure,
  and typed runtime policy. It does not place orders or mutate state.
- The report path can surface dry-run dynamic queue decisions when
  pair-validity diagnostics are requested, including score components,
  entry-allowed flags, block reasons, review reasons, and current rank.
- Execution can build dynamic queue decisions from current tick opportunity
  evidence and pair-validity snapshots, then filter/rank future entries when
  pipeline config sets `execution.pair_queue.mode: future_entries`.
- Blocked queue decisions prevent new entries and do not prevent existing
  positions from receiving natural-exit signal evaluation.
- Pipeline config now declares explicit `execution.pair_queue` policy for
  queue behavior, scoring weights, validity thresholds, and
  allocation caps. `null` means intentionally unlimited for caps and optional
  thresholds.
- Pipeline config now declares explicit `execution.pair_validity` diagnostics
  policy used by execution-time queue consumption.
- Fresh research candidate artifacts now carry baseline fields needed for
  validity diagnostics: research window start/end/bars, baseline correlation,
  canonical spread mean/std, and z-score distribution stats. Stress filtering
  refreshes these fields from the aligned source window used by surviving
  pairs.
- The execution CLI supports bounded local state-only drills through
  process-local `--max-ticks` and `--heartbeat-seconds` overrides. These
  overrides do not modify YAML and preserve the typed pipeline config boundary.
- A fresh dev research/promote/refresh/report drill produced 7 promoted pairs
  with complete baseline fields. After the next closed candle refresh, all 7
  queue decisions were entry-eligible with no validity blocks.
- A bounded state-only execution smoke run completed with `COMPLETED_MAX_TICKS`,
  no open positions, and no exchange/client order ids recorded.

Required next behavior:

- Run a fresh local research/promote/refresh/report/execution drill with queue
  consumption enabled.
- Confirm no exchange/client order ids are recorded during the state-only
  execution drill.
- Preserve pair-validity refresh cadence and thresholds as explicit typed
  config or CLI/runtime policy rather than hidden constants.
- Keep tuning thresholds separate from capital sizing.

Do not implement:

- automatic rebalancing
- forced closes from pair-set changes
- automatic scheduled refresh before the quantified policy is designed and
  tested
- hot reload
- exchange mutation from research
- automatic promotion
- hidden entry blocking without operator-visible diagnostics and tests
- queue-driven forced closes or rebalancing
- increased real-capital exposure

## Standing Gate: No Capital Increase

Do not increase real-capital exposure while the active work is artifact
lifecycle. Production readiness is a separate gate defined in
`docs/engineering-rules.md`.

## Next: Queue Policy Threshold Calibration

```text
tune pair-validity and allocation thresholds after queue-driven state-only
behavior is tested
```

Initial execution consumption should still work with permissive dev thresholds.
After that, tune thresholds for correlation, p-value, hedge-ratio drift,
half-life drift, bars since promotion, and capital slots.

## Next: Capital Slot And Position Sizing Policy

```text
define the capital-slot policy that decides how many queue entries may become
open positions and how large those state-only/live positions should be
```

Keep this separate from first queue consumption. Dev can remain permissive while
tests prove future-entry filtering and natural-exit behavior.

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
