# Simulation Feature Catalog

This catalog describes the full target capability of the simulation lab. It is
intentionally broad so implementation can proceed later in small slices without
losing the bigger design.

## Scenario Definition

- Named scenarios with stable ids.
- Human-readable descriptions.
- Deterministic random seed.
- Timeframe and exchange id.
- Symbol universe.
- Bar count and start timestamp.
- Scenario phases with start/end bars.
- Expected outcomes.
- Safety invariants.
- Output directory.
- Optional tags such as `fast`, `replay`, `chaos`, `regression`, `slow`.

## Scenario Inputs

- Promoted pair artifacts.
- Candidate pair artifacts.
- Runtime state DB seed data.
- Synthetic OHLCV frames.
- Pair-validity diagnostics.
- Queue policy.
- Risk policy.
- Order execution config.
- Operator command schedule.
- Reconciliation exchange snapshots.
- Runtime clock.
- Market-data provider.
- Market-data stream provider.
- Virtual stream clock.

## Synthetic Price Processes

- Geometric Brownian motion for base assets.
- Arithmetic Brownian motion for special cases.
- Ornstein-Uhlenbeck spread process.
- Colored-noise OU spread process.
- Generalized Langevin spread process.
- Cointegrated pair process.
- Cointegrated pair process with a generalized Langevin spread.
- Jump diffusion.
- Fat-tail return generator.
- Volatility-regime switching.
- Correlation-regime switching.
- Hedge-ratio drift.
- Spread mean drift.
- Spread volatility drift.
- Deterministic scripted paths.
- Process calibration against explicit diagnostic bands.
- Optional accelerated kernels for profiled process bottlenecks.

## Market Path Manipulators

- One-leg flash crash.
- Both-leg flash crash.
- Gap up.
- Gap down.
- Slow bleed.
- Melt-up.
- Volatility explosion.
- Volatility compression.
- Spread shock.
- Spread stuck away from mean.
- Whipsaw near entry threshold.
- False entry.
- False exit.
- Correlation breakdown.
- Cointegration breakdown.
- Hedge-ratio drift.
- Recovery after breakdown.
- Cross-asset contagion.
- Weekend or maintenance gap.

## OHLCV Construction

- Close-first generation.
- Open from previous close.
- Configurable high/low wick width.
- Configurable volume model.
- Lognormal volume noise.
- Volume spikes.
- Zero-volume bars.
- Missing volume bars.
- Deterministic timestamp generation.
- UTC-only timestamps.
- Per-symbol OHLCV metadata.
- Exchange/timeframe path compatibility.

## Data Quality Faults

- Missing candles.
- Duplicate candles.
- Out-of-order candles.
- Stale symbol data.
- One-leg stale data.
- Both-leg stale data.
- NaN close values.
- NaN high/low values.
- Zero price.
- Negative price.
- Extreme outlier.
- Mismatched timestamp alignment.
- Partial symbol coverage.
- Truncated history.
- Market data older than artifact.
- Market data older than open position.

## Artifact Simulation

- Valid promoted artifacts.
- Valid candidate artifacts.
- Malformed artifact envelopes.
- Missing metadata.
- Wrong artifact type.
- Wrong timeframe.
- Wrong exchange.
- Stale generation timestamp.
- Missing pair rows.
- Empty pair set.
- Duplicate pairs.
- Missing baseline fields.
- Incomplete research window.
- Bad hedge ratio.
- Bad best params.
- Pair removed after position opened.
- Pair added after refresh.
- Promotion audit event generation.

## Pair Validity Controls

- Artifact generation age.
- Promotion age.
- Research-window age.
- Bars since generation.
- Bars since promotion.
- Bars since research end.
- Recent correlation drift.
- Recent cointegration p-value drift.
- Hedge-ratio drift.
- Half-life drift.
- Spread mean shift.
- Spread standard-deviation drift.
- Insufficient recent bars.
- Missing recent market data.
- Open position holding-time multiple.
- Operator review reason injection.
- Open position review reason injection.
- Unavailable diagnostics with audit notes.

## Dynamic Pair Queue Controls

- Entry-eligible pair.
- Blocked pair.
- Missing validity snapshot.
- Operator-review block.
- Missing entry opportunity.
- No-entry-signal block.
- Capital slots full.
- Max positions per pair reached.
- Max positions per asset reached.
- Research score dominance.
- Validity score dominance.
- Opportunity score dominance.
- Tie-breaking by research rank and pair label.
- Queue reranking after a synthetic shock.
- Queue blocks future entries only.
- Existing positions continue natural-exit evaluation.

## Runtime Replay

- Replay `execute_tick` over synthetic market data.
- Inject market-data provider without private monkeypatching.
- Run fixed tick count.
- Run until expected event.
- Run until max ticks.
- Start with empty state.
- Start with seeded open positions.
- Restart from persisted state DB.
- Pause/resume command injection.
- Stop/stop_all command injection.
- Heartbeat override.
- Boundary-sync override.
- Deterministic runtime clock.

## Stream Simulation

- Virtual-time websocket-like market-data streams.
- Candle open/update/close events.
- Ticker update events.
- Trade print events.
- Order book snapshot events.
- Order book delta events.
- Heartbeat events.
- Subscription acknowledgement events.
- Disconnect and reconnect events.
- Stream error events.
- Event sequence numbers.
- Exchange timestamps and receive timestamps.
- Configurable latency.
- Configurable jitter.
- Event drops.
- Event duplicates.
- Out-of-order events.
- Burst delivery after lag.
- One-leg feed lag.
- Partial symbol outage.
- Missing heartbeat.
- Delayed reconnect.
- Candle close emitted twice.
- Order book delta gap.
- Deterministic stream replay from generated market paths.
- Stream health assertions.

## Order Execution Simulation

- State-only target recording.
- Paper fills.
- Full fills.
- Partial fills.
- Delayed fills.
- Rejected orders.
- Cancel failures.
- Stale open orders.
- Slippage model.
- Fee model.
- Precision model.
- Min notional rejection.
- Liquidity rejection.
- Exchange client order ids only when explicit.

## Reconciliation Simulation

- Exchange snapshot matches local state.
- Missing exchange position.
- Unexpected exchange position.
- Quantity mismatch.
- Side mismatch.
- Symbol mismatch.
- Missing fills.
- Partial fills.
- Stale local leg target.
- Duplicate exchange position.
- Exchange API failure.
- Empty exchange snapshot with local open position.
- Read-only audit never mutates exchange.
- Boot reconciliation warns without auto-close.

## Command Injection

- `/pause`.
- `/resume`.
- `/stop`.
- `/stop_all`.
- Unknown command.
- Command during sleep window.
- Command while paused.
- Command failure recording.
- Forced local close audit.
- Explicit close reason checks.

## Risk Controls

- Max open positions.
- Max positions per pair.
- Max positions per asset.
- Max notional.
- Max leverage.
- Max portfolio exposure.
- Liquidity checks.
- Precision checks.
- Price bound checks.
- Kill-switch trigger.
- Kill-switch during open position.
- Kill-switch blocks entries.
- Emergency close behavior.
- Risk rejection reason audit trail.

## Expected Outcome Assertions

- Position opens by tick N.
- Position does not open.
- Position closes by natural exit.
- Position remains open after max ticks.
- Position is never force-closed by artifact change.
- Queue blocks future entry.
- Queue does not block natural exit.
- Pair-validity review reason exists.
- Pair-validity unavailable note exists.
- Signal observations are recorded.
- Equity snapshots are recorded.
- Order lifecycle events are recorded.
- No exchange order ids in state-only.
- Every close has an explicit reason.
- Every blocked entry has an explicit reason.
- Reporting does not mutate state.
- Reconciliation does not mutate exchange.

## Result Artifacts

- Scenario metadata JSON.
- Tick-by-tick event log.
- Final state snapshot.
- Position lifecycle summary.
- Queue decision timeline.
- Pair-validity timeline.
- Signal timeline.
- Equity curve.
- Order event timeline.
- Reconciliation timeline.
- Assertion summary.
- Failing seed report.
- Optional markdown report.

## Visualization

- Price chart.
- Spread chart.
- Z-score chart.
- Entry and exit markers.
- Queue rank timeline.
- Validity drift timeline.
- Equity curve.
- Holding-bars timeline.
- Command timeline.
- Reconciliation delta timeline.

## CI Profiles

- Fast deterministic scenario tests.
- Medium replay tests.
- Slow chaos tests.
- Fuzz tests with saved failing seed.
- Local-only visualization runs.
- Regression scenario catalog.
