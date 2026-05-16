# Handoff: Local Readiness Before Cloud Infra

Updated: 2026-05-16

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
202 passed, 3 deselected
```

Command used:

```bash
PYTHONPATH=. .venv/bin/pytest
```

## Highest Priority Next Run

Run a fresh, more realistic dev/local workflow drill.

Goal:

- Avoid force-promoting hand-picked pairs.
- Tune dev-only research and stress configuration so more pairs are promoted
  through the normal candidate artifact and promotion path.
- Keep the run strictly read-only and state-only.
- Leave the Telegram daemon and observer running for 2-3 hours.
- Confirm positions open, close naturally, and remain inspectable through
  Telegram and reports.

This is a workflow-safety drill, not a profitability drill.

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
  skip_fetch: true
```

Decision before the fresh drill:

- If keeping `data/parquet`, leave `skip_fetch: true`.
- If deleting all `data`, set the dev run profile to fetch fresh data or run the
  relevant data download step first.

## Dev Config Tuning For Natural Promotion

Relevant files:

- `configs/runs/dev_1m_research.yml`
- `configs/pipelines/dev.yml`
- `configs/universe/alpha_v1_dev_1m.yml`
- `configs/backtest/stress_test_dev_1m.yml`
- `configs/strategy/alpha_v1.yml`

Current important gates:

- `configs/pipelines/dev.yml`
  - `credential_tier: "readonly"`
  - `order_execution.mode: "state_only"`
  - `min_sharpe: 1.0`
- `configs/universe/alpha_v1_dev_1m.yml`
  - broader local universe filters than canonical config
  - `p_value_threshold: 0.10`
  - `max_half_life_bars: 180`
- `configs/backtest/stress_test_dev_1m.yml`
  - entry grid: `[1.25, 1.5, 2.0, 2.5]`
  - lookback grid: `[60, 120, 180, 240, 360]`
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

## Drill Acceptance Checklist

During or after the 2-3 hour run, confirm:

- Research writes a candidate eligible-pair artifact.
- Promotion writes `data/universes/1m/surviving_pairs.json`.
- Promotion appends `data/universes/1m/promotion_audit.jsonl`.
- Observer loads promoted pairs on boot.
- Telegram `/status` responds.
- Telegram `/positions` lists open position ids.
- Telegram `/inspect <ID|PAIR>` shows entry, current z-score, prices, and PnL.
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
PYTHONPATH=. .venv/bin/pytest
```

Generate a text report:

```bash
.venv/bin/python -m src.engine.trader.report_generator \
  --db-path data/dev/trades_1m.db \
  --min-sharpe 1.0 \
  --surviving-pairs-path data/universes/1m/surviving_pairs.json
```

Generate parse-safe JSON:

```bash
.venv/bin/python -m src.engine.trader.report_generator \
  --db-path data/dev/trades_1m.db \
  --min-sharpe 1.0 \
  --surviving-pairs-path data/universes/1m/surviving_pairs.json \
  --json
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

