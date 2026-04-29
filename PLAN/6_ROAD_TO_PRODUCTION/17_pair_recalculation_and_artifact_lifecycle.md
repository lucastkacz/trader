# Pair Recalculation, Artifact Lifecycle & Natural-Exit Policy

## Purpose

The platform now has a clear research-to-execution artifact boundary:

```text
research flow
-> data/universes/{timeframe}/surviving_pairs.json
-> execute flow loads the artifact on boot
-> trader evaluates only those pairs
```

That is enough for a manual dev run, but not enough for an always-on system. Pair
eligibility decays as market structure changes:

```text
clusters drift
cointegration relationships decay
liquidity changes
half-life changes
backtest/stress assumptions age
symbols delist or become stale
```

This document defines the implementation plan for pair recalculation and pair
artifact lifecycle management.

Important terminology:

```text
Pair recalculation:
  Re-running the research/discovery/stress process to produce a new eligible
  pair artifact for future entries.

Rebalancing:
  Actively changing, reducing, closing, or replacing currently open positions
  because the eligible pair set changed.
```

This plan is about **pair recalculation**, not automatic rebalancing.

---

## Core Policy Decision

The default production-safe behavior is:

```text
recalculate eligible pairs for future entries
do not force-close positions merely because a pair falls out of the new artifact
let existing positions close naturally under their normal exit logic
```

If a future auditor or operator decides an open pair is dangerous, that must be
handled as a separate explicit action:

```text
operator /stop
auditor force-close request
risk-policy kill switch
manual emergency process
```

Do not hide forced position changes behind pair recalculation.

---

## Current State

Current artifact path:

```text
data/universes/{timeframe}/surviving_pairs.json
```

Current artifact shape:

```json
{
  "metadata": {
    "schema_version": 1,
    "artifact_type": "surviving_pairs",
    "generated_at": "...",
    "timeframe": "1m",
    "exchange": "bybit",
    "pair_count": 12
  },
  "pairs": []
}
```

Current execution behavior:

```text
LiveTrader loads surviving_pairs.json once during boot
LiveTrader rejects missing/mismatched/malformed artifacts
LiveTrader keeps the loaded pair list in memory for the full process lifetime
LiveTrader does not reload pair artifacts while running
```

Current research behavior:

```text
research can be run manually
research fetches historical candles unless --skip-fetch is used
research recalculates clusters
research recalculates cointegrated pairs
stress testing rewrites surviving_pairs.json
```

Current config surface:

```text
configs/pipelines/dev.yml
configs/pipelines/uat.yml
configs/pipelines/prod.yml
```

There is no pair recalculation cadence config yet.

---

## Non-Negotiables

```text
no live exchange mutation from pair recalculation
no automatic forced close because of pair-set changes
no hidden default recalculation cadence
no raw YAML dicts below the config boundary
no config-origin .get("key", default)
no network calls in unit tests
no broad live-trader rewrites in the same slice as policy changes
no stale list-only surviving_pairs.json artifacts accepted by execute
```

Pair recalculation must be observable, auditable, and reversible.

---

## Target Behavior

### Manual Mode

Manual mode is the first supported mode.

```text
operator runs research
new pair artifact is written
operator restarts trader
trader loads new artifact on boot
new entries use new pair set
old open positions from previous pair sets close naturally if still open
```

Manual mode should be the default for `dev`, `uat`, and `prod` until periodic
automation is explicitly implemented.

### Scheduled Mode

Scheduled mode is future work.

```text
system runs pair recalculation on a configured cadence
new artifact is written as a candidate
candidate is validated
candidate is promoted atomically
trader notices/promotes on next safe boundary or next restart
new entries use promoted artifact
existing positions close naturally
```

Scheduled mode must not be introduced until artifact versioning and state
traceability are complete.

### Hot Reload Mode

Hot reload is later and higher risk.

```text
trader reloads pair artifact while running
new entries use the latest accepted pair set
open positions remain managed even if absent from the latest artifact
```

Hot reload must never interrupt:

```text
entry execution
exit execution
flip handling
command processing
reconciliation writes
```

Do not implement hot reload before the runtime loop has explicit safe reload
boundaries.

---

## Proposed Config Shape

Add a required `pair_refresh` block under pipeline execution.

Example initial shape:

```yaml
pipeline:
  execution:
    pair_refresh:
      mode: "manual"
      max_artifact_age_bars: 1440
      reload_policy: "on_boot"
      stale_open_position_policy: "natural_exit"
```

Field meanings:

```text
mode:
  manual | scheduled

max_artifact_age_bars:
  Maximum allowed artifact age measured in the same bars as pipeline.timeframe.
  Missing is invalid. null may be allowed only if the operator explicitly chooses
  no freshness limit.

reload_policy:
  on_boot | safe_boundary

stale_open_position_policy:
  natural_exit
```

Initial allowed values:

```text
mode: manual
reload_policy: on_boot
stale_open_position_policy: natural_exit
```

Do not add `force_close` as an allowed value in the first implementation.

---

## Artifact Contract Expansion

The current metadata is useful but incomplete for lifecycle validation.

Target metadata:

```json
{
  "schema_version": 1,
  "artifact_type": "surviving_pairs",
  "generated_at": "2026-04-28T00:00:00+00:00",
  "timeframe": "1m",
  "exchange": "bybit",
  "pair_count": 12,
  "data_start_timestamp": "2026-04-27T00:00:00+00:00",
  "data_end_timestamp": "2026-04-28T00:00:00+00:00",
  "historical_days": 1,
  "pipeline_name": "DEV 1M Sandbox",
  "universe_name": "Top 100 Liquid Ex-MegaCaps",
  "strategy_name": "Institutional Mean Reversion V1",
  "backtest_name": "Alpha Stress Test",
  "config_fingerprint": "sha256:..."
}
```

Minimum required metadata for the first lifecycle implementation:

```text
schema_version
artifact_type
generated_at
timeframe
exchange
pair_count
```

Recommended next metadata:

```text
data_end_timestamp
historical_days
pipeline_name
universe_name
strategy_name
backtest_name
config_fingerprint
```

---

## State Traceability

The trader should eventually record which pair artifact was active.

Possible state additions:

```text
runtime_state["active_pair_artifact"]
runtime_state["active_pair_artifact_generated_at"]
runtime_state["active_pair_artifact_fingerprint"]
runtime_state["last_pair_recalculation_seen_at"]
```

When opening a new position, the state should eventually store:

```text
pair_artifact_fingerprint
pair_artifact_generated_at
```

This allows later reporting:

```text
position opened under artifact X
pair later absent from artifact Y
position naturally exited under normal signal logic
```

Do not add schema fields until the runtime policy is fully tested.

---

## Recalculation Semantics

### New Pair Appears

```text
old artifact: pair absent
new artifact: pair present
behavior: pair becomes eligible for future entries
```

No special position handling needed.

### Existing Pair Remains

```text
old artifact: pair present
new artifact: pair present
behavior: pair remains eligible for future entries
```

Future detail: if best params changed, new entries use new params. Existing open
position should keep the values recorded at entry unless explicitly designed
otherwise.

### Pair Disappears With No Open Position

```text
old artifact: pair present
new artifact: pair absent
open position: none
behavior: pair no longer eligible for new entries
```

No close event.

### Pair Disappears With Open Position

```text
old artifact: pair present
new artifact: pair absent
open position: yes
behavior: block new entries for that pair, but manage existing position until
normal exit signal closes it
```

Record/report the condition as:

```text
STALE_OPEN_POSITION_NATURAL_EXIT
```

This is an informational state, not a liquidation command.

---

## Phase 1: Artifact Metadata Completeness

Goal:

```text
Make surviving_pairs.json self-describing enough for safe boot validation.
```

Tasks:

```text
extend build_pair_artifact metadata
include pipeline/universe/strategy/backtest names where available
include historical_days
include data_end_timestamp if available from parquet or research frame
add config fingerprint helper using canonical JSON from typed config models
update research writer
update stress writer
update runtime reader
update reporting reader
```

Tests:

```text
artifact builder includes required metadata
artifact builder computes stable fingerprint for same config
runtime rejects missing generated_at
runtime rejects missing pair_count
runtime rejects mismatched pair_count
runtime rejects timeframe mismatch
runtime rejects exchange mismatch
runtime rejects legacy list-only artifact
reporting can load valid artifact
```

Verification:

```bash
PYTHONPATH=. .venv/bin/pytest tests -m "not live" --tb=short
.venv/bin/ruff check src tests main.py
```

---

## Phase 2: Pair Refresh Config Model

Goal:

```text
Add explicit config for pair artifact freshness and reload policy without
implementing automatic recalculation yet.
```

Tasks:

```text
add PairRefreshConfig model
add pair_refresh block to dev.yml, uat.yml, prod.yml
require mode
require max_artifact_age_bars or explicit null
require reload_policy
require stale_open_position_policy
update config tests
```

Initial allowed values:

```text
mode = manual
reload_policy = on_boot
stale_open_position_policy = natural_exit
```

Tests:

```text
valid dev/uat/prod configs parse
missing pair_refresh fails
missing mode fails
missing max_artifact_age_bars fails
unsupported mode fails
unsupported stale_open_position_policy fails
```

Do not:

```text
run research automatically
reload artifacts while trader is running
close positions due to artifact changes
```

---

## Phase 3: Boot Freshness Validation

Goal:

```text
Trader boot should reject stale or mismatched pair artifacts before evaluating
new entries.
```

Tasks:

```text
parse generated_at
calculate artifact age in bars using pipeline.timeframe
compare age to pair_refresh.max_artifact_age_bars
fail boot if artifact is too old
log loaded artifact metadata
send Telegram boot warning if artifact is accepted but near freshness threshold
```

Tests:

```text
fresh artifact accepted
stale artifact rejected
null max_artifact_age_bars accepts any age only when explicit
invalid generated_at fails
age calculation uses timeframe math
```

Design note:

```text
Freshness should be based on data_end_timestamp when available. Until then,
generated_at is acceptable for dev, but production should prefer data_end_timestamp.
```

---

## Phase 4: Manual Recalculation Runbook

Goal:

```text
Operators can safely refresh pair artifacts manually.
```

Runbook:

```bash
python main.py research \
  --pipeline configs/pipelines/dev.yml \
  --universe configs/universe/alpha_v1.yml \
  --backtest configs/backtest/stress_test.yml \
  --strategy configs/strategy/alpha_v1.yml
```

Then:

```text
inspect artifact metadata
inspect pair_count
optionally generate report
restart dev trader
```

Required docs:

```text
how to identify artifact age
how to inspect pair_count
what happens to old open positions
how to recover if research yields zero pairs
```

---

## Phase 5: Candidate/Promoted Artifact Layout

Goal:

```text
Avoid partially written or unreviewed artifacts becoming active.
```

Proposed layout:

```text
data/universes/{timeframe}/candidate/surviving_pairs_{timestamp}.json
data/universes/{timeframe}/active/surviving_pairs.json
```

Or, if keeping current path:

```text
write surviving_pairs.tmp.json
fsync/close
atomic rename to surviving_pairs.json
archive previous artifact
```

Tasks:

```text
write artifact atomically
archive previous active artifact
record artifact fingerprint
add tests for atomic promotion helper
```

Do not implement scheduled refresh until this exists.

---

## Phase 6: Runtime Visibility

Goal:

```text
Reports and Telegram should show pair artifact state.
```

Surfaces:

```text
Telegram /status
TradeReport
terminal report
markdown report
boot logs
```

Fields:

```text
active artifact generated_at
active artifact age
pair_count
timeframe
exchange
fingerprint
stale open positions count
```

Tests:

```text
status includes artifact metadata when available
report includes artifact metadata when available
missing metadata does not crash report
```

---

## Phase 7: Scheduled Recalculation

Goal:

```text
Allow the system to run research on a configured cadence, producing candidate
artifacts for operator review or automatic promotion.
```

Prerequisites:

```text
Phase 1 metadata complete
Phase 2 config complete
Phase 3 boot freshness validation complete
Phase 5 atomic artifact promotion complete
Phase 6 visibility complete
offline tests green
```

Config extension:

```yaml
pair_refresh:
  mode: "scheduled"
  cadence_bars: 1440
  max_artifact_age_bars: 2880
  reload_policy: "on_boot"
  stale_open_position_policy: "natural_exit"
```

Initial scheduled behavior:

```text
scheduled job writes candidate artifact
operator reviews/promotes manually
trader reloads only on restart
```

Do not start with hot reload.

---

## Phase 8: Safe Boundary Hot Reload

Goal:

```text
Trader can adopt a newly promoted artifact without full process restart.
```

Prerequisites:

```text
single-writer state discipline remains intact
runtime loop has explicit safe boundaries
open position behavior for absent pairs is tested
artifact fingerprint recorded in runtime state
```

Safe reload boundary:

```text
after command processing
before tick pair iteration begins
not during entry/exit/flip
not while reconciliation is writing
```

Behavior:

```text
load new artifact
validate metadata and freshness
replace eligible pair list for future entry checks
keep managing open positions even if absent from new list
record stale-open informational status
```

Tests:

```text
new pair becomes eligible after reload
removed pair with no open position is ignored
removed pair with open position is still evaluated for exit
no forced close occurs
```

---

## Definition Of Done

```text
surviving_pairs.json is fully self-describing
execute rejects stale/mismatched/malformed artifacts
pair_refresh config is explicit in dev/uat/prod
manual recalculation runbook exists
active/candidate artifact promotion is atomic
reports expose active pair artifact state
scheduled recalculation is introduced only after promotion safety exists
hot reload is introduced only after safe runtime boundaries exist
pair recalculation never force-closes positions by default
stale open positions naturally exit unless explicitly acted on by operator/auditor/risk policy
offline tests green
ruff green
```

