# Handoff: Local Trader Fresh-Start Stabilization

Updated: 2026-05-28

## Purpose

This handoff is for continuing local trader work after a completed cold local
rebuild of `data/`. The next goal is to tighten the local trader contract with
capital-slot policy and pre-trade risk gates, while deferring simulator
implementation until those runtime decisions are stable.

Do not call the system production-ready for real capital. The production
readiness gate in `docs/engineering-rules.md` still applies.

## Required Context

Read these before changing code:

- `.agents/AGENTS.md`
- `.agents/CONTEXT.md`
- `docs/index.md`
- `docs/engineering-rules.md`
- `docs/system-design.md`
- `docs/current-roadmap.md`
- `docs/local-operator-runbook.md`

Use project skills when relevant:

- `improve-quant-architecture` for module shape and operational seams.
- `quant-code-quality-auditor` for safety/config/test integrity reviews.
- `quant-roadmap-maintainer` when changing roadmap state.

Preserve these terms:

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

## Branch And Working Tree

Current branch for this planning/docs work:

```text
local-trader-fresh-start-docs
```

Baseline before the branch:

```text
main...origin/main at 1a96f6fc Merge simulation scenario lab docs
```

Known uncommitted/untracked work carried onto this branch:

- Simulation documentation updates under `simulation/`.
- New simulation docs:
  - `simulation/IMPLEMENTATION_PLAN.md`
  - `simulation/STREAM_SIMULATION.md`
- New content docs under `.content/docs/`.
- Fresh-start trader docs updates in `.agents/` and `docs/`.

## Current Verified State

Latest offline verification:

```text
.venv/bin/python -m pytest -q
267 passed, 3 deselected
```

Latest lint verification:

```text
.venv/bin/ruff check src tests
All checks passed!
```

## Local Data State

`data/` was intentionally deleted and then rebuilt through the supported local
operator lifecycle on 2026-05-28.

Implications:

- Current local runtime DB: `data/dev/trades_1m.db`.
- Current promoted artifact:
  `data/universes/1m/surviving_pairs.json`.
- Current local parquet store: `data/parquet/bybit/1m/`.
- Current local state after the extended observation drill has 2 open
  state-only positions and 0 exchange/client order ids. Treat them as local
  accounting state only; do not force-close them for documentation cleanup.
- Old open-position notes from before deletion remain stale.
- Future fresh-start drills should still recreate state through supported CLI
  flows, not manual file edits.

## Fresh-Start Drill Results

Completed on 2026-05-28 from branch `local-trader-fresh-start-docs`.

Preflight:

- `configs/pipelines/dev.yml` used `credential_tier: readonly`.
- `configs/pipelines/dev.yml` used `order_execution.mode: state_only`.
- `configs/pipelines/dev.yml` used `execution.pair_queue.mode: future_entries`.
- `launchctl` observer service was not loaded.
- `launchctl` dev Telegram daemon was initially running as
  `com.quant.dev-telegram-daemon` with PID `45833`; it was stopped before the
  lifecycle drill.
- Post-stop process scan showed no trader, observer, dev Telegram daemon, or
  `caffeinate` process. Only Telegram Desktop crash-handler processes matched
  the broad `telegram` search term.

Research:

```text
.venv/bin/python main.py run --config configs/runs/dev_1m_research.yml
```

- First sandboxed attempt failed because Prefect could not find a local API
  port. The same command succeeded outside the sandbox.
- Prefect temporary server: `http://127.0.0.1:8403`.
- Research window: 2026-05-27 to 2026-05-28.
- Bybit universe after volume filter: 572 assets.
- Dev research limited the universe to 150 symbols.
- Mining result: 150 successes, 0 failures.
- Discovery loaded 20 assets, 19 passed data maturity, and 1 valid cohort was
  exported to `data/universes/1m/clusters_20260528_1519.json`.
- Alpha cointegration discovery yielded 14 candidate pairs.
- Pair stress filter tested 14 candidate pairs and promoted 3 candidates into
  the candidate artifact.
- Recoverable Bybit rate-limit warnings occurred during research and were
  handled by fetcher backoff.

Promotion:

```text
.venv/bin/python main.py promote-pairs \
  --pipeline configs/pipelines/dev.yml \
  --operator local-fresh-start
```

- Promoted artifact: `data/universes/1m/surviving_pairs.json`.
- Promotion audit: `data/universes/1m/promotion_audit.jsonl`.
- Promoted artifact metadata:
  - `generated_at`: `2026-05-28T15:19:13.041806+00:00`
  - `timeframe`: `1m`
  - `exchange`: `bybit`
  - `pair_count`: `3`
- Promoted pairs:
  - `ALT/USDT|1000BONK/USDT`, stress Sharpe `18.5837`, PnL `1.3445%`,
    `13` stress trades.
  - `ASTER/USDT|ADA/USDT`, stress Sharpe `3.7825`, PnL `0.1432%`,
    `6` stress trades.
  - `ASTER/USDT|AVAX/USDT`, stress Sharpe `14.4262`, PnL `0.4644%`,
    `8` stress trades.

Refresh:

```text
.venv/bin/python -m src.engine.trader.cli.refresh_pair_data \
  --pipeline configs/pipelines/dev.yml \
  --overlap-bars 5 \
  --missing-lookback-bars 1500 \
  --fetch-limit 1000
```

- First sandboxed attempt failed on DNS access to Bybit. The same command
  succeeded outside the sandbox.
- Scope: Bybit `1m`.
- Symbols refreshed: `5`.
- Started: `2026-05-28T15:20:35.611637+00:00`.
- Finished: `2026-05-28T15:20:41.151885+00:00`.
- `1000BONK/USDT`, `ADA/USDT`, `ALT/USDT`, `ASTER/USDT`, and `AVAX/USDT`
  each fetched `21` bars, saved `1455` bars, and had latest local data at
  `2026-05-28T15:19:00+00:00`.

Reports:

```text
.venv/bin/python -m src.engine.trader.cli.report_generator \
  --pipeline configs/pipelines/dev.yml \
  --pair-validity-window-bars 240 \
  --pair-validity-min-bars 60 \
  --open-position-review-half-life-multiple 3

.venv/bin/python -m src.engine.trader.cli.report_generator \
  --pipeline configs/pipelines/dev.yml \
  --pair-validity-window-bars 240 \
  --pair-validity-min-bars 60 \
  --open-position-review-half-life-multiple 3 \
  --json
```

- Both reports succeeded.
- PyArrow emitted sandbox-only `sysctlbyname` CPU-cache warnings during report
  generation; reports still completed.
- Pair-validity diagnostics covered 3 promoted pairs.
- All 3 pairs carried review reasons:
  `market_data_older_than_artifact_generation` and
  `market_data_older_than_promotion`.
- Pre-execution queue decisions ranked all 3 pairs and blocked all 3 from
  entry with `pair_validity_operator_review_required`.

Bounded state-only execution:

```text
.venv/bin/python main.py execute \
  --pipeline configs/pipelines/dev.yml \
  --strategy configs/strategy/dev.yml \
  --risk configs/risk/alpha_v1.yml \
  --max-ticks 5 \
  --heartbeat-seconds 10
```

- Ran outside the sandbox so Prefect and readonly Bybit market-data fetches
  could operate.
- Prefect temporary server: `http://127.0.0.1:8199`.
- Loaded 3 Tier 1 pairs from 3 total survivors.
- Boot reconciliation status:
  `SKIPPED_NO_SNAPSHOT_PROVIDER`, deltas `0`, no actions taken.
- Completed 5 ticks and auto-stopped.
- Runtime state:
  `observer_run.status = COMPLETED_MAX_TICKS`,
  `max_ticks = 5`, `completed_ticks = 5`,
  `started_at = 2026-05-28T15:21:17.960607+00:00`,
  `completed_at = 2026-05-28T15:23:57.421035+00:00`,
  `open_position_ids = []`.
- All 5 equity snapshots recorded `open_positions = 0`,
  `realized_pnl_pct = 0.0`, `unrealized_pnl_pct = 0.0`, and
  `total_equity_pct = 0.0`.
- `tick_signals` recorded 15 signal rows:
  - `ALT/USDT|1000BONK/USDT`: `FLAT/SKIP` x 5.
  - `ASTER/USDT|ADA/USDT`: `FLAT/SKIP` x 4 and `SHORT_SPREAD/ENTRY` x 1.
  - `ASTER/USDT|AVAX/USDT`: `SHORT_SPREAD/ENTRY` x 5.
- No spread positions were opened.
- No leg fills were recorded.
- No order events were recorded.
- No user commands were recorded.
- No reconciliation deltas were recorded.
- Exchange/client order-id verification:
  `select count(*) from leg_fills where exchange_order_id is not null or client_order_id is not null;`
  returned `0`.

Post-execution report:

- Status: `HEALTHY`.
- Active pairs: `0`.
- Total trades: `0`.
- Total signals recorded: `15`.
- Latest reconciliation run status: `SKIPPED_NO_SNAPSHOT_PROVIDER`.
- Post-execution dynamic queue summary:
  - Rank 1: `ASTER/USDT|AVAX/USDT`, total score `0.91`,
    opportunity score `1.0`, `entry_allowed = false`.
  - Rank 2: `ASTER/USDT|ADA/USDT`, total score `0.905614`,
    opportunity score `0.9780675210249339`, `entry_allowed = false`.
  - Rank 3: `ALT/USDT|1000BONK/USDT`, total score `0.875062`,
    opportunity score `0.8253118127683133`, `entry_allowed = false`.
- Every post-execution queue decision was blocked by
  `pair_validity_operator_review_required`.
- Every post-execution queue decision retained review reasons
  `market_data_older_than_artifact_generation` and
  `market_data_older_than_promotion`.

## Extended State-Only Observation Drill

After the cold lifecycle, promoted-pair data was refreshed again and a longer
bounded state-only execution run was started on 2026-05-28.

Preflight:

- Observer service was not loaded.
- Dev Telegram daemon was not loaded.
- Process scan showed no local trader/observer process before start.
- Dev config still used readonly credentials, `order_execution.mode:
  state_only`, and `execution.pair_queue.mode: future_entries`.

Refresh:

```text
.venv/bin/python -m src.engine.trader.cli.refresh_pair_data \
  --pipeline configs/pipelines/dev.yml \
  --overlap-bars 5 \
  --missing-lookback-bars 1500 \
  --fetch-limit 1000
```

- Started: `2026-05-28T16:08:06.294782+00:00`.
- Finished: `2026-05-28T16:08:13.466780+00:00`.
- Symbols refreshed: `5`.
- Each promoted symbol fetched `54` bars, saved `1503` bars, and had latest
  local data at `2026-05-28T16:07:00+00:00`.

Pre-run report:

- Pair-validity operator review reasons cleared for all 3 promoted pairs.
- Queue decisions allowed entry for all 3 promoted pairs:
  - Rank 1: `ASTER/USDT|AVAX/USDT`, latest action `ENTRY`, latest z
    `3.6797`.
  - Rank 2: `ASTER/USDT|ADA/USDT`, latest action `SKIP`, latest z `2.4452`.
  - Rank 3: `ALT/USDT|1000BONK/USDT`, latest action `SKIP`, latest z
    `-1.2380`.

Longer bounded state-only execution:

```text
.venv/bin/python main.py execute \
  --pipeline configs/pipelines/dev.yml \
  --strategy configs/strategy/dev.yml \
  --risk configs/risk/alpha_v1.yml \
  --max-ticks 180 \
  --heartbeat-seconds 60
```

- Ran outside the sandbox so Prefect and readonly Bybit market-data fetches
  could operate.
- Prefect temporary server: `http://127.0.0.1:8353`.
- Boot reconciliation status:
  `SKIPPED_NO_SNAPSHOT_PROVIDER`, deltas `0`, no actions taken.
- The run was manually stopped with `SIGTERM` after several hours of
  state-only observation. Prefect recorded the flow as crashed/cancelled, and
  the trader logged `Database connection closed cleanly`.
- The process and Prefect temporary server were stopped; follow-up process
  checks showed no `main.py`, trader runtime, or Prefect process.

Observed state-only trades:

- Position 1:
  - Pair: `ALT/USDT|1000BONK/USDT`.
  - Side: `LONG_SPREAD`.
  - Opened: `2026-05-28T16:28:22.878202+00:00`.
  - Closed: `2026-05-28T16:51:20.800304+00:00`.
  - Close reason: `SIGNAL_EXIT`.
  - Holding bars: `23`.
  - Realized PnL: `0.7611%`.
- Position 2:
  - Pair: `ASTER/USDT|ADA/USDT`.
  - Side: `SHORT_SPREAD`.
  - Opened: `2026-05-28T16:32:39.912219+00:00`.
  - Closed: `2026-05-28T20:48:16.381629+00:00`.
  - Close reason: `SIGNAL_EXIT`.
  - Holding bars: `256`.
  - Realized PnL: `0.1821%`.
- Position 3:
  - Pair: `ASTER/USDT|ADA/USDT`.
  - Side: `SHORT_SPREAD`.
  - Opened: `2026-05-29T00:28:32.856274+00:00`.
  - Status after SIGTERM: `OPEN`.
- Position 4:
  - Pair: `ALT/USDT|1000BONK/USDT`.
  - Side: `SHORT_SPREAD`.
  - Opened: `2026-05-29T00:29:57.743064+00:00`.
  - Status after SIGTERM: `OPEN`.

SQLite verification after stop:

- Runtime DB: `data/dev/trades_1m.db`.
- `spread_positions`: `2` closed, `2` open.
- `leg_fills`: `12` rows, all `TARGET_RECORDED`, all `filled_qty = 0`.
- Exchange/client order-id verification:
  `select count(*) from leg_fills where exchange_order_id is not null or client_order_id is not null;`
  returned `0`.
- `order_events`: `6`, all signal events:
  `SIGNAL_ENTRY` x 4 and `SIGNAL_EXIT` x 2.
- `reconciliation_runs`: `2`, both `SKIPPED_NO_SNAPSHOT_PROVIDER`.
- `reconciliation_deltas`: `0`.
- `equity_snapshots`: `150`.
- Latest equity snapshot:
  - Timestamp: `2026-05-29T00:32:48.695255+00:00`.
  - Open positions: `2`.
  - Realized PnL: `0.9432%`.
  - Unrealized PnL: `-0.0716%`.
  - Total equity: `0.8715%`.
- `tick_signals`: `439`.
  - `SKIP`: `299`.
  - `HOLD`: `128`.
  - `ENTRY`: `10`.
  - `EXIT`: `2`.

Post-run report:

- Command:
  `.venv/bin/python -m src.engine.trader.cli.report_generator --pipeline configs/pipelines/dev.yml --json`.
- Status: `HEALTHY`.
- Active pairs: `2`.
- Total closed trades: `2`.
- Total equity: `0.8715%`.
- Realized PnL: `0.9432%`.
- Unrealized PnL: `-0.0716%`.
- Total signals recorded: `439`.
- State ledger:
  - Order events: `6`.
  - Leg targets: `OPEN` x 8, `CLOSE` x 4, all `TARGET_RECORDED`.
  - Latest reconciliation status: `SKIPPED_NO_SNAPSHOT_PROVIDER`.
  - Reconciliation deltas: `0`.
- Pair queue:
  - `ASTER/USDT|AVAX/USDT` remained entry-allowed.
  - `ALT/USDT|1000BONK/USDT` and `ASTER/USDT|ADA/USDT` were blocked by
    `pair_position_limit_reached`.
  - Both open-position pairs carried review reason
    `market_data_older_than_open_position`.
- PyArrow emitted sandbox-only `sysctlbyname` CPU-cache warnings during report
  generation; report still completed.

Stabilization findings from the extended run:

- State-only execution did not write any exchange or client order ids.
- Natural exits were preserved and recorded as signal exits.
- Long readonly Bybit operation exposed rate-limit/network stalls:
  - Bybit `retCode 10006` rate-limit responses appeared around
    `2026-05-28T19:00:07+00:00` and
    `2026-05-28T19:00:22+00:00`.
  - Later market-data requests stalled for long gaps before recovering.
- `runtime_state.observer_run` remained stale after SIGTERM:
  `status = RUNNING`, `completed_ticks = 0`, `completed_at = null`,
  `open_position_ids = []`, even though the database contained 2 open
  state-only positions.
- The next implementation slice should keep focusing on explicit capital-slot
  policy and operator-visible stop/run-state behavior before simulator work.

Post-5-tick-drill process check:

- The 5-tick bounded execution process exited cleanly after
  `COMPLETED_MAX_TICKS`.
- `launchctl` observer service remained not loaded.
- `launchctl` dev Telegram daemon remained not loaded.
- Process scan showed no trader, observer, dev Telegram daemon, or
  `caffeinate` process. Telegram Desktop crash-handler processes still matched
  the broad `telegram` search term.

## What Is Implemented

Architecture and package shape:

- Trader CLI entrypoints live under `src/engine/trader/cli/`.
- Runtime artifact lifecycle lives under `src/engine/trader/runtime/artifacts/`.
- Runtime monitoring lives under `src/engine/trader/runtime/monitoring/`.
- Pair validity lives under `src/engine/trader/runtime/pair_validity/`.
- Dynamic queue ranking lives under `src/engine/trader/runtime/pair_queue/`.
- Canonical imports are under state, signals, runtime, reporting, and CLI
  packages rather than root-level trader compatibility facades.

Artifact lifecycle:

- Research writes candidate artifacts.
- `main.py promote-pairs` validates and promotes candidate artifacts.
- Promotion appends `promotion_audit.jsonl`.
- Execution loads only the promoted artifact on boot.
- Pair recalculation must not force-close or rebalance open positions.

Pair validity and refresh:

- Refresh CLI fetches/appends local OHLCV only for symbols in the promoted
  artifact with readonly credentials.
- Report CLI can compute pair-validity diagnostics and dynamic queue decisions.
- Pair validity reports artifact/data age, recent bars, hedge-ratio drift,
  correlation drift, p-value drift, half-life drift, execution observations, and
  review reasons.
- Refresh does not promote artifacts, reload execution, submit orders, or close
  positions.

Dynamic promoted-pair queue:

- Execution consumes queue decisions for future entries when
  `execution.pair_queue.mode: future_entries`.
- Queue decisions block only new entries.
- Existing positions continue natural-exit evaluation.
- Blocked flip signals close the existing position but skip the replacement
  entry.
- The queue does not place orders, promote artifacts, force-close, or rebalance.

Bounded local execution:

- `main.py execute` supports process-local bounds:
  - `--max-ticks`
  - `--heartbeat-seconds`
- Overrides do not modify YAML.
- Dev should remain on `credential_tier: readonly` and
  `order_execution.mode: state_only`.

## Fresh-Start Drill Order

Before running anything:

1. Confirm no trader, observer, Telegram daemon, or `caffeinate` process is
   active.
2. Confirm `configs/pipelines/dev.yml` still uses:
   - `credential_tier: readonly`
   - `order_execution.mode: state_only`
   - `execution.pair_queue.mode: future_entries`

Run the cold lifecycle:

```bash
.venv/bin/python main.py run \
  --config configs/runs/dev_1m_research.yml

.venv/bin/python main.py promote-pairs \
  --pipeline configs/pipelines/dev.yml \
  --operator local-fresh-start

.venv/bin/python -m src.engine.trader.cli.refresh_pair_data \
  --pipeline configs/pipelines/dev.yml \
  --overlap-bars 5 \
  --missing-lookback-bars 1500 \
  --fetch-limit 1000

.venv/bin/python -m src.engine.trader.cli.report_generator \
  --pipeline configs/pipelines/dev.yml \
  --pair-validity-window-bars 240 \
  --pair-validity-min-bars 60 \
  --open-position-review-half-life-multiple 3

.venv/bin/python -m src.engine.trader.cli.report_generator \
  --pipeline configs/pipelines/dev.yml \
  --pair-validity-window-bars 240 \
  --pair-validity-min-bars 60 \
  --open-position-review-half-life-multiple 3 \
  --json

.venv/bin/python main.py execute \
  --pipeline configs/pipelines/dev.yml \
  --strategy configs/strategy/dev.yml \
  --risk configs/risk/alpha_v1.yml \
  --max-ticks 5 \
  --heartbeat-seconds 10
```

After execution, verify:

```bash
sqlite3 data/dev/trades_1m.db \
  'select id, pair_label, side, status, opened_at, closed_at from spread_positions order by id;'

sqlite3 data/dev/trades_1m.db \
  'select leg_role, status, count(*) from leg_fills group by leg_role, status order by leg_role, status;'

sqlite3 data/dev/trades_1m.db \
  'select count(*) from leg_fills where exchange_order_id is not null or client_order_id is not null;'

sqlite3 data/dev/trades_1m.db \
  'select key, value_json, updated_at from runtime_state order by key;'
```

Any non-zero exchange/client order id count is a stop-and-investigate event.

## Next Implementation Order

Do this before simulator implementation:

1. Tighten capital-slot policy through execution-path tests:
   - global max open positions
   - max positions per pair
   - max positions per asset
   - explicit block reasons
2. Add or tighten pre-trade risk gates:
   - notional sizing
   - leverage
   - exposure
   - precision
   - liquidity policy
   - kill-switch state
3. Strengthen reconciliation and command drills:
   - read-only mismatch snapshots
   - `/pause` and `/resume`
   - `/stop` and `/stop_all` only in archived/dedicated local state
4. Only then start simulator Phase 1.

## Simulator Boundary

The simulator is deferred on purpose.

Reason:

```text
finish the local trader contract first
-> then build simulation against stable public runtime seams
```

Avoid implementing synthetic replay around trader behavior that is still likely
to change, especially capital slots, pre-trade risk gates, reconciliation,
operator kill-switch behavior, and market-data provider seams.

## Safety Boundaries

Do not implement in the same slice:

- real capital increase
- automatic promotion
- automatic scheduled candidate regeneration
- hot reload
- forced closes from pair-set changes
- queue-driven rebalancing
- hidden live exchange mutation
