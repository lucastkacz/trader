# Simulation Lab

`simulation/` is the offline scenario laboratory for the quant trading platform.
It exists to create controlled market, state, artifact, command, and execution
conditions that historical market data may not contain on demand.

The goal is not to predict real markets. The goal is to manufacture difficult,
auditable, deterministic edge cases and prove that the trading system remains
safe, boring, and explainable.

## Design Position

Simulation scenarios should be declarative and config-based. Humans and AI
agents should be able to open a YAML file, understand the exact edge case being
manufactured, adjust a parameter, and run the scenario.

The execution path must still be typed:

```text
scenario.yml
-> typed ScenarioConfig
-> simulation engine
-> generated OHLCV, artifacts, replay state, assertions, and reports
```

YAML describes what to simulate. Python implements how to simulate it.

## Purpose

The simulation lab should help answer questions such as:

- Does an existing position still receive natural-exit evaluation when a newer
  pair artifact removes that pair?
- Does the dynamic promoted-pair queue block future entries without forcing
  closes?
- Does pair-validity degradation produce explicit review or block reasons?
- Does state-only execution avoid exchange/client order ids under every replay?
- Does reporting survive stale, missing, malformed, or drifting data?
- Does reconciliation warn without mutating exchange state?
- Do command paths record explicit operator actions and close reasons?
- Do risk gates fail closed when sizing, liquidity, or exposure constraints are
  violated?

## Top-Level Ownership

`simulation/` is a top-level package because it is a cross-cutting verification
capability:

- It is not production runtime code.
- It is not pure research.
- It is not merely test fixtures.
- It may depend on `src/`.
- `src/` must never depend on `simulation/`.
- Tests may depend on both `src/` and `simulation/`.

Dependency direction:

```text
src/        -> never imports simulation
simulation/ -> may import src
tests/      -> may import src and simulation
```

## Safety Defaults

Every simulation feature must default to offline and non-mutating behavior.

Required defaults:

- State-only execution mode.
- Temporary state DB.
- Temporary market-data store.
- No network access.
- No live credentials.
- No exchange mutation.
- Deterministic seed.
- Explicit output directory.
- Explicit timeframe.
- Explicit exchange id.
- Explicit scenario clock.
- YAML parsed once at the scenario boundary.
- Typed config objects below the boundary.

Hard failures:

- A scenario attempts to instantiate a live exchange adapter.
- A scenario uses live credentials.
- A scenario writes outside its configured temporary output directory.
- A test scenario performs a network call.
- A state-only replay records exchange/client order ids.
- A pair recalculation scenario causes an automatic forced close.
- Raw YAML dictionaries leak into generators, replay, assertions, or runtime
  adapters.

## Outputs

Scenario outputs should be explicit, reproducible, and useful for both machines
and humans.

Machine-readable outputs:

- `scenario.json`: normalized typed scenario config, seed, git commit, and
  generated metadata.
- `market_data/`: generated parquet OHLCV, organized by exchange and timeframe.
- `artifacts/`: promoted/candidate pair artifacts and promotion audit records
  when applicable.
- `state/trades.db`: replay state database.
- `results.json`: assertion outcomes, position summaries, queue summaries, and
  diagnostic summaries.
- `events.jsonl`: tick-by-tick replay events.

Human-readable outputs:

- `report.md`: scenario summary, expected behavior, observed behavior, and
  failures.
- `plots/`: optional price, spread, z-score, queue rank, validity drift, and
  equity visualizations.

Example output layout:

```text
simulation/outputs/
  queue_blocks_future_entries/
    2026-05-22T150000Z_seed_42/
      scenario.json
      results.json
      events.jsonl
      report.md
      market_data/
        bybit/
          1m/
            AAA_USDT.parquet
            BBB_USDT.parquet
      artifacts/
        universes/
          1m/
            surviving_pairs.json
      state/
        trades.db
      plots/
        prices.html
        spread_zscore.html
        equity_curve.html

## Documentation Map

- `FEATURES.md`: complete feature catalog for future implementation.
- `ARCHITECTURE.md`: proposed package layout, dependency rules, and interfaces.
- `SCENARIO_DSL.md`: scenario definitions, phase composition, and expected
  outcomes.
- `MARKET_GENERATION.md`: stochastic processes, synthetic OHLCV, shocks, and
  data-quality faults.
- `REPLAY_AND_ASSERTIONS.md`: replay harness, invariant library, outputs, and
  CI integration.
- `ROADMAP.md`: implementation slices in a safe order.

## First Implementation Target

The first useful implementation should be deliberately small:

```text
synthetic cointegrated pair
-> deterministic OHLCV
-> injected market-data provider
-> execute_tick replay in state-only mode
-> assertions for queue blocking and natural exit
```

This first target should prove that a synthetic scenario can drive the existing
runtime through public module interfaces without monkeypatching private helpers.

## Non-Goals For The Initial Version

- No live exchange integration.
- No production order submission.
- No automatic promotion.
- No scheduled research.
- No hot reload.
- No capital increase.
- No large dashboard before deterministic replay works.
- No broad rewrite of runtime loop or state manager.

## Promotion Path

Start with the lab as test-supporting infrastructure. If the simulation API
becomes useful for local operator drills or research validation, selected pieces
can later be promoted into `src/simulation/` after they have stable interfaces,
tests, and clear operational boundaries.
