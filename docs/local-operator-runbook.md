# Local State-Only Operator Runbook

**Scope:** bounded local drills with an existing valid promoted artifact and
market data.

**Last command/schema review:** 2026-07-17.

This runbook does not certify a cold start, paper trading, demo/testnet, live
execution, or real-capital readiness. Keep:

```text
configs/exchange/venues/dev.yml      credential_tier: readonly
configs/pipelines/dev.yml            order_execution.mode: state_only
```

`state_only` evaluates signals and mutates local SQLite state. It does not
simulate fills, fees, funding, slippage, rejections, partial orders, or exchange
recovery. Its PnL is theoretical.

## Current Cold-Start Status

A rebuild from an empty `data/` directory is **not yet a supported operator
procedure**. The intended flow is:

```text
readonly market data
-> universe manifest
-> research and stress evaluation
-> manual promotion
-> readonly refresh and report
-> bounded state_only execution
-> restart verification
```

Symbol round-trip, universe handoff, artifact provenance, restart ownership, and
natural exit still have open work in `docs/current-roadmap.md`. Until its
Milestone 1 definition of done passes, do not use one successful manual research
run as evidence that the cold-start contract works.

The supported drill below starts only when the promoted artifact already exists
and its data provenance is understood.

## 1. Preflight

Run from the repository root with the project virtual environment available.

Confirm the required versioned inputs and current runtime artifact exist:

```bash
test -f configs/pipelines/dev.yml
test -f configs/exchange/venues/dev.yml
test -f configs/exchange/market_profiles/linear_usdt_swap.yml
test -f configs/strategy/dev.yml
test -f configs/risk/alpha_v1.yml
test -s data/universes/1m/surviving_pairs.json
```

Any failure is a stop condition. In particular, do not invent or hand-edit a
promoted artifact to get past boot validation.

Confirm config safety:

```bash
rg -n 'credential_tier|order_execution|mode:' \
  configs/exchange/venues/dev.yml \
  configs/pipelines/dev.yml
```

Stop if the effective values are not `readonly` and `state_only`.

Check for an existing process:

```bash
ps aux | rg -i 'main.py execute|src.interfaces.telegram.daemon|caffeinate'
```

An unexpected trader or Telegram daemon is a stop-and-investigate event. This
repository does not version a `launchd` plist, so no background service is
assumed or supported by this runbook.

## 2. Optional Readonly Refresh And Report

Refresh local OHLCV for the symbols in the promoted artifact:

```bash
.venv/bin/python -m src.engine.trader.cli.refresh_pair_data \
  --pipeline configs/pipelines/dev.yml \
  --venue configs/exchange/venues/dev.yml \
  --market-profile configs/exchange/market_profiles/linear_usdt_swap.yml \
  --overlap-bars 5 \
  --missing-lookback-bars 1500 \
  --fetch-limit 1000
```

This command is readonly with respect to the exchange. It writes local Parquet,
but does not promote artifacts, hot-reload execution, submit orders, or close
positions. Treat `INCOMPLETE`, stale data, symbol mismatch, or fetch exhaustion
as a stop condition.

Generate a human-readable report:

```bash
.venv/bin/python -m src.engine.trader.cli.report_generator \
  --pipeline configs/pipelines/dev.yml \
  --pair-validity-window-bars 240 \
  --pair-validity-min-bars 60 \
  --max-latest-data-age-bars 5 \
  --open-position-review-half-life-multiple 3
```

Generate automation-safe JSON when needed:

```bash
.venv/bin/python -m src.engine.trader.cli.report_generator \
  --pipeline configs/pipelines/dev.yml \
  --pair-validity-window-bars 240 \
  --pair-validity-min-bars 60 \
  --max-latest-data-age-bars 5 \
  --open-position-review-half-life-multiple 3 \
  --json
```

Pair validity and queue decisions are evidence for future entries. They do not
authorize promotion, rebalancing, or forced closes.

## 3. Start A Bounded Foreground Drill

```bash
.venv/bin/python main.py execute \
  --pipeline configs/pipelines/dev.yml \
  --venue configs/exchange/venues/dev.yml \
  --market-profile configs/exchange/market_profiles/linear_usdt_swap.yml \
  --strategy configs/strategy/dev.yml \
  --risk configs/risk/alpha_v1.yml \
  --max-ticks 30 \
  --heartbeat-seconds 60
```

The two bounds override only the in-memory config for this process. They do not
edit YAML. Keep the process in the foreground so lifecycle and failures remain
visible.

Boot may still stop because the promoted artifact is absent, stale, invalid, for
the wrong exchange/timeframe, or contains no Tier 1 pairs. Do not weaken the
validator to continue a drill.

To stop a foreground run, interrupt the terminal process. A bounded run should
also stop after `--max-ticks` and record its run status.

## 4. Inspect Local Runtime State

The configured dev database is `data/dev/trades_1m.db`. Check it exists before
using the following queries:

```bash
test -s data/dev/trades_1m.db
```

Positions:

```bash
sqlite3 data/dev/trades_1m.db \
  'select id, pair_label, side, status, opened_at, closed_at from spread_positions order by id;'
```

Leg lifecycle:

```bash
sqlite3 data/dev/trades_1m.db \
  'select leg_role, status, count(*) from leg_fills group by leg_role, status order by leg_role, status;'
```

Commands:

```bash
sqlite3 data/dev/trades_1m.db \
  'select id, command, target_pair, status, timestamp, claimed_at, completed_at, error from user_commands order by id;'
```

Reconciliation runs and deltas:

```bash
sqlite3 data/dev/trades_1m.db \
  'select id, status, started_at, finished_at from reconciliation_runs order by id;'

sqlite3 data/dev/trades_1m.db \
  'select run_id, delta_type, symbol, spread_id, action_taken from reconciliation_deltas order by id;'
```

Boot reconciliation is diagnostic and readonly. Its current `NO_ACTION` results
do not repair state or block execution.

## 5. Verify State-Only Evidence

This query should return zero:

```bash
sqlite3 data/dev/trades_1m.db \
  'select count(*) from leg_fills where exchange_order_id is not null or client_order_id is not null;'
```

A non-zero value is a stop-and-investigate event. A zero proves only that the
local rows have no recorded exchange/client order IDs; it is not a universal
proof that no external mutation happened outside this process.

Also review the logs for unexpected credential tier, execution mode, fetch
failure, reconciliation delta, or validation warning.

## 6. Risk Kill Switch

The durable kill switch blocks future entries and flip replacement entries in
the selected SQLite database. It does not pause the process, cancel orders,
flatten positions, repair state, or mutate the exchange.

Inspect:

```bash
.venv/bin/python main.py risk-kill-switch \
  --pipeline configs/pipelines/dev.yml \
  inspect
```

Activate with a visible reason:

```bash
.venv/bin/python -m src.engine.trader.cli.risk_kill_switch \
  --pipeline configs/pipelines/dev.yml \
  activate \
  --reason "operator review"
```

Clear:

```bash
.venv/bin/python -m src.engine.trader.cli.risk_kill_switch \
  --pipeline configs/pipelines/dev.yml \
  clear
```

Known limitations: a malformed persisted payload is not yet guaranteed to fail
closed, and a mistyped DB target can create or inspect the wrong database. Check
the pipeline path and inspect the resulting state after every change.

Do not claim that activating the switch guarantees natural exits. Pause,
missing data, and artifact/restart gaps can still prevent exit evaluation.

## 7. Telegram Foreground Drill

Run the daemon in a visible terminal:

```bash
.venv/bin/python -m src.interfaces.telegram.daemon \
  --config configs/telegram/dev.yml
```

Available commands include:

```text
/status
/positions
/inspect <ID|PAIR>
/pause
/resume
/stop <PAIR>
/stop_all
```

Inspect `user_commands` afterward. In the current `state_only` flow, stop
commands mutate local state only. They do not cancel or flatten exchange
positions. Pause currently skips the entire tick, including mark-to-market and
exit evaluation.

No background daemon installation is documented until its lifecycle and plist
are versioned and tested.

## 8. Archive Before Replacing Local State

First stop the observer and confirm no matching process remains. Then archive
only files that actually exist:

```bash
mkdir -p data/dev/archive
test -f data/dev/trades_1m.db && \
  cp data/dev/trades_1m.db data/dev/archive/trades_1m.$(date +%Y%m%d_%H%M%S).db
test -f data/universes/1m/surviving_pairs.json && \
  cp data/universes/1m/surviving_pairs.json \
  data/dev/archive/surviving_pairs.$(date +%Y%m%d_%H%M%S).json
```

This runbook does not authorize deleting or manually rewriting runtime data.

## Stop Conditions

Stop the drill and investigate when any of these occur:

- effective mode or credential tier differs from `state_only`/`readonly`;
- promoted artifact is missing, stale, mismatched, or manually fabricated;
- refresh is incomplete or candles are stale/discontinuous;
- an unexpected trader/daemon already owns the local state;
- reconciliation reports a delta or snapshot failure;
- exchange/client order IDs appear in a state-only drill;
- the process requires weakening validation to continue.
