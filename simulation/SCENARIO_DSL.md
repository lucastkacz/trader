# Scenario Definition Model

The scenario definition layer should make difficult market and runtime
conditions explicit, repeatable, and easy to review. The primary authoring
format should be YAML, parsed into typed Python models before any generator,
replay harness, or assertion code sees it.

## Design Goals

- Human-readable.
- AI-agent-readable.
- Deterministic.
- Typed after parsing.
- Declarative, not executable.
- Composable.
- Easy to diff in code review.
- Small enough for unit tests.
- Rich enough for local stress drills.
- Explicit about safety expectations.

## Representation

Use YAML as the scenario authoring layer and typed schema objects as the runtime
interface.

```text
simulation/configs/scenarios/example.yml
-> ScenarioConfig
-> simulation engine
```

YAML answers "what edge case should exist?" Python answers "how is that edge
case generated and replayed?"

No lower simulation layer should receive raw YAML dictionaries.

## AI-Friendly Authoring Rules

Scenario YAML should be easy for an AI agent to understand and modify safely.

Rules:

- Use long, descriptive field names.
- Require `description` on every scenario.
- Prefer explicit values over inferred defaults.
- Include `why` on expectations.
- Use named phases.
- Use stable scenario ids.
- Avoid formula strings.
- Avoid ambiguous directions such as `up` or `down` when a domain-specific name
  is clearer.
- Validate with descriptive field-path errors.

Good expectation example:

```yaml
expectations:
  - type: natural_exit_occurs
    pair_label: AAA/USDT|BBB/USDT
    why: >
      Existing positions must continue normal signal evaluation even when
      pair validity blocks future entries.
```

## Example Scenario YAML

```yaml
scenario_id: queue_blocks_future_entries_existing_position_exits
description: >
  Simulates a promoted pair that opens a state-only position, later becomes
  invalid for future entries, and then naturally exits when the spread reverts.

seed: 42
timeframe: 1m
exchange: bybit
start_at: "2026-01-01T00:00:00+00:00"
bars: 500

outputs:
  write_market_data_parquet: true
  write_state_db: true
  write_events_jsonl: true
  write_results_json: true
  write_report_markdown: true
  write_plots: true

market:
  symbols:
    - AAA/USDT
    - BBB/USDT
  base_process:
    type: geometric_brownian_motion
    initial_price: 100.0
    drift: 0.0
    sigma: 0.015
  pair_process:
    type: cointegrated_ou
    asset_x: AAA/USDT
    asset_y: BBB/USDT
    alpha: 0.1
    beta: 0.82
    spread_mean: 0.0
    spread_theta: 0.12
    spread_sigma: 0.02

stream:
  enabled: false
  delivery_mode: virtual_time
  channels:
    - candles
    - heartbeat

pair_artifacts:
  promoted:
    artifact_type: surviving_pairs
    include_research_baseline: true
    pairs:
      - asset_x: AAA/USDT
        asset_y: BBB/USDT
        hedge_ratio: 0.82
        entry_z: 2.0
        exit_z: 0.2
        lookback_bars: 60

phases:
  - type: cointegrated_regime
    name: stable_research_like_behavior
    start_bar: 0
    end_bar: 150
    spread_theta: 0.12
    spread_sigma: 0.015

  - type: spread_shock
    name: force_entry_signal
    start_bar: 151
    end_bar: 155
    magnitude_sigma: 3.0
    direction: long_spread_entry

  - type: slow_reversion
    name: position_stays_open
    start_bar: 156
    end_bar: 300
    spread_theta: 0.01

  - type: validity_degradation
    name: future_entries_become_blocked
    start_bar: 220
    end_bar: 300
    recent_correlation: 0.35
    recent_p_value: 0.25

  - type: recovery
    name: natural_exit_window
    start_bar: 301
    end_bar: 420
    spread_theta: 0.18

expectations:
  - type: position_opens
    pair_label: AAA/USDT|BBB/USDT
    why: The synthetic spread shock should cross the entry threshold.

  - type: queue_blocks_future_entries
    pair_label: AAA/USDT|BBB/USDT
    why: Pair-validity degradation should block new entries.

  - type: natural_exit_occurs
    pair_label: AAA/USDT|BBB/USDT
    why: Queue blocking must not prevent existing positions from exiting.

  - type: no_exchange_order_ids
    why: State-only replay must never record real exchange identifiers.

  - type: no_forced_close
    why: Pair-validity degradation must not become hidden rebalancing.
```

## Process Types

Process definitions must be explicit and typed. A scenario selects a named
process family and supplies only the fields accepted by that family.

Initial process types:

- `geometric_brownian_motion`
- `ornstein_uhlenbeck_spread`
- `cointegrated_ou`
- `scripted_spread_path`

Future process types:

- `colored_noise_ou`
- `arma_residual_spread`
- `generalized_langevin_spread`
- `cointegrated_generalized_langevin`

Rules:

- Process types are schema-dispatched, not dynamically imported from YAML.
- Each process type has a typed config object.
- Unknown process fields are rejected.
- Calibration targets may request diagnostic bands, but generation must report
  the measured diagnostics, seed, and accepted parameters.
- Expensive process types may declare a preferred acceleration backend, but the
  scenario result must not depend on hidden global performance settings.

## Scenario Metadata

Each scenario should declare:

- `scenario_id`
- `description`
- `seed`
- `timeframe`
- `exchange`
- `start_at`
- `bars`
- `tags`
- `outputs`
- `stream`

Tags should support:

- `fast`
- `replay`
- `chaos`
- `pair_validity`
- `pair_queue`
- `reconciliation`
- `risk`
- `commands`
- `stream`
- `slow`

## Output Configuration

Output settings should be explicit:

- `write_market_data_parquet`
- `write_state_db`
- `write_events_jsonl`
- `write_results_json`
- `write_report_markdown`
- `write_plots`
- `output_dir`

Tests should usually set `output_dir` to a temporary path. Local operator drills
may write under `simulation/outputs`.

## Stream Configuration

Stream configuration describes websocket-like delivery under virtual time. It
must not describe live websocket URLs or credentials.

Fields:

- `enabled`
- `delivery_mode`
- `channels`
- `candle_updates_per_bar`
- `base_latency_ms`
- `jitter_ms`
- `heartbeat_interval_seconds`
- `timeout_seconds`
- `faults`

Supported delivery modes:

- `virtual_time`
- `as_fast_as_possible`

Supported initial channels:

- `candles`
- `ticker`
- `trades`
- `order_book`
- `heartbeat`

Initial stream fault types:

- `delayed_events`
- `dropped_events`
- `duplicated_events`
- `out_of_order_events`
- `one_leg_feed_lag`
- `partial_symbol_outage`
- `disconnect_reconnect`
- `missing_heartbeat`
- `duplicate_candle_close`
- `order_book_delta_gap`

Rules:

- Unit scenarios must use virtual time.
- Unknown channels are rejected.
- Unknown fault types are rejected.
- Stream faults must reference declared symbols.
- Live websocket URLs are rejected.
- Live credentials are rejected.

## Phase Types

### CointegratedRegime

Defines normal pair behavior.

Fields:

- `name`
- `start_bar`
- `end_bar`
- `beta`
- `alpha`
- `spread_mean`
- `spread_theta`
- `spread_sigma`
- `base_sigma`

### SpreadShock

Moves the spread away from mean.

Fields:

- `name`
- `start_bar`
- `end_bar`
- `magnitude_sigma`
- `direction`

Directions:

- `long_spread_entry`
- `short_spread_entry`
- `toward_mean`
- `away_from_mean`

### SlowReversion

Reduces mean-reversion speed after entry.

Fields:

- `name`
- `start_bar`
- `end_bar`
- `spread_theta`

### Recovery

Restores stronger mean reversion.

Fields:

- `name`
- `start_bar`
- `end_bar`
- `spread_theta`

### ValidityDegradation

Forces validity diagnostics to degrade.

Fields:

- `name`
- `start_bar`
- `end_bar`
- `recent_correlation`
- `recent_p_value`
- `hedge_ratio_drift_pct`
- `half_life_drift_pct`

### HedgeRatioDrift

Changes hedge ratio over time.

Fields:

- `name`
- `start_bar`
- `end_bar`
- `beta_from`
- `beta_to`

### CorrelationBreakdown

Decouples one asset from the other.

Fields:

- `name`
- `start_bar`
- `end_bar`
- `replacement_process`

### VolatilityRegime

Changes volatility for one or both legs.

Fields:

- `name`
- `start_bar`
- `end_bar`
- `target_symbols`
- `sigma_multiplier`

### FlashCrash

Applies a large one-time drop with optional recovery.

Fields:

- `name`
- `start_bar`
- `end_bar`
- `symbol`
- `drop_pct`
- `recovery_bars`

### MissingData

Deletes bars.

Fields:

- `name`
- `start_bar`
- `end_bar`
- `symbols`
- `pattern`

Patterns:

- `continuous`
- `every_n`
- `random_with_seed`

### StaleData

Stops updating a symbol after a bar.

Fields:

- `name`
- `start_bar`
- `symbols`

## Artifact Definitions

Scenarios should be able to create:

- Promoted artifact.
- Candidate artifact.
- Malformed artifact.
- Artifact update that removes a pair.
- Artifact update that adds a pair.
- Artifact with stale generation timestamp.
- Artifact with incomplete baseline fields.

## State Seeds

Initial runtime state may include:

- Open position.
- Closed position.
- Equity snapshots.
- Tick signals.
- Leg targets.
- Order events.
- User commands.
- Reconciliation runs.
- Reconciliation deltas.

All seeded state must use state manager interfaces when possible.

## Command Schedule

Commands can be scheduled by bar:

- `/pause`
- `/resume`
- `/stop`
- `/stop_all`
- Unknown commands.

Each command should define:

- `bar`
- `command`
- `target_pair`
- `expected_status`

## Expectations

Expectations should be explicit and composable.

Examples:

- Position opens by bar N.
- Position does not open.
- Position closes by natural exit.
- Position remains open at max ticks.
- Queue blocks future entry.
- Queue does not block natural exit.
- Pair validity report contains review reason.
- No exchange order ids are recorded.
- Reporting completes successfully.
- Reconciliation status is not auto-resolved by mutation.

## Validation

Scenario validation should reject:

- Missing `scenario_id`.
- Missing `seed`.
- Missing `timeframe`.
- Missing `exchange`.
- Missing `start_at`.
- Missing `bars`.
- Unknown phase type.
- Unknown expectation type.
- Phase end before phase start.
- Symbols referenced by phases but not declared by market config.
- Live execution mode in unit scenario profiles.
- Output path outside configured simulation output root unless explicitly
  allowed by a local operator run.
