# Stream Simulation

Stream simulation extends the simulation lab from deterministic batch replay into
deterministic event replay. Its purpose is to test how the platform behaves when
market data arrives as a live-like stream, without opening sockets, using live
credentials, or depending on wall-clock timing.

The stream layer should be built on top of generated market paths. It should not
replace batch generation or parquet replay.

```text
scenario.yml
-> typed ScenarioConfig
-> generated market path
-> stream event projection
-> virtual clock
-> synthetic stream provider
-> runtime/replay target
-> assertions and reports
```

## Design Goals

- Offline.
- Deterministic.
- No network calls.
- No live credentials.
- No real websocket dependency in unit tests.
- Virtual-time controlled.
- Exchange-shape aware without becoming exchange-coupled.
- Able to simulate both healthy streams and pathological feeds.
- Able to replay the exact same stream after a failure.

## Batch Replay Versus Stream Replay

Batch replay answers:

```text
Given this generated candle history, what does the runtime do at each tick?
```

Stream replay answers:

```text
Given these live-like events, delays, gaps, reconnects, and partial updates,
does the runtime still make safe decisions?
```

Both modes should share the same scenario schema, generated market paths,
artifacts, seeded state, and assertion library. They differ in how market data
is delivered to the system under test.

## Core Concepts

### Stream Event

A stream event is a typed, replayable market-data or transport event.

Initial event types:

- Candle opened.
- Candle updated.
- Candle closed.
- Ticker update.
- Trade print.
- Order book snapshot.
- Order book delta.
- Heartbeat.
- Subscription acknowledgement.
- Disconnect.
- Reconnect.
- Stream error.

Every event should include:

- Scenario id.
- Seed.
- Exchange id.
- Symbol when applicable.
- Timeframe when applicable.
- Event sequence number.
- Exchange event timestamp.
- Simulated receive timestamp.
- Payload.
- Source phase name when applicable.

### Virtual Clock

Stream replay must use a virtual clock instead of real sleeps.

The virtual clock controls:

- Event delivery time.
- Runtime perceived time.
- Heartbeat cadence.
- Reconnect delays.
- Backoff schedules.
- Timeout checks.

Tests should be able to advance the clock manually or run until the next event,
next bar close, expected assertion, or max virtual time.

### Stream Projection

Stream projection converts generated market paths into event sequences.

Examples:

- OHLCV close series to candle open/update/close events.
- Close series plus intrabar noise to trade prints.
- Close series plus spread/liquidity parameters to ticker updates.
- Synthetic depth model to order book snapshots and deltas.

Projection should be deterministic for a given scenario id, seed, and process
config.

### Synthetic Stream Provider

The synthetic stream provider is the test adapter that exposes replayable events
through an interface similar to production streaming code.

It may be:

- An async iterator.
- A callback dispatcher.
- A pull-based event source for deterministic unit tests.

It must not:

- Open a websocket.
- Read live credentials.
- Call the network.
- Import production exchange clients unless they are pure type definitions.
- Hide nondeterministic sleeps.

## Stream Faults

The stream layer should support feed-level faults that batch OHLCV alone cannot
express.

Fault categories:

- Delayed events.
- Dropped events.
- Duplicated events.
- Out-of-order events.
- Burst delivery after lag.
- Stale heartbeat.
- Missing heartbeat.
- Disconnect.
- Reconnect.
- Resubscription acknowledgement delay.
- Partial symbol outage.
- One-leg feed lag.
- Candle update without final close.
- Candle close emitted twice.
- Order book delta gap.
- Sequence number reset.
- Exchange timestamp drift.
- Receive timestamp jitter.

Each configured fault should record:

- Affected symbols.
- Affected event types.
- Start and end event or bar.
- Phase name.
- Expected runtime behavior.

## Timing Model

Stream scenarios need two clocks:

- `exchange_time`: when the synthetic exchange says the event happened.
- `receive_time`: when the runtime receives the event.

The difference between them models latency, jitter, backlog, and clock skew.

Scenarios should be able to configure:

- Base latency.
- Latency distribution.
- Jitter.
- Burst size.
- Max backlog.
- Event reorder window.
- Heartbeat interval.
- Timeout threshold.
- Reconnect delay.

All timing config must be explicit and typed.

## Runtime Seams

Stream simulation should not force `src/` to depend on `simulation/`.

Allowed direction:

```text
simulation synthetic stream provider -> production stream interface
```

Forbidden direction:

```text
production runtime -> simulation provider
```

If production runtime later gains websocket support, the seam should look like:

```text
MarketDataStream
  subscribe(symbols, channels)
  events() -> async iterator of typed stream events
```

Production implementation:

```text
Exchange websocket adapter
```

Simulation implementation:

```text
Synthetic stream provider
```

The shared interface should live in production code only if production also uses
it. Otherwise keep the simulation provider inside `simulation/` until the seam is
needed by `src/`.

## Scenario DSL Shape

Stream simulation should extend scenario YAML with an explicit stream section.

Example:

```yaml
stream:
  enabled: true
  delivery_mode: virtual_time
  channels:
    - candles
    - ticker
    - heartbeat
  candle_updates_per_bar: 4
  base_latency_ms: 50
  jitter_ms: 20
  heartbeat_interval_seconds: 10
  timeout_seconds: 30
  faults:
    - type: one_leg_feed_lag
      name: asset_y_lags_during_entry_window
      symbols:
        - BBB/USDT
      start_bar: 151
      end_bar: 170
      latency_ms: 45000
      expected_behavior: no_unsafe_entry

    - type: disconnect_reconnect
      name: stream_reconnects_before_recovery
      start_bar: 220
      end_bar: 225
      reconnect_delay_seconds: 15
      expected_behavior: runtime_recovers_without_exchange_mutation
```

Rules:

- `stream.enabled` controls stream replay, not live networking.
- Unknown stream channels are rejected.
- Unknown stream fault types are rejected.
- Stream faults must be deterministic.
- Stream tests must use virtual time.
- Unit scenarios must reject live websocket URLs and live credentials.

## Assertions

Stream-specific assertions should include:

- No network calls.
- No live websocket connection.
- No live credentials loaded.
- Events delivered in deterministic replay order.
- Runtime detects stale feed.
- Runtime avoids unsafe entries when one leg is delayed.
- Runtime survives duplicate candle close events.
- Runtime survives reconnect without forced close.
- Runtime records data unavailability as an audit reason.
- Queue blocks future entries when stream health is degraded.
- Natural exits remain eligible when fresh data is available again.

## Outputs

Stream runs should extend the normal simulation outputs.

Additional machine-readable outputs:

- `stream/events.jsonl`: delivered stream events.
- `stream/source_events.jsonl`: original projected events before faults.
- `stream/faults.json`: applied stream faults.
- `stream/timing.json`: latency, jitter, and virtual-clock summary.

Additional human-readable outputs:

- Stream health section in `report.md`.
- Optional feed latency plot.
- Optional heartbeat timeline.
- Optional symbol freshness timeline.

## Implementation Order

Do not implement stream simulation before deterministic batch generation exists.

Recommended order:

1. Generate deterministic OHLCV and spread paths.
2. Add typed scenario schema.
3. Add tick replay with synthetic candle provider.
4. Add stream event projection from generated paths.
5. Add synthetic stream provider with virtual clock.
6. Add stream faults.
7. Add stream-specific assertions.

This keeps stream simulation anchored to the same deterministic data used by
batch replay and avoids building a second, incompatible simulation engine.
