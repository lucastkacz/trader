# Current Roadmap

This file tracks only active or near-term work. It is intentionally short.

## Now: Local Trader Stabilization Gates

Goal:

```text
keep state-only execution behind explicit entry gates, durable operator
controls, and observable run-state/reconciliation behavior before building
synthetic replay around the trader
```

Latest stabilization slice completed on 2026-05-29:

- Interrupted async trader runs now persist `observer_run.status =
  INTERRUPTED` instead of leaving future cancelled/SIGTERM-style bounded runs as
  `RUNNING`.
- Observer run markers now seed `open_position_ids` from actual SQLite open
  positions when a run starts and when it records interruption/failure.
- Execution re-checks the dynamic pair queue against current SQLite open
  positions before each tick transition, so multiple same-tick entry signals
  cannot oversubscribe capital slots.
- Execution-path tests now cover global max open positions, max positions per
  pair, max positions per asset, explicit block reasons, and natural-exit
  preservation.
- A first pre-trade risk gate now sizes new runtime entries to
  `risk.max_cluster_exposure`, blocks entries that would exceed
  `risk.max_portfolio_exposure`, and blocks entries whose projected gross
  exposure would exceed `risk.max_leverage`.
- Pre-trade risk blocks happen before opening a spread, emit explicit operator
  reasons such as `portfolio_exposure_above_max` and
  `max_leverage_exceeded`, and do not record leg targets or exchange/client
  order ids for blocked entries.
- Flip replacement entries are checked while excluding the position being
  replaced from projected exposure; if the replacement is blocked, the
  signal-driven close still happens and the replacement entry is skipped.
- Verification after the slice: `.venv/bin/python -m pytest -q` reported
  `276 passed, 3 deselected`; `.venv/bin/ruff check src tests` passed.
- The existing local DB still contains the stale pre-fix marker from the
  extended drill: `observer_run.status = RUNNING`, `open_position_ids = []`,
  while SQLite has 2 open state-only positions. This historical local state was
  not manually rewritten.

Precision/min-size slice completed on 2026-05-29:

- Runtime pre-trade risk policy now includes explicit typed checks for
  `min_order_quantity`, `min_order_notional`, and `order_quantity_step`.
- New entries and flip replacement entries are blocked before opening when a
  sized leg target is below the minimum quantity, below the minimum notional, or
  not aligned to the configured quantity step.
- Precision/min-size blocks emit operator-visible reasons:
  `order_quantity_below_min`, `order_notional_below_min`, and
  `order_precision_invalid`.
- Blocked new entries do not create spread positions, leg targets, or
  exchange/client order ids. Blocked flip replacements still preserve the
  signal-driven close and skip the replacement entry.
- Verification after this slice:
  `.venv/bin/python -m pytest tests/engine/trader/runtime/test_tick_queue.py tests/engine/trader/config/test_loader.py -q`
  reported `39 passed`; `.venv/bin/python -m pytest -q` reported
  `283 passed, 3 deselected`; `.venv/bin/ruff check src tests` passed.

Liquidity slice completed on 2026-05-29:

- Runtime risk gates now live under `runtime/risk/`, split into typed models,
  liquidity evidence, and the pre-trade entry evaluator. This gives exposure,
  precision, liquidity, and future kill-switch entry policy one package home
  instead of growing the runtime root.
- Runtime pre-trade risk policy now includes explicit typed liquidity checks:
  `liquidity_lookback_bars` and `min_recent_quote_volume`.
- Tick execution builds a recent quote-volume snapshot from fetched OHLCV
  candles using `close * volume` for both proposed entry legs.
- New entries and flip replacement entries are blocked before opening when
  either leg has missing liquidity evidence or recent average quote volume below
  policy.
- Liquidity blocks emit operator-visible reasons:
  `liquidity_snapshot_missing` and `liquidity_below_min`.
- Blocked liquidity entries do not create spread positions, replacement opens,
  exchange/client order ids, or new-entry leg targets. Blocked flip
  replacements still preserve the signal-driven close.
- Focused verification after this slice:
  `.venv/bin/python -m pytest tests/engine/trader/runtime/test_tick_queue.py tests/engine/trader/config/test_loader.py tests/engine/trader/runtime/test_signal_transition.py -q`
  reported `46 passed`; runtime/config/risk verification reported
  `178 passed`; `.venv/bin/python -m pytest -q` reported
  `287 passed, 3 deselected`; `.venv/bin/ruff check src tests` passed.

Kill-switch entry-gate slice completed on 2026-05-29:

- Runtime risk state now has a typed durable kill-switch helper over SQLite
  `runtime_state` instead of ad hoc runtime dictionaries at call sites.
- The pre-trade risk path now reads the durable kill-switch state before opening
  new entries or flip replacement entries.
- When active, the switch blocks additional exposure with operator-visible
  reason `risk_kill_switch_active`.
- The gate preserves natural exits: existing positions still receive normal
  `FLAT` signal handling and are not force-closed or rebalanced.
- Malformed kill-switch runtime payloads are treated as inactive rather than
  crashing the trader.
- Focused verification after this slice:
  `.venv/bin/python -m pytest tests/engine/trader/runtime/test_tick_queue.py tests/engine/trader/runtime/risk/test_kill_switch.py tests/engine/trader/runtime/test_signal_transition.py -q`
  reported `25 passed`; runtime/config/risk verification reported
  `185 passed`; `.venv/bin/python -m pytest -q` reported
  `294 passed, 3 deselected`; `.venv/bin/ruff check src tests` passed.

Operator kill-switch control slice completed on 2026-05-30:

- Added an operator CLI for the durable runtime risk kill switch:
  `src.engine.trader.cli.risk_kill_switch`.
- The CLI supports `inspect`, `activate --reason ...`, and `clear` using
  typed pipeline config or an explicit SQLite `--db-path`.
- `main.py risk-kill-switch` now exposes the same control path through the
  top-level operational CLI.
- The control path uses typed runtime risk helpers instead of raw
  `runtime_state` dictionaries at call sites.
- Activating the switch remains state-only and blocks future entries through
  the existing `risk_kill_switch_active` pre-trade reason. It does not submit,
  cancel, modify, rebalance, force-close, hot-reload, promote artifacts, or
  increase capital exposure.
- Focused verification after this slice:
  `.venv/bin/python -m pytest tests/engine/trader/test_risk_kill_switch_cli.py tests/engine/trader/runtime/risk/test_kill_switch.py tests/engine/trader/runtime/test_tick_queue.py::test_risk_kill_switch_blocks_new_entry_without_opening_position tests/engine/trader/runtime/test_tick_queue.py::test_risk_kill_switch_blocks_flip_replacement_but_preserves_close tests/engine/trader/runtime/test_tick_queue.py::test_risk_kill_switch_does_not_prevent_existing_position_natural_exit tests/test_run_profile_command.py -q`
  reported `16 passed`; runtime/config/risk verification reported
  `194 passed`; `.venv/bin/python -m pytest -q` reported
  `300 passed, 3 deselected`; `.venv/bin/ruff check src tests` passed.
- Read-only local inspect after the slice:
  `.venv/bin/python -m src.engine.trader.cli.risk_kill_switch --pipeline configs/pipelines/dev.yml --json inspect`
  returned `active: false` for `data/dev/trades_1m.db`.

Fresh-start drill completed:

- The cold local lifecycle was run on 2026-05-28:
  research -> promote -> refresh pair data -> report -> bounded state-only
  execution -> SQLite verification.
- `data/` was rebuilt through supported CLI flows, not manual data edits.
- Research mined 150/150 dev symbols, discovered 14 candidate pairs, and the
  stress filter produced 3 promoted pairs.
- Promoted artifact:
  `data/universes/1m/surviving_pairs.json`, `pair_count = 3`,
  `generated_at = 2026-05-28T15:19:13.041806+00:00`.
- Promoted pairs:
  `ALT/USDT|1000BONK/USDT`, `ASTER/USDT|ADA/USDT`,
  `ASTER/USDT|AVAX/USDT`.
- Refresh used readonly Bybit market-data access for 5 promoted symbols and
  saved 1455 local bars per symbol through
  `2026-05-28T15:19:00+00:00`.
- Reports showed all 3 pairs with operator review reasons
  `market_data_older_than_artifact_generation` and
  `market_data_older_than_promotion`.
- Bounded state-only execution completed 5/5 ticks and auto-stopped with
  `observer_run.status = COMPLETED_MAX_TICKS`.
- SQLite verification showed zero open positions, zero leg fills, zero order
  events, zero user commands, zero reconciliation deltas, and zero non-null
  exchange/client order ids.
- Post-execution queue decisions ranked all 3 pairs using live opportunity
  evidence but blocked every new entry with
  `pair_validity_operator_review_required`.
- A longer state-only observation drill then refreshed promoted-pair data,
  cleared pair-validity operator review reasons, and let the trader run for
  several hours with readonly market-data access.
- The longer drill recorded 4 state-only entries and 2 natural signal exits:
  realized PnL `0.9432%`, latest unrealized PnL `-0.0716%`, latest total
  equity `0.8715%`, and 2 open state-only positions after manual SIGTERM.
- SQLite verification after the longer drill still showed 0 non-null
  exchange/client order ids, 0 reconciliation deltas, and all leg targets as
  `TARGET_RECORDED` with `filled_qty = 0`.
- The longer drill exposed rate-limit/network stalls in readonly Bybit fetches
  and stale shutdown status: `runtime_state.observer_run` remained `RUNNING`
  after SIGTERM even though the trader closed its database connection cleanly.

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
- Capital-slot policy is explicit in `execution.pair_queue.allocation`; the
  execution path now enforces global max open positions, max positions per pair,
  and max positions per asset against the latest SQLite open-position state for
  each tick transition.
- Runtime pre-trade risk policy is explicit in `configs/risk/alpha_v1.yml` and
  typed as `RiskConfig`: max per-position cluster exposure, max portfolio
  exposure, max leverage, minimum order quantity, minimum order notional, order
  quantity step, liquidity lookback bars, and minimum recent quote volume.
- Runtime kill-switch entry state is explicit in SQLite `runtime_state` through
  typed runtime risk helpers. It blocks future exposure only and does not imply
  automatic liquidation.
- Operator CLI controls can inspect, activate, and clear the durable runtime
  kill switch through either `main.py risk-kill-switch` or
  `python -m src.engine.trader.cli.risk_kill_switch`.
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
- Offline verification before the drill was green:
  `267 passed, 3 deselected`.
- Lint before the drill was green: `ruff check src tests`.

Current local assumption:

- Dev remains on readonly credentials and state-only execution.
- Pair queue mode remains `future_entries`.
- The current local DB contains 2 open state-only positions from the extended
  drill. They are accounting state only, not exchange positions.
- Queue-driven entry blocking is visible in reports and must remain limited to
  future entries.
- Existing positions must continue natural-exit evaluation.

Required next behavior:

- Keep each gate explicit in typed config or runtime policy, not hidden
  constants.
- Emit operator-visible block reasons for every pre-trade rejection.
- Preserve natural exit: risk and slot limits may block future entries, but
  must not force-close or rebalance existing positions.
- Treat readonly market-data cadence/backoff as part of local trader
  stabilization before longer unattended runs.
- Keep pair-validity threshold tuning separate from capital sizing.
- Defer simulator implementation until capital slots and pre-trade risk gates
  are stable enough to be durable runtime behavior.

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

Do not increase real-capital exposure while the active work is local trader
stabilization. Production readiness is a separate gate defined in
`docs/engineering-rules.md`.

## Next: Queue Policy Threshold Calibration

```text
tune pair-validity thresholds after queue-driven state-only behavior and
capital-slot behavior are both tested
```

Tune thresholds for correlation, p-value, hedge-ratio drift, half-life drift,
and bars since promotion after slot-policy behavior is no longer moving.

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
