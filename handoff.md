# Handoff: Local Readiness Before Cloud Infra

Updated: 2026-05-17

## Purpose

This handoff is for continuing the local readiness session. The goal is to make
the local dev environment complete, testable, and operator-friendly before
moving attention to UAT, production, or cloud infrastructure.

The project is not being optimized for profitability yet. The immediate goal is
to prove workflow behavior safely:

```text
research / screening
-> candidate eligible-pair artifact
-> operator promotion
-> state-only execution
-> Telegram operator controls
-> reporting, recovery, and auditability
```

Do not call this production-ready for real capital. The production readiness
gate in `docs/engineering-rules.md` still applies.

## Required Context For Every Development Session

Read or keep present:

- `AGENTS.md`
- `CONTEXT.md`
- `docs/index.md`
- `docs/engineering-rules.md`
- `docs/system-design.md`
- `docs/current-roadmap.md` when touching active roadmap work
- `.agents/skills/`

Use project-specific skills when relevant:

- `quant-code-quality-auditor` for safety, test integrity, maintainability, and
  config-boundary scans.
- `improve-quant-architecture` for module shape, adapters, and responsibility
  boundaries.
- `quant-roadmap-maintainer` when updating roadmap state or choosing the next
  implementation slice.

Important repository terms to preserve:

- research flow
- execution flow
- candidate artifact
- eligible pair artifact
- promoted artifact
- pair recalculation
- natural exit
- runtime state
- operational seam

## Current Session State

Branch:

```bash
git branch --show-current
```

Expected active branch:

```text
local-readiness-drills
```

Do not push, merge, or enable live exchange mutation unless explicitly asked.

Latest local commit:

```text
09beeb5c Add env strategy configs and Telegram health controls
```

Current git state immediately after that commit was:

```text
working tree clean
```

Current working tree has uncommitted local-readiness changes from the latest
Telegram/operator slice plus this handoff update. Review before committing:

```text
requirements.txt
src/interfaces/telegram/daemon.py
src/interfaces/telegram/handlers.py
src/interfaces/telegram/renderers.py
src/interfaces/telegram/plots.py
tests/interfaces/telegram/test_daemon.py
handoff.md
```

## Completed In This Session

Local Telegram and state-only readiness work completed:

- Fixed Telegram environment labeling so `[TRADER LIVE]` is not derived from log
  level.
- Fixed Telegram PnL formatting for exit and flip notifications.
- Made report `--json` output parse-safe.
- Made default pytest runs exclude `live` tests through `pytest.ini`.
- Added `docs/local-operator-runbook.md` and linked it from `docs/index.md`.
- Tested dev Telegram bot setup locally.
- Added Telegram `/inspect <ID|PAIR>` for deeper open-position inspection.
- Verified `/pause`, `/resume`, `/stop_all`, and command consumption against
  local SQLite state.
- Ran a wide state-only observer drill with a 12-pair workflow-test artifact.
- Confirmed state-only leg rows did not record exchange or client order ids.
- Split `configs/strategy/alpha_v1.yml` into environment-specific strategy
  config files:
  - `configs/strategy/dev.yml`
  - `configs/strategy/uat.yml`
  - `configs/strategy/prod.yml`
- Updated workflow/config/test references to use the environment-specific
  strategy files.
- Made the dev workflow more permissive, without touching UAT/prod trading
  posture:
  - `configs/pipelines/dev.yml`: `max_symbols: 150`, `min_sharpe: 0.5`
  - `configs/universe/alpha_v1_dev_1m.yml`: wider workflow-drill filters
  - `configs/backtest/stress_test_dev_1m.yml`: wider entry/lookback grid and
    lower workflow-drill friction
  - `configs/strategy/dev.yml`: `entry_z_score: 1.5`
- Re-fetched missing 1m data after local `data/` deletion:
  - 150 symbols total
  - 0 fetch failures
  - 13 discovery candidates
  - 4 stress survivors
- Promoted the 4-pair 1m dev eligible pair artifact:
  - `APT/USDT|BCH/USDT`
  - `1000PEPE/USDT|BCH/USDT`
  - `BCH/USDT|1000BONK/USDT`
  - `BCH/USDT|AVAX/USDT`
- Added Telegram `/pairs` and `/promoted_pairs` to show the promoted artifact.
- Added initial inline `Inspect #id` buttons to `/positions`, later replaced
  by the two-step `Position #id -> Summary | Plot` flow.
- Added Telegram `/health` for runtime health and staleness.
- Added Telegram z-score/PnL plotting:
  - new `src/interfaces/telegram/plots.py`
  - `/plot <ID|PAIR>` sends a PNG chart
  - plot includes z-score path, mean/exit guide, entry guide, entry marker,
    exit marker when closed, and PnL subplot
  - `Refresh Plot #id` inline button sends an updated chart
- Changed `/positions` into a two-step operator flow:
  - `/positions` lists open positions
  - tapping `Position #id` opens a menu with `Summary` and `Plot`
  - direct `/inspect <ID|PAIR>` and `/plot <ID|PAIR>` still work
- Enhanced `/pairs` to include latest observed z-score from persisted
  `tick_signals`, entry gap, and latest action for every promoted pair.
- Added runtime boot health notifications and max-tick auto-stop notifications.
- Refactored the Telegram daemon into:
  - `src/interfaces/telegram/context.py`
  - `src/interfaces/telegram/handlers.py`
  - `src/interfaces/telegram/renderers.py`
  - thin `src/interfaces/telegram/daemon.py`
- Added `src/engine/trader/runtime/health.py`.
- Enabled real Telegram notifications from the dev state-only observer, instead
  of the previous local `NoopNotifier`.
- Fixed report annualization to prefer the surviving-pairs artifact timeframe
  and render sub-hour intervals correctly.

Signal logic issue found and fixed:

- Live exit logic previously used `abs(z_score) <= exit_z`.
- With `exit_z_score: 0.0`, that meant "exactly zero" instead of crossing the
  intended mean boundary.
- Live evaluator now exits side-aware:
  - `LONG_SPREAD` exits when `z_score >= -abs(exit_z)`.
  - `SHORT_SPREAD` exits when `z_score <= abs(exit_z)`.
- The promotion/backtest simulator now uses the same side-aware state machine.
- Added regression tests for live evaluator and simulator long/short exits.

Latest safe offline test result:

```text
220 passed, 3 deselected
```

Command used:

```bash
.venv/bin/python -m pytest
```

## Latest Drill Results

The latest bounded local state-only observer drill completed successfully.

Final local status at handoff time:

- Telegram daemon is running:
  - `com.quant.dev-telegram-daemon`
- Wide dev state-only observer is not running:
  - `com.quant.dev-wide-state-only-observer`
  - `QUANT_OBSERVER_MAX_TICKS=180`
  - `QUANT_OBSERVER_HEARTBEAT_SECONDS=60`
  - latest run completed `180` ticks and auto-stopped cleanly
- `/health` reports `STALE` because the bounded observer stopped, not because
  the DB is corrupt:

```text
Mode: DEV
Status: STALE
Open Positions: 1
Paused: NO
Latest Tick: 2026-05-17T18:25:46.144809+00:00
Tick Age: 63.6m
Equity: +1.5729%
Realized: +1.5348%
Unrealized: +0.0381%
Reconciliation: SKIPPED_NO_SNAPSHOT_PROVIDER | Deltas: 0
```

Current open local state-only position at handoff time is left over from the
bounded run:

```text
10|BCH/USDT|1000BONK/USDT|SHORT_SPREAD|entry_z=3.3009|opened_at=2026-05-17T17:57:04.473046+00:00
```

State-only safety invariant at handoff time:

```text
0 live/client order ids
```

Position lifecycle results:

- `10` total local state-only positions recorded.
- `9` positions closed via `SIGNAL_EXIT`.
- `1` position remains open only because the bounded observer completed before
  it reached natural exit.
- Position `#7`, the previously watched open position, closed naturally:
  - pair: `1000PEPE/USDT|BCH/USDT`
  - side: `LONG_SPREAD`
  - opened: `2026-05-17T13:44:38.862406+00:00`
  - closed: `2026-05-17T17:44:10.763934+00:00`
  - close reason: `SIGNAL_EXIT`
  - realized PnL: `+0.3799%`
- Two additional positions opened and closed naturally after that:
  - `#8 BCH/USDT|1000BONK/USDT SHORT_SPREAD`
  - `#9 BCH/USDT|AVAX/USDT SHORT_SPREAD`

Report checks:

- Text report works.
- JSON report parses cleanly.
- Latest report summary:
  - total equity: `+1.5729%`
  - realized: `+1.5348%`
  - unrealized: `+0.0381%`
  - closed trades: `9`
  - win rate: `77.8%`
  - order events: `19`
  - leg targets: `OPEN: 20`, `CLOSE: 18`
  - user commands: none recorded in this drill window

Recovery behavior observed:

- The observer previously auto-stopped after `max_ticks=180` while two positions
  were open. Restarting resumed from persisted local state and both stale
  positions closed on the next fresh tick.
- The latest observer run also auto-stopped after `max_ticks=180`, this time
  leaving one open state-only position. This is expected for a bounded dev drill,
  but Telegram `/health` currently only reports this as `STALE`.
- This proved useful recovery behavior for dev, but UAT/prod should run on a
  VPS with process supervision, not a laptop.

Operational interpretation:

- The green PnL is a pleasant side effect, not proof of production alpha.
- The real success is that the execution flow is now observable:
  promoted artifact loading, entries, natural exits, state-only leg targets,
  reports, Telegram health, position summary, plots, and `/pairs` z-score
  proximity all worked from persisted runtime state.

## Highest Priority Next Run

Focus on local dev operations, not UAT/prod yet.

Start the next chat from `main`, then create a fresh feature branch before
editing:

```bash
git switch main
git pull --ff-only origin main
git switch -c dev-run-status-drill
```

Do not continue new implementation work directly on `main`. Keep the next
branch focused on local run-status/drill-status operations.

Recommended next implementation slice:

1. Add a Telegram `/drill` or `/run_status` command that explains the local run
   lifecycle in one place:
   - whether the observer process is running or stopped
   - whether the latest stale health is expected because max ticks completed
   - latest tick age
   - open/closed position counts
   - current open position ids
   - state-only order-id invariant
   - latest reconciliation status and delta count
   - report JSON parse status
2. Distinguish operationally between:
   - actively running and fresh
   - cleanly stopped after bounded max ticks
   - stale unexpectedly
3. Consider a max-tick completion Telegram notification that explicitly says:

```text
Observer completed 180 ticks.
Open local positions remain: 1.
No exchange exposure exists in state-only mode.
Restart observer to continue natural-exit evaluation.
```

4. Add or document restart/resume drills for:
   - observer stops mid-tick and resumes without duplicate entry/exit events
   - `/pause` persists across restart and blocks new entries
   - `/stop_all` is claimed once across restart
   - same-pair re-entry works after natural exit, never while already open

Recommended later discussion, after dev operations are tighter:

- Define the real UAT/prod hosting model on a cloud VPS.
- Decide process supervision:
   - systemd service
   - restart policy
   - log rotation
   - health checks
- Decide reconciliation expectations for UAT/prod:
   - snapshot provider available
   - boot warning vs halt behavior
   - stale local/exchange mismatch policy
- Decide whether to add runtime decay/time-stop controls:
   - alert-only after `N * Half_Life`
   - optional dev-only state close after max holding bars
   - no hidden forced closes from pair-set changes

This is still a workflow-safety drill, not a profitability drill.

## Fresh Data Reset Plan

Before deleting or clearing local data:

- Stop the observer.
- Consider stopping the Telegram daemon too, or be ready to restart it after
  the DB path is recreated.
- Confirm no matching local observer/trader process is active.

Useful checks:

```bash
launchctl print gui/$(id -u)/com.quant.dev-wide-state-only-observer
launchctl print gui/$(id -u)/com.quant.dev-state-only-observer
launchctl print gui/$(id -u)/com.quant.dev-telegram-daemon
ps aux | rg -i 'quant|dev-state-only|run_dev_state|main.py|execute|executor|caffeinate'
```

Important data warning:

- Deleting `data/dev` and `data/universes/1m` clears runtime state and pair
  artifacts.
- Deleting the whole `data` folder also removes `data/parquet`.
- If `data/parquet` is deleted, `configs/runs/dev_1m_research.yml` cannot keep
  `skip_fetch: true`; the research flow must fetch data again using read-only
  market-data access.

Current run profile:

```yaml
run:
  skip_fetch: false
```

Decision before the fresh drill:

- If keeping `data/parquet`, leave `skip_fetch: true`.
- If deleting all `data`, set the dev run profile to fetch fresh data or run the
  relevant data download step first.

Current decision:

- `data` was deleted locally, so `configs/runs/dev_1m_research.yml` now uses
  `skip_fetch: false`.
- Current `data/parquet` has been rebuilt by the dev 1m fetch process. If a new
  chat deletes `data/` again, keep `skip_fetch: false` or fetch again first.

## Dev Config Tuning For Natural Promotion

Relevant files:

- `configs/runs/dev_1m_research.yml`
- `configs/pipelines/dev.yml`
- `configs/universe/alpha_v1_dev_1m.yml`
- `configs/backtest/stress_test_dev_1m.yml`
- `configs/strategy/dev.yml`
- `configs/strategy/uat.yml`
- `configs/strategy/prod.yml`

Current important gates:

- `configs/pipelines/dev.yml`
  - `credential_tier: "readonly"`
  - `order_execution.mode: "state_only"`
  - `min_sharpe: 0.5`
  - `max_symbols: 150`
- `configs/universe/alpha_v1_dev_1m.yml`
  - broader local universe filters than canonical config
  - `p_value_threshold: 0.15`
  - `max_half_life_bars: 240`
  - `louvain_correlation_threshold: 0.3`
- `configs/backtest/stress_test_dev_1m.yml`
  - entry grid: `[1.0, 1.25, 1.5, 2.0, 2.5]`
  - lookback grid: `[45, 60, 120, 180, 240, 360]`
  - workflow-drill friction: maker `0.0001`, taker `0.0004`, annual funding `0.05`
- `src/research/pair_stress_filter.py`
  - rejects candidates with `best_net_pnl <= 0`

Important implication:

- Lowering `min_sharpe` alone is not enough to naturally promote many pairs.
- The stress filter also requires positive net PnL before a pair becomes a
  candidate survivor.

Recommended approach for the drill:

1. Keep `configs/pipelines/dev.yml` read-only and state-only.
2. Make dev-only research/stress settings more permissive:
   - Lower `min_sharpe` for runtime loading/reporting.
   - Consider lower friction assumptions in `stress_test_dev_1m.yml` for the
     workflow drill.
   - Consider a wider entry grid such as lower entry thresholds to create more
     simulated trades.
   - Consider loosening dev universe cointegration and clustering thresholds.
3. If positive-PnL gating still leaves too few pairs, decide whether to add a
   typed, explicit dev-only workflow-test acceptance policy. Do not hide this in
   ad hoc code or raw config dictionaries.

Do not change UAT or prod config for this drill.

Current promoted dev 1m artifact:

```text
data/universes/1m/surviving_pairs.json
pair_count=4
```

## Drill Acceptance Checklist

During or after the 2-3 hour run, confirm:

- Research writes a candidate eligible-pair artifact.
- Promotion writes `data/universes/1m/surviving_pairs.json`.
- Promotion appends `data/universes/1m/promotion_audit.jsonl`.
- Observer loads promoted pairs on boot.
- Telegram `/status` responds.
- Telegram `/health` responds and reports fresh tick age.
- Telegram `/pairs` shows the promoted 4-pair artifact.
- Telegram `/pairs` shows latest z-score, entry gap, and latest action for each
  promoted pair.
- Telegram `/positions` lists open position ids.
- Telegram `/positions` opens the two-step `Position #id -> Summary | Plot`
  menu.
- Telegram `/inspect <ID|PAIR>` shows entry, current z-score, prices, and PnL.
- Telegram `/plot <ID|PAIR>` sends a z-score/PnL PNG and refresh button.
- At least one position opens naturally.
- At least one position closes naturally, if market movement permits.
- Exit notifications format PnL correctly.
- Report CLI works in text and JSON modes.
- `user_commands` are claimed and completed for `/pause`, `/resume`, and at
  least one stop command.
- `leg_fills` remains state-only.

State-only safety invariant:

```sql
select count(*)
from leg_fills
where exchange_order_id is not null
   or client_order_id is not null;
```

Expected result:

```text
0
```

Any non-zero result is a stop-and-investigate event.

## Useful Commands

Run safe offline tests:

```bash
.venv/bin/python -m pytest
```

Generate a text report:

```bash
.venv/bin/python -m src.engine.trader.report_generator \
  --db-path data/dev/trades_1m.db \
  --min-sharpe 0.5 \
  --surviving-pairs-path data/universes/1m/surviving_pairs.json
```

Generate parse-safe JSON:

```bash
.venv/bin/python -m src.engine.trader.report_generator \
  --db-path data/dev/trades_1m.db \
  --min-sharpe 0.5 \
  --surviving-pairs-path data/universes/1m/surviving_pairs.json \
  --json
```

Render current Telegram health in the terminal:

```bash
.venv/bin/python -c "from src.interfaces.telegram import context as c; from src.engine.trader.runtime.health import build_trader_health_snapshot, render_trader_health_snapshot; c.configure_daemon('configs/telegram/dev.yml'); s=c.open_state_manager(); snap=build_trader_health_snapshot(s, environment=c.environment_label() or 'N/A', stale_after_minutes=c.health_stale_after_minutes()); print(render_trader_health_snapshot(snap)); s.close()"
```

Inspect positions:

```bash
sqlite3 data/dev/trades_1m.db \
  'select id, pair_label, side, status, opened_at, closed_at from spread_positions order by id;'
```

Inspect leg lifecycle:

```bash
sqlite3 data/dev/trades_1m.db \
  'select leg_role, status, count(*) from leg_fills group by leg_role, status order by leg_role, status;'
```

Inspect commands:

```bash
sqlite3 data/dev/trades_1m.db \
  'select id, command, target_pair, status, timestamp, claimed_at, completed_at, error from user_commands order by id;'
```

## Do Not Do Yet

- Do not enable live order execution.
- Do not increase real-capital exposure.
- Do not implement scheduled pair refresh.
- Do not implement hot reload.
- Do not implement automatic rebalancing.
- Do not force-close positions because of pair-set changes.
- Do not push unless explicitly asked.
