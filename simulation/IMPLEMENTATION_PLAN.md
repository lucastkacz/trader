# Simulation Implementation Plan

This document turns the simulation blueprint into execution priorities. It is
the decision layer between the broad feature catalog and the incremental
roadmap.

The goal is to build a professional simulation framework that improves the
trading system by testing real runtime behavior under controlled edge cases.

## Current Priority Note

Simulation implementation is intentionally deferred until the local trader
contract is stable enough to be worth simulating. Finish the local state-only
trader lifecycle first: cold research/promote/refresh/report/execution drills,
capital-slot policy, pre-trade risk gates, reconciliation behavior, and
operator kill-switch semantics.

The simulator should target durable public trader interfaces. Avoid building
synthetic replay around behavior that is still being redesigned in the local
execution flow.

## Product Standard

The simulation framework is successful only when it can:

- Generate deterministic market scenarios.
- Replay those scenarios through public trading-system interfaces.
- Assert business and safety outcomes automatically.
- Reproduce every failure from scenario id, seed, and output artifacts.
- Explain failures in a way that improves production code.

It is not successful if it only generates realistic-looking data.

## Priority Definitions

### Core

Core work is required for the framework to be useful.

Rules:

- It must support deterministic offline tests.
- It must exercise existing runtime behavior, not only simulator behavior.
- It must preserve live-trading safety boundaries.
- It must be small enough to review and debug.

### Later

Later work is valuable, but should wait until core replay exists.

Rules:

- It may improve realism.
- It may improve observability.
- It may support local operator drills.
- It must not delay the first end-to-end deterministic replay.

### Non-Core

Non-core work should not be implemented until the core framework has proven
itself through multiple regression scenarios.

Rules:

- It may be interesting or impressive.
- It may be useful for demos.
- It should not become a hidden dependency of the trading system.

## Core Scope

The first production-quality version should include only these capabilities:

- Deterministic random seed handling.
- GBM base price process.
- OU spread process.
- Cointegrated pair generator.
- Close-to-OHLCV builder.
- Generated OHLCV frame validation.
- Optional parquet output.
- Minimal typed scenario schema.
- Minimal typed phase schema.
- Minimal typed expectation schema.
- Synthetic promoted pair artifact generation.
- Temporary state DB setup.
- Synthetic market-data provider for `execute_tick`.
- Tick replay harness.
- Assertion result model.
- Machine-readable `results.json`.
- Human-readable failure summary.

The first end-to-end scenario should prove:

```text
synthetic pair opens
-> pair validity or queue blocks future entries
-> existing position remains eligible for natural exit
-> position exits by signal
-> state-only replay records no exchange order ids
```

## Later Scope

Implement after the first end-to-end replay is stable:

- Data-quality faults.
- Scenario catalog.
- Calibration against diagnostic bands.
- Pair-validity drift scenarios.
- More realistic volume model.
- Jump diffusion.
- Fat-tail returns.
- Stream event projection.
- Virtual stream clock.
- Synthetic stream provider.
- Stream faults.
- Command replay.
- Read-only reconciliation replay.
- Order and risk simulation.
- Visualization.

## Non-Core Until Proven Necessary

Defer these until core scenarios reveal a concrete need:

- Generalized Langevin spread generation.
- Numba acceleration.
- C or Rust kernels.
- Heavy dashboard.
- Browser-based scenario designer.
- Full order book microstructure engine.
- External backtesting engine integration.
- Live websocket integration.
- Real-time operator UI.
- Cloud execution.

GLE support should remain design-compatible through the `SpreadProcess`
interface, but OU should be the first implementation.

## Minimal Interfaces

These are interface intentions, not final code. Keep the first implementation
boring and typed.

### Process Interfaces

```text
BasePriceProcess.generate(seed, bars, dt) -> PricePath
SpreadProcess.generate(seed, bars, dt) -> SpreadPath
PairProcess.generate(seed, bars, dt) -> PairMarketPath
```

Initial implementations:

- `GeometricBrownianMotionProcess`
- `OrnsteinUhlenbeckSpreadProcess`
- `CointegratedPairProcess`

Future implementations:

- `GeneralizedLangevinSpreadProcess`
- `ScriptedSpreadProcess`
- `JumpDiffusionProcess`

### Market Data Interfaces

```text
OhlcvBuilder.build(path, timeframe, start_at) -> dict[symbol, DataFrame]
MarketDataProvider.recent_candles(symbol, timeframe, bars_needed, as_of) -> DataFrame
```

The provider is the first critical seam into runtime. It should allow
`execute_tick` tests to consume synthetic candles without monkeypatching private
fetch helpers.

### Scenario Interfaces

```text
load_scenario(path) -> ScenarioConfig
run_scenario(config) -> ScenarioResult
```

Raw YAML dictionaries stop at the loader. Generators, replay, assertions, and
runtime adapters receive typed objects only.

### Assertion Interfaces

```text
Assertion.evaluate(result_context) -> AssertionOutcome
```

Assertions should be explicit and named. They should report:

- Assertion type.
- Scenario id.
- Seed.
- Pair label when applicable.
- Expected outcome.
- Observed outcome.
- Relevant phase.
- Failure reason.

## First Regression Scenarios

The initial scenario catalog should be intentionally small:

1. `happy_path_mean_reversion`
2. `queue_blocks_future_entries_existing_position_exits`
3. `removed_pair_existing_position_exits`
4. `missing_leg_data_blocks_entry`
5. `slow_reversion_position_remains_open_at_max_ticks`

These should become permanent regression tests once stable.

## Quality Gates

Before adding stream simulation, GLE, order simulation, or visualization, the
framework should pass these gates:

- Phase 1 generation tests are green.
- The synthetic candle provider drives `execute_tick` without network access.
- One end-to-end scenario asserts runtime state through public interfaces.
- Failures include scenario id, seed, phase, and assertion details.
- Generated outputs stay under the configured output directory.
- No production module imports `simulation`.

## Content Track

The development can be documented as a structured content series without
changing engineering priorities.

Suggested sequence:

1. Why historical data is not enough for trading-system testing.
2. Designing a simulation lab around safety invariants.
3. Generating a cointegrated pair with GBM plus OU spread.
4. Turning synthetic prices into OHLCV.
5. Replaying synthetic candles through the real runtime.
6. Testing natural exit under queue invalidation.
7. Making failures reproducible with seeds and artifacts.
8. Adding data-quality faults.
9. Simulating websocket-like streams with virtual time.
10. Why GLE is a future extension, not the first implementation.

Content rules:

- Show real engineering tradeoffs.
- Avoid claiming production readiness.
- Emphasize deterministic tests, auditability, and safety boundaries.
- Prefer short demos from committed scenarios over speculative architecture.
- Keep social content downstream of working slices.

## Next Slice

Implement Phase 1 only:

```text
simulation/generators/processes.py
simulation/generators/ohlcv.py
tests/simulation/test_market_generation.py
```

Do not touch runtime until the deterministic market-generation primitives are
tested and stable.
