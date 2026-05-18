# System Design

The platform is an exchange-agnostic statistical arbitrage system. One codebase
supports development, UAT, production, and backtesting through explicit config
and typed secrets.

## System Flow

```text
historical market data
-> universe filtering
-> returns matrix construction
-> clustering
-> cointegration discovery
-> pair stress filtering
-> eligible pair artifact
-> trader execution
-> state, reporting, and operator controls
```

## Research Flow

The research flow is offline or operator-run. It may read local data, fetch
historical data through the data layer, compute candidate pairs, run filters and
pair stress filters, and write eligible pair artifacts.

Research code must not mutate live exchange state.
Research modules are production workflow modules, not tests. They should expose
small interfaces and receive storage, paths, exchanges, clocks, and runtime
policy through config, explicit parameters, or adapters.

## Execution Flow

The execution flow loads typed config and validated artifacts, evaluates only
eligible pairs, manages runtime state, processes operator commands, reconciles
state, emits reports, and sends notifications.

Execution code may read market data. Live order mutation must be isolated behind
explicit execution modules and controlled by explicit execution mode.

The intended progression is:

```text
state-only execution
-> paper/UAT execution
-> very-small-capital canary
-> production capital only after readiness gates pass
```

No code path should silently jump from research or paper behavior into live order
mutation.

## Eligible Pair Artifact

The eligible pair artifact is the research-to-execution handoff:

```text
candidate default: data/universes/{timeframe}/candidate_surviving_pairs.json
promoted default:  data/universes/{timeframe}/surviving_pairs.json
```

Research writes candidate artifacts. Operator promotion validates schema,
metadata, generation freshness, timeframe, exchange, pair count, and pair
contents before atomically replacing the promoted artifact. Promotion records an
audit event with candidate metadata, content hash, promotion time, timeframe,
exchange, from/to paths, pipeline name, operator when supplied, and the active
pair-refresh policy. Execution loads only the promoted artifact on boot.

These paths describe the default local layout, not a domain-layer constant.
Artifact stores and paths should be supplied through typed config, explicit
parameters, or a local storage adapter so the execution and research flows can
survive alternate environments.

The artifact is a JSON envelope with `metadata` and `pairs`. Metadata includes
schema version, artifact type, generation time, timeframe, exchange, and pair
count. Execution validates the envelope on boot and rejects missing, malformed,
mismatched, or legacy list-only artifacts.

## Pair Recalculation Policy

Pair recalculation means producing a new eligible pair artifact for future
entries.

Pair recalculation is not rebalancing. A pair falling out of a new artifact must
not automatically close an existing open position. Existing positions use natural
exit unless an explicit operator command, auditor action, risk kill switch, or
manual emergency process says otherwise.

Initial supported mode is manual:

```text
operator runs research
-> candidate artifact is written
-> operator promotes the candidate artifact
-> operator restarts trader
-> trader loads promoted artifact on boot
-> new entries use new pair set
-> existing positions close naturally
```

Scheduled refresh and hot reload are future work.

## Pair Validity And Refresh Cycle

Promoted pairs are perishable execution inputs. Their useful life should be
expressed with quantified diagnostics, not vague labels. Artifact age by itself
is only a clock; pair validity asks whether recent data and observed execution
behavior still resemble the research assumptions that made the pair eligible.

The platform should treat these as separate concerns:

- **Artifact/data age**: wall-clock time and bars elapsed since the research
  input window ended, since the candidate artifact was generated, and since the
  artifact was promoted.
- **Statistical drift**: changes in hedge ratio, spread mean/std, correlation,
  cointegration p-value, half-life, and z-score distribution when measured on a
  recent rolling window versus the research window.
- **Execution behavior drift**: differences between observed state-only or live
  behavior and research expectations, including entry frequency, natural-exit
  timing, realized PnL, friction drag, and positions exceeding expected
  half-life multiples.

Refresh cycles may fetch or append market data and recompute diagnostics or a
new candidate artifact on an operator-chosen cadence. The cadence, data window,
exchange, timeframe, storage, and runtime policy must enter through typed
config, explicit parameters, or adapters.

The first safe implementation should be read-only diagnostics and operator
visibility. Later entry gating may block new entries for pairs whose quantified
diagnostics exceed configured limits. Existing positions must continue under
natural exit unless an explicit operator command, auditor action, or tested risk
kill switch says otherwise.

## Configuration

Config is split by concern:

```text
configs/pipelines/   runtime environment, exchange, DB/data/artifact paths, cadence, execution mode
configs/universe/    asset eligibility and filtering
configs/strategy/    signal thresholds and lookbacks
configs/backtest/    simulation grid and friction assumptions
configs/risk/        capital and exposure limits
configs/telegram/    Telegram environment metadata
```

Raw YAML dictionaries are parsed once near entrypoints. Runtime modules receive
typed config objects or explicit values.

Runtime and research modules should not reach for hardcoded local paths. Market
data stores, artifact locations, exchanges, timeframes, and clocks enter through
typed config or adapters at explicit operational seams.

## State And Reporting

Runtime state includes positions, order lifecycle events, leg targets, equity
snapshots, user commands, reconciliation results, and signal observations.

State writes must be auditable. Reporting should read state and artifacts to
produce summaries; reporting should not mutate exchange state.

Auditable state must make it possible to reconstruct what the system believed,
what it attempted, what the exchange accepted, and what the operator saw.

## Operator Controls

Telegram and CLI controls are operator interfaces. They may request actions such
as pause, resume, stop, or stop all. The command path should make state mutation
and exchange mutation explicit and testable.

Emergency actions must not be hidden inside unrelated workflows such as pair
recalculation.
