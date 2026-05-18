# Handoff: Local Readiness Before Cloud Infra

Updated: 2026-05-18

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
pair-validity-readonly-diagnostics
```

Do not merge or enable live exchange mutation unless explicitly asked. The user
has asked to commit and push the current branch after this handoff/docs update.

Branch started clean from:

```text
main
```

Latest verified offline test result in this continuation:

```text
230 passed, 3 deselected
```

Current working tree before commit contains:

```text
handoff.md
docs/index.md
docs/local-operator-runbook.md
docs/engineering-rules.md
docs/current-roadmap.md
docs/system-design.md
src/engine/trader/report_generator.py
src/engine/trader/refresh_pair_data.py
src/engine/trader/reporting/
src/engine/trader/runtime/artifacts/
src/engine/trader/runtime/monitoring/
src/engine/trader/runtime/pair_validity/
src/engine/trader/runtime/pairs.py
src/engine/trader/runtime/trader_runner.py
src/interfaces/telegram/handlers/runtime.py
src/interfaces/telegram/rendering/runtime.py
src/research/pair_stress_report.py
tests/engine/trader/runtime/test_pair_data_refresh.py
tests/engine/trader/runtime/test_pair_validity.py
tests/engine/trader/runtime/test_health.py
tests/interfaces/telegram/test_daemon.py
```

Local `data/parquet` was refreshed for promoted dev symbols during inspection,
but data files are not part of the git commit.

## Completed In This Session

Continuation work completed on `2026-05-18`:

- Added read-only pair-validity diagnostics behind
  `src/engine/trader/runtime/pair_validity/`.
- Added optional report CLI pair-validity output:
  - artifact/data age in bars/time
  - hedge-ratio drift
  - correlation drift
  - cointegration p-value drift
  - half-life drift
  - execution behavior counts
  - review reasons
  - explicit missing-baseline notes
- Added readonly promoted-symbol OHLCV refresh CLI:
  - `src/engine/trader/refresh_pair_data.py`
  - fetches only symbols present in the promoted artifact
  - requires `execution.credential_tier: "readonly"`
  - writes local parquet only
  - does not promote artifacts, hot-reload execution, submit orders, or close
    positions
- Ran the refresh against the current dev promoted artifact:
  - symbols: `1000BONK/USDT`, `1000PEPE/USDT`, `APT/USDT`, `AVAX/USDT`,
    `BCH/USDT`
  - each symbol now has `3433` local 1m rows
  - local parquet range for those symbols:
    `2026-05-15T22:50:00+00:00` to `2026-05-18T08:02:00+00:00`
- Reran pair-validity diagnostics after refresh:
  - stale-data warnings cleared
  - all promoted pairs show `1931` bars since artifact generation
  - only review item is open local state-only position `#10`
    `BCH/USDT|1000BONK/USDT`
  - position `#10` shows `844` bars open and `10.71x` research half-life
  - review reason: `open_position_exceeds_half_life_multiple`
- Fixed pair-validity diagnostics so stale local parquet is explicitly reported
  as:
  - `market_data_older_than_artifact_generation`
  - `market_data_older_than_promotion`
  - `market_data_older_than_open_position`
- Added offline tests with fake fetchers for refresh behavior. Unit tests do
  not call the network.
- Refactored runtime package shape:
  - `src/engine/trader/runtime/artifacts/` for eligible-pair artifact contract,
    lifecycle, rows, and promotion audit
  - `src/engine/trader/runtime/monitoring/` for health and run-status snapshots
  - `src/engine/trader/runtime/pair_validity/` for diagnostics, refresh,
    statistics, market-data loading, state summaries, and typed models
- Removed old root runtime files:
  - `runtime/health.py`
  - `runtime/run_status.py`
  - `runtime/pair_artifact_contract.py`
  - `runtime/pair_artifact_lifecycle.py`
  - `runtime/pair_artifact_promotion_audit.py`
  - `runtime/pair_artifact_rows.py`
- Updated docs:
  - `docs/engineering-rules.md`
  - `docs/current-roadmap.md`
  - `docs/system-design.md`
  - `docs/index.md`
  - `docs/local-operator-runbook.md`

Important architecture gap still open:

- `src/engine/trader/` still has root-level compatibility facades and CLI
  entrypoints:
  - `live_trader.py`
  - `signal_engine.py`
  - `state_manager.py`
  - `report_engine.py`
  - `promote_pairs.py`
  - `report_generator.py`
  - `refresh_pair_data.py`
- Preferred next architecture slice:
  - move CLI entrypoints under `src/engine/trader/cli/`
  - update callers to canonical paths:
    `state.manager`, `signals`, `runtime.trader`, `reporting`, and `cli`
  - delete root-level facades instead of preserving duplicate import paths

Remaining functional gaps:

- Telegram does not yet show pair-validity diagnostics.
- Candidate/promoted artifacts still lack full research baseline fields:
  research window start/end, bars used, baseline correlation, spread mean/std,
  and z-score distribution stats.
- Entry gating has not been implemented and should remain deferred until
  diagnostics and thresholds are operator-reviewed.
- Scheduled refresh/candidate regeneration remains later work.

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
- Added Telegram `/menu` as a button-based operator tree while keeping direct
  slash commands available.
- Added Telegram `/run_status` and `/drill` for local run lifecycle status.
- Added persisted observer run markers so bounded max-tick completion can be
  distinguished from unexpected stale runtime state.
- Updated max-tick completion notification to say how many local open positions
  remain and, in state-only mode, that no exchange exposure exists.
- Split Telegram renderers into `src/interfaces/telegram/rendering/` modules:
  - `formatting.py`
  - `menu.py`
  - `positions.py`
  - `pairs.py`
  - `runtime.py`
  - `renderers.py` now remains as a compatibility facade.
- Split Telegram handlers into `src/interfaces/telegram/handlers/` modules:
  - `auth.py`
  - `menu.py`
  - `runtime.py`
  - `positions.py`
  - `pairs.py`
  - `controls.py`
  - `handlers/__init__.py` remains as a compatibility facade.
- Restarted `com.quant.dev-telegram-daemon` after the handler split and tested
  `/menu` manually in Telegram.
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

Latest safe offline test result after the Telegram menu/run-status work and
handler/renderer split:

```text
223 passed, 3 deselected
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

## Highest Priority Next Work: Quantified Pair Validity And Refresh Cycle

The Telegram operator console is now usable enough for local dev. The next
foundation topic is the effective life of promoted statistical-arbitrage pairs.

Important design position from the user:

- Avoid vague artifact-age labels such as `FRESH`, `AGING`, or `STALE` as the
  primary interface. They do not explain risk or action.
- Prefer quantified diagnostics: exact artifact/data age, bars elapsed, drift
  percentages, half-life multiples, p-values, correlations, z-score distribution
  changes, and execution-vs-research deltas.
- If a short status is shown in Telegram, it must sit beside the underlying
  numbers and the operator action. The numbers are the product.

Current implementation status:

- The project has candidate and promoted eligible pair artifacts with metadata.
- Execution loads only the promoted artifact on boot.
- Existing positions use natural exit.
- Telegram `/pairs` shows promoted pairs, latest z-score, entry gap, and latest
  action from persisted `tick_signals`.
- There is no first-class pair validity policy.
- There is no quantified drift comparison between the research window and
  recent post-promotion data.
- There is no configured data refresh cadence for pair validity.
- There is no scheduled candidate regeneration.
- There is no entry gating based on pair validity.

### Core Concepts For The New Feature

Treat promoted pairs as perishable execution inputs. Their useful life is not a
single wall-clock duration. It should be measured across three independent
surfaces:

1. Artifact/data recency:
   - research input window start/end
   - candidate generated time
   - promoted time
   - latest local market-data timestamp available for diagnostics
   - wall-clock age since research window end
   - bars elapsed since research window end
   - bars elapsed since promotion
2. Statistical relationship drift:
   - hedge ratio now vs research hedge ratio
   - spread mean now vs research spread mean
   - spread standard deviation now vs research spread standard deviation
   - correlation now vs research correlation
   - cointegration p-value now vs research p-value
   - half-life now vs research half-life
   - z-score distribution shift, such as mean, standard deviation, and tail
     frequency over a recent window
3. Execution behavior drift:
   - observed entry count vs research expected entry frequency
   - observed natural-exit count and time-to-exit vs research half-life
   - open position holding time as a multiple of the pair's research half-life
   - realized state-only/live PnL vs stress-report expectation where comparable
   - friction drag and slippage/funding assumptions vs realized execution data
     when those fields become available

Keep these outputs separate:

- Entry eligibility for new positions.
- Open-position monitoring for existing positions.

Do not let pair decay, artifact age, or pair-set changes force-close existing
positions implicitly. Existing positions continue natural exit unless an
explicit operator command, auditor action, tested risk kill switch, or manual
emergency process says otherwise.

### Data Refresh Cycle Discussion

Re-evaluating promoted pairs requires fresh market data. This means pair
validity is not just a report calculation; it becomes part of a repeatable
refresh cycle:

```text
promoted artifact
-> fetch/append recent market data
-> recompute pair validity diagnostics
-> optionally recompute candidate eligible-pair artifact
-> write audit/report output
-> operator reviews
-> operator promotes only when acceptable
-> execution loads promoted artifact on boot
```

Cadence must be explicit config or typed runtime policy, not hardcoded in the
research or execution modules. Candidate cadence models to discuss:

1. Fixed bars per timeframe:
   - Example: revalidate every `240` closed 1m candles or every `30` closed 4h
     candles.
   - Benefit: stable across wall-clock drift and easy to relate to signal data.
   - Risk: weak relationship to each pair's actual half-life.
2. Half-life multiple:
   - Example: revalidate after `3 * median_half_life_bars` across promoted
     pairs, or after each pair exceeds `N * pair_half_life_bars`.
   - Benefit: tied to strategy mechanics.
   - Risk: promoted pairs can have very different half-lives, making one global
     cadence awkward.
3. Wall-clock schedule per environment/timeframe:
   - Example: dev 1m every few hours; UAT/prod 4h daily or weekly.
   - Benefit: operator-friendly.
   - Risk: disconnected from market activity if used alone.
4. Hybrid policy:
   - Example: run no more often than every `X` minutes, no less often than every
     `Y` bars, and force review when any pair exceeds a half-life multiple.
   - Benefit: likely best for UAT/prod.
   - Risk: more config and more tests.

Recommended initial stance:

- Implement read-only diagnostics first.
- Store/display exact ages and drift values.
- Do not block entries until thresholds are reviewed in dev drills.
- Do not automate promotion.
- Do not hot-reload execution with a new artifact.

### Proposed Implementation Plan

Phase 0: Design and data contracts only

- Define a `PairValiditySnapshot` domain model.
- Define a `PairValidityConfig` typed config model.
- Decide which metrics are required in v1 and which are optional.
- Decide how to handle missing recent data, insufficient bars, and pairs with
  too few post-promotion observations.
- Add docs/tests for the policy language before behavior changes.

Potential v1 snapshot fields:

```text
pair_label
artifact_generated_at
artifact_promoted_at
research_window_start
research_window_end
latest_data_at
wall_clock_age_minutes_since_research_end
bars_since_research_end
bars_since_promotion
recent_window_bars
research_hedge_ratio
recent_hedge_ratio
hedge_ratio_drift_pct
research_correlation
recent_correlation
correlation_delta
research_p_value
recent_p_value
p_value_delta
research_half_life_bars
recent_half_life_bars
half_life_drift_pct
research_spread_mean
recent_spread_mean
spread_mean_shift_sigma
research_spread_std
recent_spread_std
spread_std_drift_pct
open_position_id
open_position_holding_bars
open_position_half_life_multiple
observed_entries
observed_signal_exits
observed_forced_exits
observed_avg_holding_bars
notes
```

Avoid a single opaque status in the data model. If a policy output is needed,
make it action-oriented and quantified:

```text
entry_allowed: true/false
entry_block_reasons: list[str]
operator_review_reasons: list[str]
open_position_review_reasons: list[str]
```

Phase 1: Persist or expose research baseline values

- Inspect current candidate/promoted artifact schema.
- Determine whether it already contains enough baseline fields for drift:
  - `Hedge_Ratio`
  - `Half_Life`
  - `P_Value`
  - `Best_Params`
  - `Performance`
- Add missing research-window metadata if needed:
  - source data start/end
  - bars used
  - baseline correlation
  - baseline spread mean/std
  - baseline z-score distribution stats
- Keep schema versioned.
- Promotion validation must reject malformed new fields once required.

Phase 2: Build read-only diagnostics module

Candidate module shape:

```text
src/engine/trader/runtime/pair_validity/
```

Responsibilities:

- Load promoted artifact.
- Read recent local market data from an explicit store/path adapter.
- Read persisted runtime state for observed entries/exits/holding bars.
- Compute pair-level drift metrics.
- Return typed snapshots.

Do not:

- mutate exchange state
- write new promoted artifacts
- force-close positions
- reach directly into hardcoded `data/` paths below config/adapter seams
- use raw YAML dictionaries

Phase 3: Add data refresh command or workflow helper

Pair validity needs fresh data. The refresh operation should be explicit and
auditable:

```text
fetch recent OHLCV for promoted pair assets
-> append/update local parquet
-> record refresh audit metadata
-> compute validity snapshots
```

Open design questions:

- Should the refresh operate on all symbols in the promoted artifact, the full
  research universe, or both?
- Should it fetch exactly the missing range since latest parquet timestamp, or
  refetch a rolling overlap window for correction safety?
- How much overlap is needed to guard against exchange candle revisions?
- Should dev 1m and UAT/prod 4h have different retention and refresh cadence?
- Should refresh be a CLI first, with Telegram only showing results?

Recommended v1:

- CLI-only refresh/diagnostic command.
- Explicit config path.
- Read-only market-data credentials only.
- Writes local data and diagnostic reports, not promoted artifacts.
- Telegram reads the latest diagnostic output only after CLI proves stable.

Phase 4: Surface diagnostics

Add operator visibility without behavior changes:

- Report CLI section: pair validity diagnostics.
- Telegram `/pairs`: add compact quantified fields for each promoted pair.
- Telegram `/run_status`: summarize:
  - promoted artifact generated/promoted timestamps
  - bars since research window end
  - count of pairs with operator review reasons
  - count of open positions above configured half-life multiple
- New Telegram detail view later:
  - `/pair_validity <PAIR>`
  - or menu: `Pairs -> Validity -> Pair Detail`

Telegram display should prioritize numbers:

```text
BCH/USDT|AVAX/USDT
Research ended: 2026-05-17 12:00 UTC
Age: 428 closed 1m bars / 7.1h
Hedge ratio drift: +4.8%
Correlation: 0.74 recent vs 0.81 research
P-value: 0.08 recent vs 0.03 research
Half-life: 92 bars recent vs 61 research (+50.8%)
Open position: #10, 87 bars, 0.95x research half-life
Entry allowed: yes
Review reasons: none
```

Phase 5: Entry gating after visibility is proven

Only after dev diagnostics are trusted:

- Add typed thresholds:
  - max bars since research end for new entries
  - max hedge-ratio drift percentage
  - max p-value
  - min recent correlation
  - max half-life drift or max half-life bars
  - max spread std drift
  - max open-position half-life multiple for review warnings
- Execution flow may block new entries if thresholds fail.
- Blocking must be visible in persisted `tick_signals` or equivalent runtime
  audit state.
- Open positions still natural-exit.

Phase 6: Scheduled candidate regeneration

Only after read-only diagnostics and optional entry gating are tested:

- Scheduler triggers research flow on configured cadence.
- Research writes a candidate artifact plus diagnostics.
- Promotion remains operator-controlled.
- Execution still loads promoted artifact on boot.
- Hot reload remains later and higher risk.

### Testing Requirements

Add behavior tests around the module interface:

- Time/bars age calculations for 1m and 4h artifacts.
- Drift calculations with deterministic synthetic data.
- Missing-data behavior.
- Insufficient recent bars behavior.
- Pair with open position beyond `N * half_life` produces review reason but no
  forced close.
- Pair failing entry thresholds blocks new entries only after the explicit entry
  gating phase.
- Refresh logic uses read-only market data and does not call order/exchange
  mutation paths.
- Unit tests must not call network.

### Documentation Updates Already Made

- `CONTEXT.md` now defines `pair validity` and `refresh cycle`.
- `docs/system-design.md` now includes a `Pair Validity And Refresh Cycle`
  section.
- `docs/current-roadmap.md` now moves the active roadmap toward quantified pair
  validity and refresh policy design before any scheduled automation.
- `docs/index.md` now points pair-validity/data-refresh work at `CONTEXT.md`,
  `docs/system-design.md`, and `docs/current-roadmap.md`.

This remains a workflow-safety and research-validity foundation slice, not a
profitability claim and not production approval.

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
  --surviving-pairs-path data/universes/1m/surviving_pairs.json \
  --market-data-base-dir data/parquet \
  --pair-validity-window-bars 240 \
  --pair-validity-min-bars 60 \
  --open-position-review-half-life-multiple 3
```

Generate parse-safe JSON:

```bash
.venv/bin/python -m src.engine.trader.report_generator \
  --db-path data/dev/trades_1m.db \
  --min-sharpe 0.5 \
  --surviving-pairs-path data/universes/1m/surviving_pairs.json \
  --market-data-base-dir data/parquet \
  --pair-validity-window-bars 240 \
  --pair-validity-min-bars 60 \
  --open-position-review-half-life-multiple 3 \
  --json
```

Refresh local parquet for promoted-pair diagnostics:

```bash
.venv/bin/python -m src.engine.trader.refresh_pair_data \
  --pipeline configs/pipelines/dev.yml \
  --overlap-bars 5 \
  --missing-lookback-bars 1500 \
  --fetch-limit 1000
```

Render current Telegram health in the terminal:

```bash
.venv/bin/python -c "from src.interfaces.telegram import context as c; from src.engine.trader.runtime.monitoring.health import build_trader_health_snapshot, render_trader_health_snapshot; c.configure_daemon('configs/telegram/dev.yml'); s=c.open_state_manager(); snap=build_trader_health_snapshot(s, environment=c.environment_label() or 'N/A', stale_after_minutes=c.health_stale_after_minutes()); print(render_trader_health_snapshot(snap)); s.close()"
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
- Do not implement scheduled pair refresh before quantified diagnostics,
  cadence policy, and operator review workflow are designed and tested.
- Do not implement hot reload.
- Do not implement automatic rebalancing.
- Do not implement automatic promotion.
- Do not block new entries from pair-validity diagnostics until the read-only
  diagnostic phase has been reviewed.
- Do not force-close positions because of pair-set changes.
- Do not push unless explicitly asked.
