# System Design

This repository is building an exchange-agnostic statistical-arbitrage
platform. It has research, replay, state-only execution, reporting, and an
explicit live-order adapter, but it does not yet provide a credible paper broker
or a production-ready trading system.

## Status Language

- **CURRENT** describes behavior present in the code now.
- **TARGET** describes an invariant or product stage still being built.
- **KNOWN GAP** identifies a place where current behavior does not yet satisfy
  the target.

An environment name such as dev, UAT, or prod is a configuration profile. It is
not proof that the corresponding operational stage is safe or complete.

## System Flow

```text
CURRENT research
historical market data
-> universe filtering
-> returns matrix
-> clustering and cointegration discovery
-> pair stress filtering
-> candidate artifact
-> manual promotion
-> promoted artifact

CURRENT execution
promoted artifact
-> state_only trader
-> SQLite state, reports, and operator commands

TARGET progression
reproducible cold start
-> stateful paper execution with simulated fills and costs
-> demo/testnet recovery drills
-> small-capital canary
-> production only after every readiness gate passes
```

Research, pair recalculation, reporting, artifact inspection, and pair-validity
work must never mutate exchange orders or positions.

## Offline Simulation

**CURRENT:** `src/simulation/replay.py` provides deterministic signal replay. It
uses typed inputs, a replay clock, shared signal evaluation, transition
classification, and auditable observations.

This is not paper trading. It does not yet model a stateful order/fill lifecycle,
partial fills, rejection, fees, funding, slippage, or crash recovery.

**KNOWN GAP:** the candle provider includes rows whose timestamp is less than or
equal to the replay timestamp. Because stored timestamps may represent candle
open rather than candle close, this alone does not prove that every feature is
available without look-ahead. Candle-close semantics must become explicit and
tested.

**TARGET:** add an explicit clock/event-order seam and a narrow replay-state
interface, then reuse shared queue, sizing, risk, position, and natural-exit
policy. Do not build a second independent trader inside the simulator.

## Research Flow

**CURRENT:** the operator-run research flow may fetch readonly historical data,
persist local OHLCV, build returns, discover clusters and cointegrated pairs,
run stress filters, and write candidate artifacts.

Research modules receive operational values through typed config, explicit
parameters, or adapters. Storage layout, exchange, timeframe, credentials, and
clocks do not belong as hidden assumptions in domain calculations.

**KNOWN GAPS:** the cold-start chain is not yet reproducible. Symbol identity can
be lost across CCXT and Parquet, discovery can consume stale files outside the
selected universe, lifecycle refresh is incomplete, and artifact provenance
does not yet distinguish every required research stage. These gaps are the
active work in `docs/current-roadmap.md`.

## Execution Flow

**CURRENT:** execution loads typed pipeline, venue, market-profile, strategy,
and risk config. It validates and loads a promoted artifact on boot, opens
runtime state only after eligible pairs exist, performs readonly boot
reconciliation, processes operator commands, evaluates ticks, writes local
state, emits reports, and sends notifications.

Runtime OHLCV reads use typed timeout, attempt, and backoff policy. Candles for
a shared symbol may be reused within the same tick. These reads do not mutate
the exchange.

Two configuration modes exist:

- `state_only`: no order adapter is constructed. Signals and transitions mutate
  local SQLite state and record leg targets, but there are no simulated fills or
  exchange orders. PnL is theoretical and is not execution PnL.
- `live`: constructs an exchange order adapter only with explicit live mode and
  credential tier. The adapter exists, but the lifecycle around sizing, fills,
  recovery, reconciliation, and emergency controls is incomplete.

Dev, UAT, and prod pipeline profiles are currently configured as `state_only`.
No document in this repository approves switching them to `live`.

## Eligible Pair Artifacts

The artifact paths in the default local layout are:

```text
candidate: data/universes/{timeframe}/candidate_surviving_pairs.json
promoted:  data/universes/{timeframe}/surviving_pairs.json
```

These are operational defaults, not domain-layer constants. Alternate stores or
layouts should enter through typed config or a storage adapter.

**CURRENT:** research writes a JSON candidate envelope. Manual promotion
validates schema, metadata, freshness, timeframe, exchange, pair count, and pair
contents. Execution loads only the promoted artifact and rejects missing,
malformed, mismatched, or legacy list-only envelopes.

Promotion uses atomic filesystem replacement for the artifact itself. If an
audit path is configured, the audit record is appended after replacement.

**KNOWN GAP:** artifact replacement and audit append are not one recoverable
transaction. Candidate stages and the immutable research/execution contract do
not yet carry all required provenance and hashes.

**TARGET:** model and validate the transition:

```text
DISCOVERED -> STRESS_EVALUATED -> OPERATOR_PROMOTED
```

Promotion and its audit evidence must be recoverable as one logical operation.

## Pair Recalculation And Open Positions

Pair recalculation produces a new candidate for future entries. It is not
rebalancing and must never hide a forced close.

**CURRENT:** promotion is manual and execution reads the promoted artifact only
at boot; there is no hot reload. Queue decisions filter and rank future entries
for the pairs loaded by the process.

**KNOWN GAP:** on restart, the runner loads the current promoted pairs before it
opens SQLite state, and ticks iterate only those loaded pairs. If an open
position's pair was removed from the artifact, the runtime cannot currently
guarantee that the position remains evaluable for natural exit. It also does not
persist the complete entry-time statistical contract.

**TARGET:** future entries use the current promoted artifact, while every open
position retains its immutable entry contract and stays in the evaluation set
until it exits or an explicit, audited emergency action handles it.

## Pair Validity And Refresh

Promoted pairs are perishable inputs. Validity should be expressed with
measurements rather than a single label:

- artifact age and persisted-data freshness;
- drift in hedge ratio, spread distribution, correlation, cointegration, and
  half-life;
- observed holding time and state-only or fill-based execution behavior.

**CURRENT:** an explicit readonly command refreshes OHLCV for promoted symbols
and writes local Parquet. Reports can calculate pair-validity diagnostics. An
incomplete refresh is surfaced instead of silently presented as complete.

The command does not promote artifacts, hot-reload execution, place orders,
rebalance, or force-close positions.

**TARGET:** use the same quantified evidence for operator review and optional
future-entry gates. Existing positions remain governed by their entry contract;
validity failure alone does not authorize a forced close.

## Dynamic Promoted-Pair Queue

The promoted artifact defines the approved universe. The dynamic queue ranks
current opportunities for future entries using promoted pairs, validity
diagnostics, recent signal evidence, runtime state, and allocation policy.

**CURRENT:** reports expose decisions, scores, block reasons, ranks, and typed
validity-threshold evidence. Execution supports `report_only` and
`future_entries`; the latter can filter and rank new entries. A configured
`null` threshold means intentionally disabled, not an implicit default.

The queue does not place orders by itself and must not force-close positions.

**LIMIT OF THE CURRENT GUARANTEE:** pairs that remain loaded and are evaluated
during a non-paused tick receive their normal signal transition. This is not a
global natural-exit guarantee: pause skips the full tick, and artifact changes
across restart can omit an open pair.

## Runtime Package Shape

Exchange-facing code is grouped by external capability:

- `src/exchange/config/`: typed venue and market-profile configuration;
- `src/exchange/data/`: readonly market discovery and OHLCV adapters;
- `src/exchange/execution/`: order and account mutation adapters.

Internal data code remains separate:

- `src/data/ohlcv/`: candle contracts, validation, metadata, merge, retention;
- `src/data/storage/`: persisted local datasets such as Parquet;
- `src/data/sync/`: backfill and refresh orchestration over explicit seams.

Trader runtime code is grouped by trading concept:

- `runtime/artifacts/`: artifact contracts, validation, lifecycle, promotion;
- `runtime/monitoring/`: readonly health and run-status snapshots;
- `runtime/pair_validity/`: validity reports and refresh helpers;
- `runtime/pair_queue/`: ranking and entry-eligibility decisions;
- `runtime/`: tick policy and trader orchestration;
- `cli/`: operator entrypoints.

A module is canonical when it owns behavior and provides locality, not merely
because it re-exports another interface.

## Configuration

Config is split by concern:

```text
configs/pipelines/   runtime paths, cadence, execution mode and policies
configs/exchange/    venue and market-profile construction
configs/data/        market-data lifecycle and sync policy
configs/universe/    asset eligibility and filtering
configs/strategy/    signal thresholds and lookbacks
configs/backtest/    simulation grid and friction assumptions
configs/risk/        capital and exposure limits
configs/telegram/    Telegram environment metadata
```

Raw YAML is parsed at the config boundary. Runtime and research modules receive
typed objects or explicit values. A production-named config file is not evidence
that production readiness gates have passed.

## State, Reconciliation, And Reporting

**CURRENT:** SQLite state records local positions, leg targets and lifecycle
events, equity snapshots, commands, reconciliation results, and signal
observations. Reporting reads state and artifacts without mutating the exchange.

Boot reconciliation can obtain a bounded readonly account-position snapshot or
run with an explicit `none` provider. It records deltas such as local-only or
exchange-only positions, quantity/side/symbol mismatch, partial local fills,
stale local orders, and snapshot failure. Current reconciliation actions are
diagnostic `NO_ACTION` records; they do not repair state or block execution.

**KNOWN GAP:** current local state is not an authoritative fill ledger. It cannot
yet reconstruct every exchange-accepted fill, fee, funding charge, partial-leg
outcome, or ambiguous submission. That audit trail is required before live use.

## Operator Controls

**CURRENT:** CLI and Telegram can enqueue local commands. In `state_only`,
`/stop` and `/stop_all` change local runtime state only. The durable risk kill
switch blocks future entries and replacement entries; it does not cancel orders,
flatten exchange positions, or repair state.

Pause currently returns before the full tick, so it also stops mark-to-market
and exit evaluation. A malformed kill-switch payload and an incorrect DB target
are known safety gaps. Boot reconciliation reports discrepancies but does not
fail closed.

**TARGET:** pause blocks entries while preserving state maintenance and exits;
risk controls fail closed; every command identifies its local-state and exchange
effects; demo/live emergency actions are explicit, tested, idempotent, and
audited.

## Safety Boundary

Until the roadmap and `docs/engineering-rules.md` readiness gate are complete:

- keep pipeline execution in `state_only`;
- use readonly credentials only;
- treat local PnL as diagnostic, not strategy or execution evidence;
- treat cold-start, restart, natural-exit, and recovery behavior as incomplete;
- do not infer production readiness from green unit tests or existing adapters.
