# Handoff: Dynamic Queue And Local Dev Lifecycle

Updated: 2026-05-21

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

Current local work includes queue-driven future-entry execution consumption.
Commit/push state should be checked with `git status --short` in the next chat.

## Current Verified State

Latest offline verification:

```text
.venv/bin/python -m pytest -q
264 passed, 3 deselected
```

Latest lint verification:

```text
.venv/bin/ruff check src tests
All checks passed!
```

Last non-empty bounded state-only smoke command with queue execution consumption
enabled:

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

Latest drill timestamp:

```text
started_at: 2026-05-21T20:40:22.831467+00:00
completed_at: 2026-05-21T20:41:17.324403+00:00
completed_ticks: 1
open_position_ids: []
```

Latest fresh cold lifecycle drill:

```text
data directory was deleted before the run
research command: main.py run --config configs/runs/dev_1m_research.yml
fetched parquet files: 150
candidate/promoted pair_count: 6
missing baseline rows: 0
promotion operator: codex-fresh-cold-run
refresh: 7 unique promoted symbols
queue report: 6 Entry YES, 0 block reasons
execute: completed 1 bounded state-only tick
runtime_state observer_run: COMPLETED_MAX_TICKS
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
- Pipeline config now declares explicit execution-time pair-validity diagnostics
  policy under `execution.pair_validity`:
  - `recent_window_bars: 240`
  - `min_recent_bars: 60`
  - `open_position_review_half_life_multiple: 3.0`
- Refresh is read-only market data work. It does not promote artifacts, reload
  execution, submit orders, or close positions.

Dynamic promoted-pair queue:

- Queue is consumed by execution for future entries when pipeline config sets
  `execution.pair_queue.mode: future_entries`.
- Reports still surface queue decisions for operator review.
- `src/engine/trader/runtime/trader_runner.py` builds pair-validity snapshots
  before each tick when queue consumption is enabled.
- `src/engine/trader/runtime/tick.py` evaluates current signal opportunity,
  builds a dynamic queue snapshot, routes higher-ranked future entries first,
  and blocks only new entries when a queue decision is not entry-allowed.
- `src/engine/trader/runtime/signal_transition.py` preserves natural exit by
  allowing blocked flip signals to close the existing position while skipping
  the replacement entry.
- It ranks promoted pairs using:
  - research score
  - pair validity score
  - current tick opportunity score during execution
  - latest persisted tick signals in reports
  - open-position exposure
  - configured allocation caps
- Dev config has explicit `execution.pair_queue`.
- `null` allocation caps or thresholds mean intentionally not enforced.
- The queue does not place orders, does not promote artifacts, and does not
  force-close or rebalance existing positions.

Bounded local execution:

- `main.py execute` now supports CLI-only runtime bounds:
  - `--max-ticks`
  - `--heartbeat-seconds`
- Overrides are process-local and do not modify YAML.
- Non-null `max_ticks` and `heartbeat_seconds` must be positive.
- `docs/local-operator-runbook.md` now uses this canonical bounded command
  instead of the old missing `logs/run_dev_state_only_observer.py` wrapper.

Behavior tests added in this slice:

- `tests/engine/trader/runtime/test_tick_queue.py`
  - blocked queue decisions prevent new entries
  - blocked queue decisions do not prevent existing-position natural exits
  - higher-ranked eligible pairs are routed first for future entries
  - state-only mode records no exchange/client order ids in the tested flow
- Config tests prove shipped pipeline configs declare explicit pair-validity
  policy and `execution.pair_queue.mode: future_entries`.

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

This drill validated the already-promoted dev artifact with execution queue
consumption enabled. It did not rerun research or promotion.

Research/promote/refresh/report:

- Existing promoted artifact contained `7` surviving pairs.
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
- Refresh completed for `7` symbols.
- Each symbol saved `4222` local rows with latest candle
  `2026-05-21T19:11:00+00:00`.
- Pair validity report showed `1997` recent bars for each promoted pair.
- Queue report showed all `7` promoted pairs as `Entry YES` with `0` block
  reasons.
- Post-execution report used fresh persisted tick observations and still showed
  all `7` promoted pairs as `Entry YES` with `0` block reasons.

State-only execution drill:

- Execution started safely with dev config:
  - `credential_tier: readonly`
  - `order_execution.mode: state_only`
  - `execution.pair_queue.mode: future_entries`
- Loaded `7` promoted pairs.
- Boot reconciliation returned `SKIPPED_NO_SNAPSHOT_PROVIDER`.
- One bounded tick evaluated signals and persisted `7` fresh tick observations.
- Latest actions were all `SKIP`.
- No open positions were created.
- No leg fills were recorded.
- No order events were recorded.
- No user commands were recorded.
- No exchange/client order ids were recorded.
- `runtime_state observer_run` recorded `COMPLETED_MAX_TICKS` with
  `completed_ticks: 1`.
- Blocked queue decisions were not exercised in this live drill because all
  queue decisions were entry-allowed; behavior tests cover blocked-entry and
  natural-exit behavior.

## Latest Fresh Cold Lifecycle Drill

This drill started after the user deleted old local data and archives. It
performed a fresh Bybit OHLCV fetch, research, promotion, promoted-pair refresh,
report, and bounded state-only execution.

Research:

```bash
.venv/bin/python main.py run --config configs/runs/dev_1m_research.yml
```

Result:

- Bybit returned `569` assets above the configured dev volume floor.
- Dev config limited the fetch universe to `150` symbols.
- Fresh fetch recreated `150` parquet files.
- Research window: `2026-05-20` to `2026-05-21`, `1m`.
- Discovery detected `150` historical datasets.
- Universe loading kept `23` assets in memory.
- Maturity sieve passed `22` assets and rejected `1`.
- Clustering wrote `data/universes/1m/clusters_20260521_2250.json`.
- Discovery yielded `45` candidate pairs.
- Pair stress filter accepted `6` survivors and rejected `39` candidates.
- Surviving pairs:
  - `AVNT/USDT|ASTER/USDT`
  - `AVNT/USDT|ADA/USDT`
  - `BCH/USDT|BNB/USDT`
  - `BCH/USDT|ARB/USDT`
  - `BCH/USDT|CHZ/USDT`
  - `BCH/USDT|ADA/USDT`
- Candidate artifact:

```text
data/universes/1m/candidate_surviving_pairs.json
pair_count: 6
generated_at: 2026-05-21T22:50:35.369541+00:00
missing baseline rows: 0
```

Promotion:

```bash
.venv/bin/python main.py promote-pairs \
  --pipeline configs/pipelines/dev.yml \
  --operator codex-fresh-cold-run
```

Result:

- Promotion succeeded.
- Candidate was atomically moved to
  `data/universes/1m/surviving_pairs.json`.
- `promotion_audit.jsonl` recorded `pair_count: 6`, operator
  `codex-fresh-cold-run`, candidate/promoted SHA
  `1fcb6697aced659ae4e7043b7ef21cab932083d20aa308b019a6d71b207f962f`, and
  promoted time `2026-05-21T22:50:56.854352+00:00`.
- Promoted artifact validation:

```text
pairs: 6
missing baseline rows: 0
candidate_exists: False
```

Refresh/report:

- Promoted-pair refresh covered `7` unique symbols:
  - `ADA/USDT`
  - `ARB/USDT`
  - `ASTER/USDT`
  - `AVNT/USDT`
  - `BCH/USDT`
  - `BNB/USDT`
  - `CHZ/USDT`
- Each refreshed symbol saved `1458` rows with latest candle
  `2026-05-21T22:52:00+00:00`.
- Initial report showed all `6` queue decisions as `Entry YES` with `0` block
  reasons.
- Post-execution report still showed all `6` queue decisions as `Entry YES`
  with `0` block reasons.
- Latest post-execution queue ranking:
  1. `AVNT/USDT|ADA/USDT`
  2. `BCH/USDT|CHZ/USDT`
  3. `BCH/USDT|BNB/USDT`
  4. `BCH/USDT|ARB/USDT`
  5. `BCH/USDT|ADA/USDT`
  6. `AVNT/USDT|ASTER/USDT`

State-only execution drill:

```bash
.venv/bin/python main.py execute \
  --pipeline configs/pipelines/dev.yml \
  --strategy configs/strategy/dev.yml \
  --risk configs/risk/alpha_v1.yml \
  --max-ticks 1 \
  --heartbeat-seconds 1
```

Result:

- Execution started safely with dev config:
  - `credential_tier: readonly`
  - `order_execution.mode: state_only`
  - `execution.pair_queue.mode: future_entries`
- Loaded `6` Tier 1 pairs from `6` total survivors.
- Boot reconciliation returned `SKIPPED_NO_SNAPSHOT_PROVIDER`.
- One bounded tick evaluated signals and persisted `6` fresh tick observations.
- Latest actions were all `SKIP`.
- `runtime_state observer_run` recorded:

```text
status: COMPLETED_MAX_TICKS
started_at: 2026-05-21T22:53:47.270126+00:00
completed_at: 2026-05-21T22:54:37.035878+00:00
completed_ticks: 1
open_position_ids: []
```

State verification after execution:

```text
open positions: 0
leg fills: 0
order events: 0
tick signals: 6
user commands: 0
reconciliation status: SKIPPED_NO_SNAPSHOT_PROVIDER
exchange/client order ids: 0
```

Important interpretation:

- The full cold research/promote/refresh/report/execution lifecycle now works
  from a deleted local `data/` directory.
- The current active promoted artifact is non-empty with `6` promoted pairs.
- Queue consumption was exercised for a non-empty fresh promotion.
- Blocked queue decisions were not exercised live because all queue decisions
  were entry-allowed; behavior tests cover blocked-entry and natural-exit
  behavior.

## Latest Clean Lifecycle Drill

This drill archived active dev runtime/artifact outputs, kept existing local
market-data parquet, and reran research with `--skip-fetch`.

Archive:

```text
data/dev/archive/clean_lifecycle_20260521_190905/
```

Archived active files:

- `data/dev/trades_1m.db`
- `data/dev/trades_1m.db-wal`
- `data/dev/trades_1m.db-shm`
- `data/universes/1m/surviving_pairs.json`
- `data/universes/1m/promotion_audit.jsonl`
- `data/universes/1m/pair_stress_report.json`
- previous `data/universes/1m/clusters_*.json`

Research:

```bash
.venv/bin/python main.py research \
  --pipeline configs/pipelines/dev.yml \
  --universe configs/universe/alpha_v1_dev_1m.yml \
  --backtest configs/backtest/stress_test_dev_1m.yml \
  --strategy configs/strategy/dev.yml \
  --skip-fetch
```

Result:

- Research skipped API fetch and used already-fetched local parquet data.
- Discovery detected `150` historical datasets.
- Filtered `17` mature assets from `18` loaded assets.
- Clustering wrote `data/universes/1m/clusters_20260521_2211.json`.
- Discovery yielded `4` candidate pairs.
- Pair stress filter rejected all `4` candidate pairs:
  - `BCH/USDT / AAVE/USDT`: best pnl `-1.48%`
  - `ALGO/USDT / AVAX/USDT`: best pnl `-1.74%`
  - `AAVE/USDT / ATOM/USDT`: best pnl `-2.18%`
  - `AAVE/USDT / ADA/USDT`: best pnl `-2.91%`
- Candidate artifact was valid but empty:

```text
data/universes/1m/candidate_surviving_pairs.json
pair_count: 0
generated_at: 2026-05-21T22:11:34.739854+00:00
```

Promotion:

```bash
.venv/bin/python main.py promote-pairs \
  --pipeline configs/pipelines/dev.yml \
  --operator codex-clean-lifecycle
```

Result:

- Promotion succeeded.
- Candidate was atomically moved to
  `data/universes/1m/surviving_pairs.json`.
- `promotion_audit.jsonl` recorded `pair_count: 0`, operator
  `codex-clean-lifecycle`, and promoted time
  `2026-05-21T22:12:07.585056+00:00`.

Refresh/report/execution:

- Promoted-pair data refresh completed as an empty no-op:
  - `Symbols: 0`
  - started `2026-05-21T22:12:26.799237+00:00`
  - finished `2026-05-21T22:12:26.799374+00:00`
- Report was healthy with empty pair-validity and queue sections.
- Bounded state-only execution loaded `0` Tier 1 pairs from `0` total survivors
  and aborted before the tick loop with:

```text
No Tier 1 pairs found. Aborting.
```

State verification after the empty-universe execution attempt:

```text
open positions: 0
leg fills: 0
order events: 0
tick signals: 0
user commands: 0
reconciliation runs: 0
runtime_state rows: 0
exchange/client order ids: 0
```

Important interpretation:

- The clean research/promote lifecycle worked mechanically from archived state
  using old local data.
- The latest active promoted artifact is intentionally empty because the old
  data produced no stress-surviving pairs.
- This did not exercise non-empty queue consumption after a fresh promotion.

## Latest Code Slice

Implemented:

- Queue-driven future-entry selection in execution.
- Typed `StrategyConfig` is now passed into tick execution instead of converting
  config-origin data back into a raw dictionary.
- Pipeline configs now set `execution.pair_queue.mode: future_entries`.
- Pipeline configs now include explicit `execution.pair_validity` diagnostics
  policy.
- Docs were updated to describe `report_only` versus `future_entries` queue
  modes.

Verification:

```text
.venv/bin/python -m pytest -q
264 passed, 3 deselected

.venv/bin/ruff check src tests
All checks passed!
```

## Current Gaps

Primary missing behavior:

- A promoted-artifact refresh/report/execution drill has been rerun after
  enabling execution queue consumption.
- A full cold research/promote/refresh/report/execution drill has now been rerun
  from a deleted local `data/` directory and produced `6` promoted pairs.
- Live blocked-queue behavior remains unexercised in an operator drill because
  the current dev queue decisions were all entry-allowed; behavior tests cover
  blocked-entry and natural-exit behavior.
- Threshold calibration remains intentionally permissive in dev.

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

Choose the next validation slice:

- Calibrate queue policy thresholds now that the active promoted artifact has
  `6` pairs and fresh diagnostics.
- Or add an operator drill/test fixture that intentionally blocks one queue
  decision while proving existing-position natural exit remains protected.
- Keep capital slot sizing separate from threshold calibration.

Suggested shape:

1. Keep dev on readonly credentials and state-only execution.
2. Preserve queue consumption as future-entry-only behavior.
3. Confirm reports expose queue diagnostics before relying on entry blocking.
4. Confirm state-only mode still records no exchange/client order ids.
5. Update this handoff with exact drill or calibration results.

Do not implement real capital sizing, automatic scheduled refresh, hot reload,
or automatic promotion in the same slice.
