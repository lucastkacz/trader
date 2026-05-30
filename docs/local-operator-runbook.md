# Local Operator Runbook

This runbook is for local development drills only. Keep `configs/pipelines/dev.yml`
on `credential_tier: "readonly"` and `order_execution.mode: "state_only"` unless
you are deliberately changing a tested execution mode.

Do not use this runbook as real-capital production approval. The production
readiness gate in `docs/engineering-rules.md` still applies.

## 0. Fresh-Start Rule

If `data/` has been deleted, treat the next run as a cold local rebuild. Do not
resume assumptions from an old handoff, old database, or old promoted artifact.
The supported rebuild order is:

```text
research
-> promote candidate artifact
-> refresh promoted-pair market data
-> generate report
-> bounded state-only execution
-> verify local state
```

Do not create files in `data/` by hand except for archiving/restoring known local
operator artifacts. Let the CLI flows recreate the runtime database, parquet
store, promoted artifact, and reports.

## 1. Confirm The Local Observer Is Not Running

Check launchd:

```bash
launchctl print gui/$(id -u)/com.quant.dev-state-only-observer
```

If the service is not loaded, launchd prints an error. That is fine for a clean
local start.

Check for matching processes:

```bash
ps aux | rg -i 'quant|dev-state-only|run_dev_state|main.py|execute|executor|caffeinate'
```

Stop before continuing if an unexpected trader, observer, or `caffeinate`
process is active.

## 2. Start A Bounded Dev State-Only Observer

Use the execution entrypoint with CLI-only bounds. Keep the dev pipeline on
read-only credentials, state-only execution, and queue-driven future-entry
selection:

```bash
.venv/bin/python main.py execute \
  --pipeline configs/pipelines/dev.yml \
  --strategy configs/strategy/dev.yml \
  --risk configs/risk/alpha_v1.yml \
  --max-ticks 30 \
  --heartbeat-seconds 60
```

`--max-ticks` and `--heartbeat-seconds` override only the in-memory runtime
config for this process. They do not modify YAML. Use larger values for longer
manual lifecycle drills.

With `execution.pair_queue.mode: future_entries`, execution builds dynamic queue
decisions before each tick transition. Queue decisions may block new entries,
but they must not force-close, rebalance, promote artifacts, hot-reload
execution, or bypass natural-exit evaluation for existing positions.

If this is a cold local rebuild, do not start the observer before running the
research, promotion, refresh, and report steps below. Execution needs a promoted
artifact to load on boot.

## 3. Stop The Observer

For foreground runs, interrupt the terminal process and then repeat the process
check in section 1. A run with `--max-ticks` should auto-stop cleanly after the
configured number of ticks.

## 4. Inspect SQLite Runtime State

Open positions:

```bash
sqlite3 data/dev/trades_1m.db \
  'select id, pair_label, side, status, opened_at, closed_at from spread_positions order by id;'
```

Leg lifecycle status:

```bash
sqlite3 data/dev/trades_1m.db \
  'select leg_role, status, count(*) from leg_fills group by leg_role, status order by leg_role, status;'
```

Operator commands:

```bash
sqlite3 data/dev/trades_1m.db \
  'select id, command, target_pair, status, timestamp, claimed_at, completed_at, error from user_commands order by id;'
```

Reconciliation runs:

```bash
sqlite3 data/dev/trades_1m.db \
  'select id, status, started_at, finished_at from reconciliation_runs order by id;'
```

## 5. Control The Runtime Risk Kill Switch

Use the durable risk kill switch when the operator wants to block future
entries while preserving normal natural-exit handling for existing positions.
This is a local SQLite runtime-state control. It does not submit, cancel,
modify, rebalance, force-close, hot-reload, promote artifacts, or mutate
exchange state.

Inspect current state:

```bash
.venv/bin/python -m src.engine.trader.cli.risk_kill_switch \
  --pipeline configs/pipelines/dev.yml \
  inspect
```

Automation-safe JSON inspect:

```bash
.venv/bin/python -m src.engine.trader.cli.risk_kill_switch \
  --pipeline configs/pipelines/dev.yml \
  --json \
  inspect
```

Activate the switch with an operator-visible reason:

```bash
.venv/bin/python -m src.engine.trader.cli.risk_kill_switch \
  --pipeline configs/pipelines/dev.yml \
  activate \
  --reason "operator review"
```

Clear the switch:

```bash
.venv/bin/python -m src.engine.trader.cli.risk_kill_switch \
  --pipeline configs/pipelines/dev.yml \
  clear
```

The same control is available through the top-level CLI:

```bash
.venv/bin/python main.py risk-kill-switch \
  --pipeline configs/pipelines/dev.yml \
  inspect
```

When active, new entries and flip replacement entries are blocked with
`risk_kill_switch_active`. Existing open state-only positions should continue
under natural exit unless a separate explicit operator command is issued.

## 6. Refresh Pair Data And Generate Validity Reports

Refresh local parquet data for symbols in the promoted pair artifact before
using pair-validity diagnostics. This is a readonly market-data operation and
does not promote artifacts, hot-reload execution, submit orders, or close
positions.

```bash
.venv/bin/python -m src.engine.trader.cli.refresh_pair_data \
  --pipeline configs/pipelines/dev.yml \
  --overlap-bars 5 \
  --missing-lookback-bars 1500 \
  --fetch-limit 1000
```

Human-readable report:

```bash
.venv/bin/python -m src.engine.trader.cli.report_generator \
  --pipeline configs/pipelines/dev.yml \
  --pair-validity-window-bars 240 \
  --pair-validity-min-bars 60 \
  --open-position-review-half-life-multiple 3
```

When pair-validity diagnostics are enabled, the report also includes the dynamic
pair queue. This queue ranks promoted pairs for future entries using the
promoted artifact, validity diagnostics, latest persisted tick signals, and
current open-position exposure. Report generation is read-only. In execution,
the same configured queue policy may block new entries only; it must not place
orders by itself, hot-reload execution, promote artifacts, force-close, or
rebalance positions.

Automation-safe JSON report:

```bash
.venv/bin/python -m src.engine.trader.cli.report_generator \
  --pipeline configs/pipelines/dev.yml \
  --pair-validity-window-bars 240 \
  --pair-validity-min-bars 60 \
  --open-position-review-half-life-multiple 3 \
  --json
```

For a cold local rebuild, run research and promotion before this section:

```bash
.venv/bin/python main.py run \
  --config configs/runs/dev_1m_research.yml

.venv/bin/python main.py promote-pairs \
  --pipeline configs/pipelines/dev.yml \
  --operator local-fresh-start
```

After promotion, run the refresh and report commands above before starting a
bounded execution observer.

## 7. Confirm No Exchange Mutation Happened

Any non-zero result here is a stop-and-investigate event:

```bash
sqlite3 data/dev/trades_1m.db \
  'select count(*) from leg_fills where exchange_order_id is not null or client_order_id is not null;'
```

State-only runs should record local leg targets without exchange or client order
ids.

## 8. Telegram Command Drill

Use the dev Telegram config:

```bash
.venv/bin/python -m src.interfaces.telegram.daemon \
  --config configs/telegram/dev.yml
```

To leave the local daemon running under launchd:

```bash
launchctl bootstrap gui/$(id -u) logs/com.quant.dev-telegram-daemon.plist
launchctl print gui/$(id -u)/com.quant.dev-telegram-daemon
```

Stop it with:

```bash
launchctl bootout gui/$(id -u)/com.quant.dev-telegram-daemon
```

Send commands from the configured dev chat:

```text
/status
/positions
/inspect <ID|PAIR>
/pause
/resume
/stop <PAIR>
/stop_all
```

Then inspect `user_commands` in SQLite. In state-only mode these commands mutate
local runtime state only; they must not submit, cancel, or close exchange orders.

## 9. Archive Local Data Before Clearing

Archive the current dev database and promoted artifact before a fresh drill:

```bash
mkdir -p data/dev/archive
cp data/dev/trades_1m.db data/dev/archive/trades_1m.$(date +%Y%m%d_%H%M%S).db
cp data/universes/1m/surviving_pairs.json data/dev/archive/surviving_pairs.$(date +%Y%m%d_%H%M%S).json
```

Only clear or replace local files after archiving and after confirming no
observer process is running.
