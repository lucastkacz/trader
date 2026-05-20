# Handoff: Dynamic Queue And Local Dev Lifecycle

Updated: 2026-05-20

## Purpose

This handoff is for continuing the local dev automation session in a fresh chat.
The active goal is to turn the promoted-pair lifecycle into a safe, auditable
execution workflow:

```text
research flow
-> candidate artifact
-> operator promotion
-> promoted artifact
-> read-only data refresh
-> pair validity diagnostics
-> dynamic promoted-pair queue
-> state-only execution drill
-> future-entry queue consumption
```

Do not call the system production-ready for real capital. The production
readiness gate in `docs/engineering-rules.md` still applies.

## Required Context For The Next Chat

Read these before changing code:

- `AGENTS.md`
- `CONTEXT.md`
- `docs/index.md`
- `docs/engineering-rules.md`
- `docs/system-design.md`
- `docs/current-roadmap.md`
- `docs/local-operator-runbook.md`

Use project skills when relevant:

- `improve-quant-architecture` for module shape and operational seams.
- `quant-code-quality-auditor` for safety/config/test integrity reviews.
- `quant-roadmap-maintainer` when changing roadmap state.

Important language to preserve:

- research flow
- execution flow
- eligible pair artifact
- candidate artifact
- promoted artifact
- pair recalculation
- dynamic promoted-pair queue
- pair validity
- refresh cycle
- capital slot
- natural exit
- live exchange mutation
- config boundary

## Branch And Latest Baseline

Branch:

```text
pair-validity-readonly-diagnostics
```

Previous commit before this handoff update:

```text
231aae04 Add read-only pair validity refresh diagnostics
```

Remote:

```text
origin git@github.com:lucastkacz/trader.git
```

The user asked to commit and push the current branch after updating handoff and
docs.

## Current Verified State

Latest offline verification:

```text
.venv/bin/python -m pytest -q
256 passed, 3 deselected
```

Latest bounded state-only smoke command:

```bash
.venv/bin/python main.py execute \
  --pipeline configs/pipelines/dev.yml \
  --strategy configs/strategy/dev.yml \
  --risk configs/risk/alpha_v1.yml \
  --max-ticks 1 \
  --heartbeat-seconds 1
```

Result:

```text
Completed 1 ticks. Auto-stopping.
Prefect flow state: Completed()
runtime_state observer_run: COMPLETED_MAX_TICKS
open positions: 0
exchange/client order ids: 0
```

Local network caveat:

- Bybit sometimes times out during dev fetches.
- Telegram notifier sometimes times out locally.
- These failures were noisy but did not create exchange mutation.

## What Is Implemented

Architecture and package shape:

- Trader CLI entrypoints live under `src/engine/trader/cli/`.
- Runtime artifact lifecycle lives under `src/engine/trader/runtime/artifacts/`.
- Runtime monitoring lives under `src/engine/trader/runtime/monitoring/`.
- Pair validity lives under `src/engine/trader/runtime/pair_validity/`.
- Dynamic queue ranking lives under `src/engine/trader/runtime/pair_queue/`.
- Root trader compatibility facades were removed in favor of canonical package
  paths.

Artifact lifecycle:

- Research writes candidate artifacts.
- `main.py promote-pairs` validates and promotes candidate artifacts.
- Promotion appends `promotion_audit.jsonl`.
- Execution loads only the promoted artifact on boot.
- No pair recalculation path force-closes or rebalances open positions.

Research baseline fields:

- Fresh candidate/promoted artifacts now include baseline diagnostics needed by
  pair validity:
  - `Research_Window.start`
  - `Research_Window.end`
  - `Research_Window.bars`
  - `Correlation`
  - `Spread_Mean`
  - `Spread_Std`
  - `Z_Score_Distribution`
- `src/research/pair_baseline.py` owns baseline field calculation.
- Discovery and stress filtering refresh these fields from aligned research
  price windows.
- Timestamp serialization was fixed so numeric millisecond indexes become ISO
  UTC strings, not raw numeric strings.

Pair validity and refresh:

- Refresh CLI:

```bash
.venv/bin/python -m src.engine.trader.cli.refresh_pair_data \
  --pipeline configs/pipelines/dev.yml \
  --overlap-bars 5 \
  --missing-lookback-bars 1500 \
  --fetch-limit 1000
```

- Report CLI:

```bash
.venv/bin/python -m src.engine.trader.cli.report_generator \
  --pipeline configs/pipelines/dev.yml \
  --pair-validity-window-bars 240 \
  --pair-validity-min-bars 60 \
  --open-position-review-half-life-multiple 3
```

- Pair validity reports age, recent bars, hedge-ratio drift, correlation drift,
  p-value drift, half-life drift, spread mean/std drift, execution observations,
  and explicit review reasons.
- Refresh is read-only market data work. It does not promote artifacts, reload
  execution, submit orders, or close positions.

Dynamic promoted-pair queue:

- Queue is currently report-only.
- It ranks promoted pairs using:
  - research score
  - pair validity score
  - latest opportunity score from persisted tick signals
  - open-position exposure
  - configured allocation caps
- Dev config has explicit `execution.pair_queue`.
- `null` allocation caps or thresholds mean intentionally not enforced.
- The queue does not place orders and does not mutate runtime state.

Bounded local execution:

- `main.py execute` now supports CLI-only runtime bounds:
  - `--max-ticks`
  - `--heartbeat-seconds`
- Overrides are process-local and do not modify YAML.
- Non-null `max_ticks` and `heartbeat_seconds` must be positive.
- `docs/local-operator-runbook.md` now uses this canonical bounded command
  instead of the old missing `logs/run_dev_state_only_observer.py` wrapper.

Exchange client fix:

- Bybit CCXT creation now narrows market loading to linear USDT swaps and uses
  time adjustment / larger recv window to avoid timestamp drift failures:
  - `defaultType: swap`
  - `defaultSubType: linear`
  - `defaultSettle: USDT`
  - `fetchMarkets.types: ["linear"]`
  - `adjustForTimeDifference: True`
  - `recvWindow: 10000`

## Latest Fresh Dev Drill

Research/promote/refresh/report:

- Fresh dev research generated `7` surviving pairs.
- Promoted artifact:

```text
data/universes/1m/surviving_pairs.json
```

- Promoted artifact validation:

```text
pairs: 7
missing baseline rows: 0
```

- Promoted symbols were refreshed to recent Bybit 1m market data.
- Initial report right after promotion showed
  `market_data_older_than_promotion` because promotion happened between closed
  candles.
- A second refresh after the next closed candle cleared the issue.
- Queue report then showed all `7` promoted pairs as `Entry YES` with `0`
  block reasons.

State-only execution drill:

- Execution started safely with dev config:
  - `credential_tier: readonly`
  - `order_execution.mode: state_only`
- Loaded `7` promoted pairs.
- Boot reconciliation returned `SKIPPED_NO_SNAPSHOT_PROVIDER`.
- Ticks evaluated signals and persisted tick observations.
- No entries fired because latest actions were `SKIP`.
- No open positions were created.
- No exchange/client order ids were recorded.

## Current Gaps

Primary missing behavior:

- Execution does not consume the dynamic queue yet.
- The report ranks pairs, but the trading loop still evaluates promoted pairs as
  a flat list.

Capital allocation gap:

- Dev has no global max open positions yet.
- No full position sizing / capital allocator exists yet.
- `max_positions_per_pair: 1` exists, but broader capital-slot policy is still
  future work.

Threshold gap:

- These are configured but currently `null` in dev:
  - `min_recent_correlation`
  - `max_recent_p_value`
  - `max_abs_hedge_ratio_drift_pct`
  - `max_half_life_drift_pct`
  - `max_bars_since_promotion`

Lifecycle gaps:

- No scheduled candidate regeneration.
- No automatic promotion.
- No hot reload.
- No forced closes from pair-set changes, intentionally.

## Recommended Next Slice

Implement execution consumption of the dynamic queue for future entries only.

Suggested shape:

1. Build queue decisions inside the execution tick from the same typed policy
   used by reports.
2. Filter/rank only candidate future entries.
3. Preserve natural exit for existing positions.
4. Do not force-close, rebalance, or hot-reload because a pair falls in rank or
   becomes blocked.
5. Add focused tests proving:
   - blocked queue decisions prevent new entries
   - higher-ranked eligible pairs are evaluated first for future entries
   - existing open positions still receive normal exit evaluation
   - state-only mode still records no exchange/client order ids

Do not implement real capital sizing, automatic scheduled refresh, hot reload,
or automatic promotion in the same slice.
