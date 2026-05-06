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
-> stress testing
-> eligible pair artifact
-> trader execution
-> state, reporting, and operator controls
```

## Research Flow

The research flow is offline or operator-run. It may read local data, fetch
historical data through the data layer, compute candidate pairs, run filters and
stress tests, and write eligible pair artifacts.

Research code must not mutate live exchange state.

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
data/universes/{timeframe}/surviving_pairs.json
```

The artifact is a JSON envelope with `metadata` and `pairs`. Metadata includes
schema version, artifact type, generation time, timeframe, exchange, and pair
count. Execution validates the envelope on boot and rejects missing, malformed,
mismatched, or legacy list-only artifacts. Freshness checks belong to artifact
versioning and promotion before scheduled refresh is introduced.

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
-> new artifact is written
-> operator restarts trader
-> trader loads artifact on boot
-> new entries use new pair set
-> existing positions close naturally
```

Scheduled refresh and hot reload are future work.

## Configuration

Config is split by concern:

```text
configs/pipelines/   runtime environment, exchange, DB paths, cadence, execution mode
configs/universe/    asset eligibility and filtering
configs/strategy/    signal thresholds and lookbacks
configs/backtest/    simulation grid and friction assumptions
configs/risk/        capital and exposure limits
configs/telegram/    Telegram environment metadata
```

Raw YAML dictionaries are parsed once near entrypoints. Runtime modules receive
typed config objects or explicit values.

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
