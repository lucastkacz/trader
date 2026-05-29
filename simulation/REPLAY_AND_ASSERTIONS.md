# Replay And Assertions

Replay turns a scenario into runtime behavior. Assertions prove that behavior
matches safety and strategy expectations.

## YAML To Replay Flow

Tests and local drills should be able to start from a scenario YAML file:

```python
scenario = load_scenario("simulation/configs/scenarios/one_leg_flash_crash.yml")
result = run_scenario(scenario)
assert_no_exchange_order_ids(result)
```

The loader parses YAML into typed config objects. Replay code receives typed
objects only.

## Replay Targets

Initial replay targets:

- `execute_tick` with synthetic market data.
- Pair queue snapshot generation.
- Pair validity report generation.
- Report generation.

Later replay targets:

- Runtime loop with controlled clock.
- Command processing during sleep.
- Boot reconciliation.
- Order execution adapter simulation.
- Virtual-time stream replay with a synthetic stream provider.

## Market Data Provider

The replay harness should provide a market-data provider interface.

Responsibilities:

- Return recent candles for a symbol.
- Respect `bars_needed`.
- Respect timeframe.
- Return deterministic slices by replay tick.
- Simulate missing/stale data when configured.
- Never call network.

The first runtime change should allow `execute_tick` to accept this provider as
an optional dependency. Production behavior remains unchanged when the provider
is not supplied.

## Replay State

Each replay should create or receive:

- Temporary DB path.
- `TradeStateManager`.
- Synthetic promoted artifact path.
- Synthetic market-data store.
- Strategy config.
- Order execution config.
- Pair queue policy.
- Pair validity config.

State must be closed after replay.

## Replay Modes

### Tick Replay

Run `execute_tick` N times with synthetic candles.

Use for:

- Entry/exit behavior.
- Queue blocks.
- Natural exit.
- State-only order lifecycle.
- Equity snapshots.

### Report Replay

Generate reporting outputs from synthetic state and artifacts.

Use for:

- Pair validity diagnostics.
- Queue decision visibility.
- State ledger visibility.
- Corrupted or missing data resilience.

### Reconciliation Replay

Run read-only reconciliation against synthetic exchange snapshots.

Use for:

- Missing exchange positions.
- Unexpected exchange positions.
- Quantity mismatch.
- Side mismatch.
- API failure.

### Command Replay

Inject commands at specific bars.

Use for:

- Pause/resume.
- Stop one pair.
- Stop all pairs.
- Unknown commands.
- Command failure audit.

### Stream Replay

Deliver generated market data as websocket-like events under virtual time.

Use for:

- One-leg feed lag.
- Duplicated candle events.
- Out-of-order events.
- Disconnect and reconnect behavior.
- Heartbeat timeout behavior.
- Stream health based entry blocking.

Detailed stream rules live in `STREAM_SIMULATION.md`.

## Invariant Library

The assertion library should include always-on safety invariants.

### Exchange Safety

- No live exchange mutation.
- No network calls in unit scenarios.
- No exchange/client order ids in state-only mode.
- Live credentials rejected.

### Pair Recalculation Safety

- Pair artifact changes never force-close existing positions.
- Removed pairs continue natural-exit evaluation if position is open.
- Candidate artifacts never affect execution until promoted.

### Queue Safety

- Queue blocks future entries only.
- Queue never prevents natural exits.
- Blocked entries have explicit block reasons.
- Queue decisions are auditable.

### State Safety

- Every open has a state record.
- Every close has explicit close reason.
- Forced closes are only command/risk/auditor initiated.
- Equity snapshots are recorded when expected.
- Signal observations are recorded when expected.

### Reporting Safety

- Reporting does not mutate exchange.
- Reporting does not mutate runtime state except approved read metadata if any.
- Unavailable diagnostics are represented as audit notes.
- Report generation survives missing optional diagnostics.

### Stream Safety

- Stream unit tests do not open sockets.
- Stream unit tests do not sleep on wall-clock time.
- Live websocket URLs are rejected.
- Live credentials are rejected.
- Stale or degraded streams fail closed for new entries.
- Stream reconnects do not force-close existing positions.

### Reconciliation Safety

- Read-only audit does not place or cancel orders.
- Boot mismatch warns without hidden auto-close.
- Deltas are persisted for operator review.

## Outcome Assertions

Scenario-specific assertions should include:

- Position opens by tick N.
- Position does not open.
- Position closes by natural exit.
- Position remains open after max ticks.
- Position is closed by explicit forced command.
- Queue block reason exists.
- Pair-validity review reason exists.
- Report contains expected pair queue rank.
- Reconciliation run has expected status.
- No unexpected commands remain pending.

## Result Format

Each replay result should expose:

- Scenario id.
- Seed.
- Git commit when available.
- Normalized typed scenario config.
- Passed/failed assertions.
- Tick count.
- Final open positions.
- Closed positions.
- Queue decision timeline.
- Pair validity timeline.
- Signal timeline.
- Equity curve.
- State DB path.
- Artifact paths.
- Market-data parquet paths.
- Stream event log paths.
- Events JSONL path.
- Results JSON path.
- Markdown report path.
- Plot paths.
- Failure messages.

Canonical run output:

```text
simulation/outputs/{scenario_id}/{run_id}/
  scenario.json
  results.json
  events.jsonl
  report.md
  market_data/
    {exchange}/
      {timeframe}/
        {symbol}.parquet
  artifacts/
    universes/
      {timeframe}/
        surviving_pairs.json
  state/
    trades.db
  plots/
```

Unit tests should usually use temporary directories instead of the canonical
output root.

## Failure Reports

Failures should be easy to reproduce:

- Include scenario id.
- Include seed.
- Include phase names.
- Include failing assertion.
- Include latest relevant state rows.
- Include suggested replay command.

## CI Integration

Profiles:

- `fast`: deterministic unit scenarios.
- `replay`: tick replay scenarios.
- `reporting`: report resilience scenarios.
- `reconciliation`: read-only reconciliation scenarios.
- `chaos`: randomized and slower local-only scenarios.

Fast scenarios should be part of normal CI after the initial harness is stable.
Chaos scenarios should be opt-in until runtime is fast enough and failures are
easy to debug.
