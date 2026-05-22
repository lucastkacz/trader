# Simulation Roadmap

This roadmap keeps implementation incremental. The lab should become powerful,
but it should not arrive as one risky rewrite.

## Phase 0: Documentation And Boundaries

Status: planned by these documents.

Deliverables:

- Top-level `simulation/` folder.
- Feature catalog.
- Architecture rules.
- YAML-first scenario definition model.
- Market generation design.
- Replay/assertion design.

Done when:

- The package ownership is clear.
- `src -> simulation` is forbidden.
- The first implementation slice is obvious.

## Phase 1: Minimal Synthetic OHLCV

Goal:

```text
generate deterministic OHLCV for one cointegrated pair
```

Deliverables:

- GBM base process.
- OU spread process.
- Cointegrated pair generator.
- Close-to-OHLCV builder.
- Parquet writer for generated OHLCV.
- Deterministic seed tests.

Tests:

- Same seed produces same frames.
- Different seeds produce different frames.
- Generated prices are positive by default.
- Timestamps are UTC and monotonic.
- OHLC constraints hold by default.

## Phase 2: Market Data Provider Seam

Goal:

```text
run execute_tick with synthetic market data without monkeypatching private helpers
```

Deliverables:

- `MarketDataProvider` interface or callable type.
- Production default provider using existing fetch path.
- Synthetic provider for replay.
- Focused `execute_tick` tests preserving current behavior.

Safety:

- Production behavior unchanged when provider is omitted.
- Unit scenarios do not call network.

## Phase 3: YAML Scenario Loader

Goal:

```text
load scenario YAML into typed ScenarioConfig objects
```

Deliverables:

- `simulation/configs/scenarios/` examples.
- Typed scenario schema.
- Typed phase schema.
- Typed expectation schema.
- Validation errors with field paths.
- Loader tests.

Rules:

- YAML remains declarative.
- Raw YAML dictionaries stop at the schema boundary.
- Lower layers receive typed config objects.

## Phase 4: First Replay Scenario

Goal:

```text
prove queue blocks future entries while an existing position exits naturally
```

Deliverables:

- YAML scenario file.
- Typed scenario config.
- Tick replay harness.
- Temporary state DB setup.
- Synthetic promoted artifact.
- Assertions:
  - position opens
  - queue blocks future entry
  - existing position exits by signal
  - no exchange order ids in state-only

Tests:

- One end-to-end deterministic replay test.

## Phase 5: Data Quality Faults

Goal:

```text
simulate missing, stale, malformed, and misaligned market data
```

Deliverables:

- Missing bars transform.
- Stale symbol transform.
- Duplicate bars transform.
- Outlier transform.
- NaN/zero/negative price transform for validation tests.

Tests:

- Pair validity reports missing/stale data.
- Runtime avoids unsafe entries when candles are unavailable.
- Reporting survives unavailable diagnostics.

## Phase 6: Scenario Catalog

Goal:

```text
create reusable named edge-case scenarios
```

Initial catalog:

- Happy path mean reversion.
- Slow natural exit.
- No natural exit before max ticks.
- Queue invalidation.
- Artifact removal with open position.
- Missing leg data.
- One-leg flash crash.
- Hedge-ratio drift.
- Correlation breakdown.
- Stale data after promotion.

Tests:

- Fast subset in normal test suite.
- Slow subset marked separately.

## Phase 7: Reconciliation And Command Simulation

Goal:

```text
simulate operator commands and exchange snapshot mismatches
```

Deliverables:

- Command schedule.
- Synthetic exchange snapshot provider.
- Reconciliation replay harness.
- Assertions for warning/no-mutation behavior.

Tests:

- `/pause` blocks tick work.
- `/resume` restores tick work.
- `/stop` creates explicit forced local close.
- Read-only reconciliation records deltas only.

## Phase 8: Order And Risk Simulation

Goal:

```text
stress order lifecycle and risk gates without live exchange mutation
```

Deliverables:

- Simulated order adapter.
- Partial fill model.
- Rejection model.
- Slippage model.
- Precision model.
- Liquidity model.
- Risk rejection assertions.

Tests:

- Rejected order is auditable.
- Partial fill reconciliation detects mismatch.
- Risk rejection blocks entry with reason.
- Kill switch blocks new entries.

## Phase 9: Outputs And Visualization

Goal:

```text
make scenario failures easy to inspect
```

Deliverables:

- JSON replay result.
- Events JSONL.
- Generated market-data parquet.
- Replay state DB.
- Markdown summary.
- Price/spread/z-score plots.
- Queue rank timeline.
- Pair validity drift timeline.
- Equity curve.

Tests:

- Output files are written only under configured output directory.
- Output generation is deterministic where expected.

## Recommended First PR

Implement Phase 1 only:

- `simulation/generators/processes.py`
- `simulation/generators/ohlcv.py`
- `tests/simulation/test_market_generation.py`

Keep it small. Do not touch runtime until the synthetic data primitives are
tested and stable.
