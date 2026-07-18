# Research Migration Guide

> **TEMPORARY DOCUMENT — DELETE AFTER MIGRATION.**
>
> This file exists to reconstruct the Research module from a frozen reference
> implementation while correcting known conceptual and architectural problems.
> It is not a permanent product specification. When every completion gate in
> section 18 passes and all accepted decisions have been transferred to
> `docs/RESEARCH.md`, delete this document.

**Status:** M0 decisions and the offline acceptance story are frozen; no
Research production code has been written. The next slice is M1.

**Last reviewed:** 2026-07-18

## 1. Purpose

This guide is the implementation backbone for an engineer or LLM rebuilding
Research. Its current working package hypothesis is:

```text
src/stat_arb/
└── research/
    ├── api.py
    ├── config.py
    ├── models.py
    ├── universe/
    ├── discovery/
    ├── validation/
    ├── stress/
    ├── backtest/
    └── reporting/
```

This tree is provisional migration scaffolding, not a permanent file contract.
The migration creates only the packages and files justified by cohesive
implemented behavior. Names, groupings, and file boundaries may change when a
slice reveals a deeper and simpler interface. `docs/RESEARCH.md` defines
capabilities and invariants; it does not require this physical layout.

The frozen implementation is evidence: it contains useful quantitative ideas,
tests, failure modes, configuration choices, and operational assumptions. It is
not an API compatibility target. Reuse decisions only after they agree with the
canonical contract in [`RESEARCH.md`](RESEARCH.md).

This guide must help a future implementer answer:

1. Where does the existing behavior live?
2. What behavior is worth preserving?
3. What is mathematically inconsistent or unsafe?
4. Who should own each concept in the new package graph?
5. In what order can we build a small, runnable vertical?
6. What requires Lucas's explicit decision?

## 2. Sources and Resolution

### 2.1 Frozen source

The expected local reference worktree is:

```text
/Users/lucastkacz/Documents/quant-v1-reference
```

It corresponds to tag:

```text
legacy-v1-before-rewrite
```

Do not assume the path blindly. Before implementation, run:

```bash
git worktree list
git -C /Users/lucastkacz/Documents/quant-v1-reference status --short --branch
git -C /Users/lucastkacz/Documents/quant-v1-reference rev-parse HEAD
git rev-list -n 1 legacy-v1-before-rewrite
```

The worktree should be readonly reference material. Do not patch it, import it
from the new package, add it to `PYTHONPATH`, or make tests depend on its local
existence.

### 2.2 Authority order

When sources disagree, use this order:

1. Lucas's explicit instruction for the current task.
2. `.agents/AGENTS.md` for durable implementation and safety rules.
3. `docs/_IMPLEMENTATION_AGENT_GUIDE.md` for route order and completion state.
4. The relevant canonical module documents for accepted behavior and ownership.
5. `docs/current-roadmap.md` for current status and near-term scope.
6. This guide for migration traceability, open decisions, slices, and gates.
7. Frozen tests as clues about intended V1 behavior.
8. Frozen implementation and config as clues about actual V1 behavior.

Passing an old test is not proof that its underlying financial assumption is
correct.

## 3. Operating Rules for the Implementer

- Build one end-to-end offline vertical before broad package scaffolding.
- Never copy a file wholesale merely because its tests pass.
- For each migrated behavior, write down: source, accepted target rule, test, and
  destination owner.
- Introduce a model or interface only when a real invariant or side-effect seam
  justifies it.
- Prefer pure functions for math; prefer composition for I/O capabilities and
  orchestration.
- Pydantic/model inheritance used only for validation is not the inheritance
  problem to solve.
- Do not create compatibility imports from the frozen namespace.
- Do not reintroduce Prefect, CCXT, Telegram, SQLite, live probes, runtime state,
  or deployment into the first Research vertical.
- Do not silently answer an `OPEN` decision. Stop that implementation slice,
  record the question, and continue only where the answer is irrelevant.
- Update `docs/RESEARCH.md` conclusively when a migration decision is resolved;
  do not copy provisional labels or leave the code as its only record.
- Tests target public behavior and high-risk math, not old file layout.

## 4. Migration Action Labels

Every source surface below uses one of these actions:

| Label | Meaning |
|---|---|
| `KEEP-CONCEPT` | Preserve the idea after expressing it in the new contracts |
| `ADAPT` | Preserve useful behavior but change math, API, or representation |
| `SPLIT` | Separate responsibilities that are mixed in one source file |
| `MOVE-OWNER` | Concept remains, but another top-level module owns it |
| `REPLACE` | Implement a corrected baseline instead of preserving behavior |
| `DROP` | Do not migrate; obsolete, misleading, or unjustified |
| `DEFER` | Useful later, outside the first offline vertical |
| `OPEN` | Requires an explicit product/quantitative decision |

## 5. Existing End-to-End Behavior

The orchestration path is effectively:

```text
master research flow
  |
  +-- optional market-data mining/selection
  |     -> ticker and eligibility filters
  |     -> OHLCV download/storage
  |     -> historical quality/liquidity filters
  |
  +-- alpha discovery
  |     -> scan local Parquet directory
  |     -> build returns matrix
  |     -> Spearman graph
  |     -> Louvain clusters
  |     -> cointegration within clusters
  |     -> write candidate artifact
  |
  +-- vector stress
        -> load candidates and pair candles
        -> evaluate lookback/entry-z grid
        -> choose maximum net PnL combination
        -> write stress report/candidate artifact
```

This flow contains good stage names but weak contracts between them:

- data selection does not return an exact immutable manifest to discovery;
- discovery scans every Parquet file in a directory, allowing stale data back in;
- multiple stages write to the same candidate path with different evidence;
- the stress winner is selected on the same observations used to report it;
- orchestration couples research to concrete settings, storage, exchange, and
  workflow framework behavior.

The new flow keeps the conceptual pipeline but makes every boundary typed and
auditable.

## 6. File-by-File Inventory: Direct Research

All paths in inventory tables are relative to the frozen worktree.

| Source | What it does | Action | Target / notes |
|---|---|---|---|
| `src/research/__init__.py` | Exposes research helpers | `DROP` | New package exports only the intentional public API |
| `src/research/pair_baseline.py` | Pair-level baseline metrics and diagnostics | `SPLIT` | Move pure statistics to `discovery/` or `validation/`; return typed evidence |
| `src/research/pair_stress_data.py` | Loads/alines pair OHLCV from local Parquet | `MOVE-OWNER` | Dataset access belongs to `market_data`; Research receives canonical series |
| `src/research/pair_stress_filter.py` | Loads pairs, loops parameter grid, invokes simulator, ranks winner, writes artifacts | `SPLIT` + `REPLACE` | Orchestration in `stress/evaluation.py`; no concrete store/writer; no max-PnL-only winner |
| `src/research/pair_stress_report.py` | Formats stress summaries | `ADAPT` | Typed report model under `reporting/`; rendering has no decisions |
| `src/research/pair_stress_simulation.py` | Bridges spread signals, sizing, friction, simulation | `SPLIT` | Pure signal/portfolio/backtest pieces under `backtest/`; exact timing contract first |

### Direct-test inventory

| Source | Useful evidence | Migration rule |
|---|---|---|
| `tests/research/test_pair_baseline.py` | Expected baseline diagnostics and edge cases | Re-express only accepted math through public/pure APIs |
| `tests/research/test_pair_stress_filter.py` | Grid orchestration and candidate filtering cases | Replace implementation-shape tests with acceptance/stability behavior |
| `tests/research/test_pair_stress_report.py` | Human-readable report expectations | Keep a small renderer contract after report models exist |

Do not migrate test count. Migrate high-value invariants and failure examples.

## 7. File-by-File Inventory: Universe

| Source | What it does | Action | Target / notes |
|---|---|---|---|
| `src/universe/selection.py` | Orchestrates ticker filtering, downloads, quality/liquidity checks, persistence | `SPLIT` | Research eligibility policy in `universe/`; acquisition/storage in `market_data`/`exchange` |
| `src/universe/symbol_pool.py` | Builds eligible symbol pool | `ADAPT` | Use canonical `SymbolId`; no filename or raw exchange-symbol identity leakage |
| `src/universe/clusters.py` | Cluster models/persistence | `SPLIT` | Cluster result in Research; serialization through artifact adapter |
| `src/universe/discovery.py` | Reads Parquet directory, clusters and discovers candidates | `REPLACE` | Accept exact `ResearchDataset` + `UniverseManifest`; never scan an ambient directory |
| `src/universe/pairs.py` | Pair candidate structures/helpers | `MOVE-OWNER` | Cross-module `PairId`, orientation, pair set/artifact types belong to `pairs` |
| `src/universe/clustering/returns_matrix.py` | Builds clipped log-return matrix | `ADAPT` | Preserve log-return concept; make alignment/clipping explicit policy |
| `src/universe/clustering/graph_louvain.py` | Spearman graph and Louvain partition | `ADAPT` | Explicit seed, stable ordering, overlap and degeneracy evidence |
| `src/universe/filters/data_quality.py` | Rejects low-coverage/invalid stored histories | `KEEP-CONCEPT` | Split canonical dataset validity (`market_data`) from Research eligibility thresholds |
| `src/universe/filters/market_tickers.py` | Active/type/quote/volume ticker screen | `SPLIT` | Raw exchange normalization elsewhere; policy under Research universe |
| `src/universe/filters/mega_caps.py` | Excludes top-N dominant instruments | `ADAPT` | Configurable policy, disabled unless an explicit strategy thesis enables it |
| `src/universe/filters/ohlcv_liquidity.py` | Daily/intraday historical notional-liquidity checks | `ADAPT` | Retain robust liquidity evidence with clear units and coverage |

### Universe-test inventory

| Tests | Preserve | Replace/remove |
|---|---|---|
| `tests/universe/test_clustering.py` | Graph thresholds, stable membership, degenerate cases | Assertions coupled to nondeterministic partition ids |
| `tests/universe/test_data_quality.py` | Gap, coverage, stale/invalid history examples | Any local-path shape that bypasses canonical dataset validation |
| `tests/universe/test_discovery_pairs.py` | No duplicates, within-cluster search, rejection evidence | Ambient directory scanning |
| `tests/universe/test_market_ticker_filtering.py` | Eligibility and volume boundary cases | Raw exchange dictionaries inside Research tests |
| `tests/universe/test_mega_caps.py` | Deterministic ranking/exclusion if policy accepted | Policy itself until Lucas confirms it |
| `tests/universe/test_ohlcv_liquidity.py` | Notional units, daily/intraday constraints | Hidden timeframe assumptions |
| `tests/universe/test_selection.py` | Stage counts and rejection visibility | Download/storage orchestration in Research |
| `tests/universe/test_symbol_pool.py` | Stable canonical identity | Filename-derived symbols |
| `tests/universe/test_volume_filter_flow.py` | Multi-stage eligibility evidence | Concrete exchange/store coupling |
| `tests/universe/test_live_volume_filter_probe.py` | Nothing in default Research suite | `DEFER`; live probes belong to external adapter validation |

## 8. File-by-File Inventory: Quantitative Core

### 8.1 Spread math

`src/engine/analysis/spread_math.py` contains valuable invariants:

- raw prices must be finite and positive;
- prices are logged exactly once;
- spread is consistently built from two aligned log-price series;
- rolling z-score behavior is centralized.

Action: `ADAPT` into `research/discovery/spread.py`, with the cross-module fitted
spread specification represented by a typed model owned by `pairs`.

Required correction: include the intercept in the canonical spread. The frozen
spread uses

```text
log(X) - beta * log(Y)
```

while the regression estimates an intercept and half-life later uses a centered
residual. The target proposed contract is:

```text
log(X) - alpha - beta * log(Y)
```

Do not preserve a convenient formula if it breaks alignment with estimation.

`tests/engine/test_spread_math.py` and
`tests/engine/trader/signals/test_spread_math_alignment.py` are important
evidence. Rebuild the alignment guarantee without importing trader internals.

### 8.2 Cointegration

`src/engine/analysis/cointegration.py`:

- logs prices;
- fits OLS in both directions;
- applies ADF to both residual series;
- selects the smaller p-value;
- independently fits a canonical exponentially weighted WLS beta for `X ~ Y`;
- estimates half-life using a residual with intercept.

Action: `REPLACE`, while preserving useful invalid-input examples from
`tests/engine/test_cointegration.py`.

The current output can combine:

1. a p-value from `Y ~ X`;
2. a hedge ratio from `X ~ Y`;
3. an ADF residual produced with OLS;
4. a traded spread produced with EW-WLS;
5. an intercept used in half-life but absent from the spread contract.

Those pieces do not describe one fitted stochastic process. The new
implementation must create an orientation-specific fitted model and compute all
downstream evidence from its exact residual.

### 8.3 Statistical choices not to copy silently

- configured cointegration p-value threshold of `0.15`;
- implicit stats-library defaults for ADF regression/autolag/maxlag;
- choosing the best of two orientations without accounting for that search;
- no false-discovery adjustment across many pairs;
- no minimum effect/stability evidence beyond a p-value and half-life.

Each becomes an explicit question or a documented proposed baseline.

## 9. File-by-File Inventory: Simulation and Economic Evidence

| Source | What it does | Action | Target / correction |
|---|---|---|---|
| `src/simulation/vectorized_engine.py` | Vectorized positions/returns/cost simulation | `REPLACE` | Causal event semantics, prior executable weights, turnover costs, typed result |
| `src/simulation/friction_model.py` | Fees, slippage, funding approximations | `ADAPT` | Explicit execution type; funding by elapsed time/settlement; reject unused config |
| `src/simulation/replay.py` | Replays records for simulation | `DEFER` or `SPLIT` | Keep only if first vertical needs a real event seam; otherwise vectorized acceptance first |
| `src/risk/position_sizer.py` | Inverse-volatility leg sizing | `REPLACE` for Research | Preserve `(1, -beta)` exposure ratio; pair-level risk scaling is a later policy |

### Known causal/economic problems

1. Shifting a signal by one row does not by itself define when the candle closed,
   when the decision existed, or what price was executable.
2. Intrabar high/low may influence an action while the same bar contributes
   returns, which can create look-ahead.
3. Current-bar inverse-volatility weights can be applied to current-bar returns.
4. Weights vary over time without charging all resulting turnover.
5. Research simulation and running strategy can freeze/update weights
   differently.
6. Independent inverse-volatility leg weights no longer represent the tested
   cointegration spread `(1, -beta)`.
7. Annual funding is converted to hourly and then charged once per row, which is
   dimensionally wrong for timeframes other than one hour.
8. A maker-fee config exists without a guaranteed maker execution path.

`tests/simulation/test_simulation.py`, `tests/simulation/test_replay.py`, and
`tests/risk/test_position_sizer.py` contain useful numerical examples, but new
tests must begin from the accepted information/fill/portfolio contracts.

## 10. File-by-File Inventory: Artifacts and Downstream Alignment

### 10.1 Artifact surfaces

| Source | Existing concern | Action |
|---|---|---|
| `src/engine/trader/runtime/artifacts/contract.py` | JSON envelope validation, schema/type/timeframe/exchange/pair count | `ADAPT` and `MOVE-OWNER` to `pairs` domain + serialization adapter |
| `src/engine/trader/runtime/artifacts/rows.py` | Converts raw row dictionaries | `REPLACE` with typed pair evidence; no raw-dict domain boundary |
| `src/engine/trader/runtime/artifacts/loading.py` | Reads candidate/promoted files and validates freshness | `ADAPT`; loading belongs to artifact adapter, lifecycle rules to `pairs` |
| `src/engine/trader/runtime/artifacts/lifecycle.py` | Candidate/promoted paths and atomic promotion | `SPLIT`; Research writes candidate evidence only; promotion is outside Research |
| `src/engine/trader/runtime/artifacts/promotion_audit.py` | Appends promotion audit | `DEFER` to promotion/application workflow |
| `src/engine/trader/runtime/artifacts/__init__.py` | Broad convenience exports | `DROP`; expose narrow public contracts |

Useful concepts to preserve:

- schema validation at read and write;
- candidate/promoted separation;
- freshness/timeframe/venue validation;
- atomic pointer replacement;
- explicit manual promotion with audit.

Required improvements:

- immutable run-addressed history plus optional current pointer;
- stage-specific lifecycle rather than multiple producers overwriting one file;
- complete data/config/code/universe provenance;
- typed rows and stable rejection/diagnostic schemas;
- content hash and exact fitted spread contract;
- artifact persistence separated from promotion transaction semantics.

### 10.2 Downstream consumers

`src/engine/trader/signals/evaluator.py` and
`src/risk/position_sizer.py` show which facts a future trader expects: pair
orientation, hedge ratio, lookback, z thresholds, weights, and state transitions.
They are not migrated into Research. Use them to ensure the candidate contract is
sufficient without importing trading behavior backward.

The later trader must consume the exact fitted spread contract, not reconstruct
it differently. Recalculated candidates affect future entries only.

## 11. File-by-File Inventory: Market Data and Exchange Boundaries

These files are relevant because Research currently reaches into their concerns.
Their implementations belong to later module migrations.

| Source group | Useful contract clue | Research migration action |
|---|---|---|
| `src/data/ohlcv/frames.py`, `metadata.py`, `retention.py` | Candle frames, metadata, retention/open-candle concerns | Define only the canonical input required; `MOVE-OWNER` implementation to `market_data` |
| `src/data/storage/local_parquet.py` | Local OHLCV persistence | Replace concrete dependency with readonly dataset input; adapter later |
| `src/data/storage/local_funding.py` | Funding history storage | Define required funding series semantics; adapter later |
| `src/data/lifecycle/config.py` and package exports | Data freshness/coverage configuration | Split data validity from Research eligibility |
| `src/data/sync/backfill.py`, `refresh.py`, `helpers.py`, `models.py`, `config.py` | Backfill/tail refresh and synchronization contracts | `DEFER`; Research never triggers sync in offline vertical |
| `src/exchange/data/market_data.py`, `ccxt_adapter.py` | Readonly external data acquisition | `DEFER`; later adapter implements `market_data` boundary |

Related tests:

- `tests/exchange/data/test_exchange_market_data.py` may inform normalization;
- every `tests/exchange/data/test_live_*` probe stays out of default tests;
- no Research unit or acceptance test may call CCXT or require credentials.

The new offline fixture must already express closed-candle meaning, canonical
symbols, timeframe, temporal coverage, and provenance. Otherwise the first
vertical would postpone the hardest data invariants.

## 12. File-by-File Inventory: Orchestration and Configuration

### 12.1 Orchestration

`src/pipeline/master_flow.py` mixes workflow-framework decorators, settings,
concrete exchange access, storage, discovery, artifact writing, and stress.

Action: `REPLACE` with a plain application function in `research/api.py` for the
offline vertical. A future scheduler calls the public API from outside the
module. Do not make Research depend on Prefect concepts.

`tests/pipeline/test_master_flow_config.py` and
`tests/test_run_profile_command.py` are not migrated as structural tests. Reuse
only configuration-boundary cases that remain valid.

### 12.2 Existing configuration files

| Source | Decision clues | Action |
|---|---|---|
| `configs/universe/dev.yml` | ticker, mega-cap, quality, liquidity, graph, cointegration thresholds | Inventory values; do not accept defaults silently |
| `configs/backtest/stress_test.yml` | main stress grid, capital and friction assumptions | Replace with typed policies and temporal validation |
| `configs/backtest/stress_test_dev_1m.yml` | one-minute development variant | Use only if chosen first timeframe; units need audit |
| `configs/strategy/dev.yml`, `uat.yml`, `prod.yml` | spread/signal/risk/runtime values | Extract candidate-contract needs; trading config stays out |
| `configs/data/lifecycle/default.yml` | freshness/retention assumptions | Move to market-data ownership later |
| `configs/data/ohlcv_backfill/default.yml` | acquisition ranges/pagination | Defer to market-data/exchange migration |
| `configs/pipelines/dev.yml`, `uat.yml`, `prod.yml` | orchestration toggles | Drop environment-tier abstraction until runnable behavior exists |
| `configs/runs/dev_1m_research.yml` | composed run profile | Rebuild only after one direct public API is stable |

The first config can be constructed directly in a test/fixture. A YAML loader is
not required to validate the quantitative vertical.

## 13. Quantitative Behavior Audit

| Topic | Existing behavior | Assessment | Required target |
|---|---|---|---|
| Price transform | Positive raw prices, log once | Good invariant | Preserve and test |
| Pair search | Spearman graph, Louvain, within-cluster pairs | Useful baseline | Stable seed/order and exact manifest |
| Determinism | Stable-looking flow but Louvain seed absent | Incorrect claim | Explicit seed and tie-breaking |
| Regression orientation | Tests both directions, keeps best p-value | Search is reasonable | Keep complete fitted orientation; account for search |
| Hedge ratio | EW-WLS `X ~ Y` after OLS/ADF selection | Misaligned | One estimator/model per tested spread |
| Intercept | Used for half-life, omitted from spread | Inconsistent | Persist and apply alpha everywhere |
| Cointegration threshold | Nominal p-value up to 0.15 | Too permissive/uncontrolled | Explicit alpha plus FDR policy |
| Multiple tests | None | False-discovery risk | Record family/count and adjust |
| Half-life | AR(1)/OU-style delta regression | Useful diagnostic | Apply to exact canonical residual |
| Z-score | Central rolling calculation | Good direction | Pin ddof/min periods/causality |
| Temporal selection | Same history for discovery/grid/performance | Severe overfit | Formation/validation/final OOS |
| Grid winner | Maximum total net PnL; positive only | Fragile | Stability/min trades/OOS/stress gates |
| Signals | Side-aware entry/exit, shifted position | Partial | Explicit state and event/fill timing |
| Portfolio | Independent inverse-vol legs | Diverges from spread | Preserve `(1, -beta)` then normalize |
| Costs | Fee/slippage/funding approximations | Useful categories | Coherent units, turnover, execution type |
| Funding | Annual-to-hourly charged per row | Timeframe bug | Elapsed time or settlement events |
| Artifact stages | Candidate/promoted; manual promotion | Good safety concept | Typed multi-stage immutable evidence |
| Invalid data | Can collapse into ordinary downstream behavior | Unsafe ambiguity | Explicit unavailable/incomplete state |
| Historical universe | Current symbols likely used historically | Survivorship bias | Point-in-time provenance or visible warning |

## 14. Target Ownership Map

The new Research module should not absorb everything it needs.

| Target concept | Owner | Research usage |
|---|---|---|
| `SymbolId`, `Timeframe`, `Candle`, validated dataset | `market_data` | Readonly input |
| Local fixture/Parquet/database dataset adapter | `market_data` infrastructure | Injected at application edge |
| Exchange symbol/ticker/OHLCV normalization | `exchange` adapter | Not imported by Research |
| `PairId`, `PairOrientation`, fitted spread specification | `pairs` | Imported public values |
| Candidate lifecycle and `CandidatePairSet` | `pairs` | Research produces candidate stage |
| Statistical policies and stage results | `research` | Owned internally/public result |
| Cointegration, validation, stress, causal backtest | `research` | Pure or composed behaviors |
| JSON candidate serializer/store | infrastructure/application adapter | Called at Research API edge |
| Promotion decision/audit | application/pairs workflow | Outside Research |
| Signals, positions, fills, recovery | `trading` | Future consumer only |
| CLI/HTTP/Telegram/UI | `interfaces` | Calls public APIs |

### 14.1 Composition seams

Potential small interfaces, introduced only with their first two implementations
(usually production adapter plus test fake):

- readonly historical dataset reader;
- candidate artifact store;
- research report store;
- clock.

Do not create repositories or protocols for OLS, ADF, z-score, signal rules, or
metric functions. Those are values/functions and can be composed directly.

## 15. Implementation Slices

Each slice must remain small enough to review and teach. Do not advance because
files exist; advance when its exit gate passes. Every `Targets` entry below is a
working destination to evaluate during that slice, not permission to scaffold
all listed files in advance.

### M0 — Resolve decisions and executable acceptance story

**Sources:** canonical Research doc, old configs, spread/cointegration/simulation
audit.

**Work:**

- answer the blocking questions in section 17;
- write one concrete example of dataset boundaries and expected lifecycle;
- define the acceptance command and deterministic fixture shape;
- record any accepted answer in `docs/RESEARCH.md`.

**Exit gate:** no unresolved choice can change the meaning of the first spread,
temporal split, or simulated fill.

### M1 — Minimal cross-module value contracts

**Sources:** OHLCV metadata/frame clues, universe pairs, artifact rows/contract.

**Targets:** the smallest required `market_data` and `pairs` value types plus
`research/models.py` and `research/config.py`.

**Work:** model canonical closed candles/dataset identity, pair identity and
orientation, temporal plan, configs, statuses, and rejection evidence.

**Tests:** validation, equality/hash, temporal non-overlap, closed-candle
boundary, unknown config rejection.

**Exit gate:** a deterministic fixture and request can be represented without raw
dictionaries, filenames, exchange objects, paths, or wall-clock access.

### M2 — Canonical fitted spread

**Sources:** `spread_math.py`, `cointegration.py`, their tests, alignment test.

**Targets:** `research/discovery/spread.py` and minimal pair fitted-model type.

**Work:** aligned positive log prices, orientation-specific regression,
intercept-inclusive spread, rolling z-score contract.

**Tests:** known synthetic coefficients, reverse orientation, log-once,
non-positive values, alignment, z-score warm-up.

**Exit gate:** one fitted model produces the exact same spread everywhere it is
used.

### M3 — Cointegration and multiplicity

**Sources:** existing cointegration behavior/tests and universe search counts.

**Targets:** `discovery/cointegration.py`, `multiple_testing.py`.

**Work:** explicit Engle-Granger settings, exact residual ADF, half-life,
orientation policy, BH-FDR, typed invalid results.

**Tests:** synthetic stationary residual/non-cointegrated cases, invalid matrix,
orientation separation, FDR boundaries, deterministic result order.

**Exit gate:** no p-value can be paired with different coefficients/residuals;
every hypothesis family and search count is observable.

### M4 — Exact universe and deterministic discovery

**Sources:** universe filters, returns matrix, graph/Louvain, discovery.

**Targets:** `research/universe/`, discovery orchestration.

**Work:** exact manifest, eligibility/quality evidence, return matrix,
deterministic graph/clusters, within-cluster unordered search.

**Tests:** stale/unrelated data cannot enter, canonical symbols survive,
seed/order reproducibility, degenerate graph, stage counts/rejections.

**Exit gate:** fixture to discovery result is deterministic and contains no path
scan or network dependency.

### M5 — Temporal validation

**Sources:** none authoritative; correct the shared-sample selection design.

**Targets:** `research/validation/`.

**Work:** formation/validation/final OOS slicing, warm-up/embargo, frozen-model
evaluation, stability evidence.

**Tests:** boundary timestamps, no OOS-dependent selection, insufficient window,
coefficient/stationarity changes.

**Exit gate:** changing final OOS values cannot change selected parameters before
the final evaluation.

### M6 — Causal pair backtest

**Sources:** stress simulation, vectorized engine, friction model, signal
evaluator, position sizer.

**Targets:** `research/backtest/`.

**Work:** explicit state machine, next-event fills, beta-coherent holdings,
turnover, fees/slippage/funding, gross/net metrics.

**Tests:** hand-calculated tiny path, no same-bar earnings, entry/exit equality,
weight ratio, rebalancing cost, timeframe-independent funding units.

**Exit gate:** every reported return is derivable from prior executable holdings
and declared prices/costs.

### M7 — Stress and candidate acceptance

**Sources:** stress config/filter/report.

**Targets:** `research/stress/` and acceptance policy.

**Work:** predeclared neighboring scenarios, full response surface, stability
gate, minimum trades, rejection reasons, lifecycle transition.

**Tests:** isolated lucky maximum rejected, robust neighborhood accepted,
cost-stress failure, deterministic tie behavior.

**Exit gate:** stress cannot overwrite discovery evidence or select solely by
maximum PnL.

### M8 — Public API, artifact, and report

**Sources:** master flow, artifact package, pair stress report.

**Targets:** `research/api.py`, `reporting/`, pairs artifact adapter.

**Work:** compose stages, persist immutable typed result/candidate, render report,
inject clock/stores, atomic current pointer if needed.

**Tests:** complete offline integration, no-candidate, incomplete-data, artifact
round-trip/hash, renderer snapshot kept intentionally small.

**Exit gate:** one public call and one documented command complete the offline
flow without old namespace, network, credentials, or pre-existing artifacts.

### M9 — Consolidate and delete migration scaffolding

**Work:**

- run tests, lint, type and package checks;
- verify dependency direction and import side effects;
- delete unused scaffolds and tests that protect no risk;
- reconcile architecture, canonical module docs, roadmap, and index;
- transfer final decisions and operational commands to permanent docs;
- delete this file.

**Exit gate:** all section 18 gates pass.

## 16. Scope Exclusions During Migration

The Research migration does not include:

- live or streaming market-data integration;
- automatic scheduling or artifact promotion;
- trading runtime, portfolio recovery, or order routing;
- Telegram, HTTP, UI, authentication, or remote-operation interfaces;
- database or cloud-platform selection;
- automatic model retraining during trading;
- claims of real-capital readiness;
- FM-OLS, DOLS, Johansen, Kalman-filter hedge ratios, KPSS/PP batteries,
  GARCH, machine learning, or broad optimizer searches.

These exclusions keep the migration focused on one causal, reproducible
Research flow. They can be revisited through the relevant module documentation
after this migration is complete.

## 17. Resolved M0 Decisions

These decisions were accepted on 2026-07-18 and are transferred to
`RESEARCH.md`. Test-only fixture values are explicitly not product defaults.

| ID | Resolution |
|---|---|
| `RQ-001` | The first semantic profile is a configured linear USDT perpetual swap. Bybit is the initial intended venue, but venue choice remains in composition/config and quantitative code is exchange-agnostic. |
| `RQ-002` | The acceptance fixture uses `1m` for speed. Real timeframe profiles are independent and define timeframe-aware calendar durations/minimum observations. |
| `RQ-003` | Evaluate both orientations as separate hypotheses; retain both evidence sets; allow one per unordered pair. If both survive, rank by BH-adjusted p-value, ADF statistic, then canonical ordering. |
| `RQ-004` | The canonical spread is always `log(X) - alpha - beta*log(Y)` for the fitted model; intercept is required and no deterministic time trend is used initially. |
| `RQ-005` | First baseline: augmented Engle-Granger; OLS/intercept/no trend; residual ADF; Schwert max lag `floor(12*(n/100)^(1/4))`; AIC autolag; nominal 5%; record all lag/test/version evidence. |
| `RQ-006` | BH-FDR at 5% over the whole-run family, including every tested pair, orientation, and estimator. |
| `RQ-007` | Mega-cap exclusion remains configurable and is off unless an explicit strategy thesis enables it. |
| `RQ-008` | Quote, settlement, contract type, and eligibility are explicit market-profile configuration, never code constants. |
| `RQ-009` | Real window lengths have no defaults yet. The synthetic acceptance story alone uses 1,500 formation, 500 validation, and 500 final-OOS bars, with derived warm-up. |
| `RQ-010` | Point-in-time membership is preferred; until available, a current-universe run must report its survivorship/listing-bias warning. |
| `RQ-011` | Louvain remains a deterministic configurable search reducer with explicit seed/resolution, not evidence of cointegration. |
| `RQ-012` | Decide after candle close and simulate the fill at next candle open with explicit slippage. |
| `RQ-013` | Preserve raw holdings `(1, -beta)`, normalize gross notional, and volatility-scale the pair only. |
| `RQ-014` | Use real historical funding settlement events. Missing funding is not zero; required net evidence becomes unavailable or an explicitly labeled conservative scenario. |
| `RQ-015` | Gate structure is required, but real numeric thresholds have no defaults and are deferred to M7. Diagnostic runs cannot emit candidates; test configs may use artificial explicit gates. |
| `RQ-016` | Candidate history is immutable per run and content-addressed, with an optional current-candidate pointer; typed models remain independent of JSON. |
| `RQ-017` | Manual promotion is a separate later workflow. Research ends at immutable candidate evidence. |

### Frozen first acceptance story

The first vertical uses four synthetic canonical instruments, a gap-free closed
`1m` dataset, exact manifest, frozen cutoff, 1,500/500/500 chronological bars,
derived warm-up, seeded discovery, baseline OLS/ADF/FDR, both orientations,
rolling-z-score/Bollinger-style historical decisions, causal next-open fills,
synthetic funding settlements, and explicit artificial costs, stress scenarios,
and gates. It must return one typed synthetic candidate with non-promotable test
provenance and observable rejections without network, credentials, ambient
files, existing artifacts, or exchange mutation. Repeated semantic inputs must
have the same semantic output/hash.

No exact shell command is recorded yet because the acceptance test does not
exist. M8 publishes the tested command after the executable flow is present.

### Non-blocking, intentionally deferred

- Real formation/validation/OOS durations and candidate gate values per profile.
- Whether evidence justifies WLS/EW-WLS, robust/M-estimators, DOLS, FM-OLS,
  Phillips-Perron, KPSS, explicit Bollinger variants, or OU decision policies.
- Johansen/multivariate baskets, database-backed adapters, walk-forward policy,
  UI channels, and scheduling.
- Optional hard time-based exits. The baseline instead reports half-life and
  observed holding median/p90/max/unresolved positions.

These deferrals cannot silently fall back to test values or library defaults
and do not delay M1.

## 18. Migration Completion Gates

This migration is complete only when all are true:

### Product and quantitative behavior

- [ ] `docs/RESEARCH.md` contains every accepted quantitative decision.
- [ ] One canonical oriented fitted spread is used by every stage.
- [ ] Formation, validation, and final OOS are non-overlapping and causal.
- [ ] Multiple testing is explicit and tested.
- [ ] Simulation timing, holdings, costs, and funding use coherent units.
- [ ] Stress measures robustness rather than selecting maximum PnL alone.

### Architecture

- [ ] Public entry is through `stat_arb.research.api`.
- [ ] Research has no dependency on exchange mutation, trading runtime, CCXT,
  workflow framework, UI, Telegram, or credentials.
- [ ] Market data and pair concepts have their proper owners.
- [ ] Math is pure and side effects are at the application edge.
- [ ] No compatibility import or runtime dependency points to the frozen tree.
- [ ] No unjustified protocol/class/file fragmentation was introduced.

### Data, artifacts, and reporting

- [ ] The exact closed dataset and universe are immutable inputs with provenance.
- [ ] No ambient directory scan can add symbols to a run.
- [ ] Candidate stages cannot overwrite or masquerade as each other.
- [ ] Typed candidate evidence validates and round-trips through versioned JSON.
- [ ] Accepted and rejected outcomes have machine-readable reasons.
- [ ] Reports distinguish formation, validation, final OOS, and limitations.

### Verification

- [ ] A fresh offline acceptance run needs no network, secrets, or prior files.
- [ ] Repeated semantic inputs produce identical semantic outputs.
- [ ] Focused unit, integration, lint, type, and packaging checks pass.
- [ ] Tests protect risk and contracts instead of the old directory layout.
- [ ] The roadmap and documentation index reflect the implemented reality.

### Deletion rule

After the checklist passes:

1. Move any still-useful rationale, formulas, contracts, and tested commands to
   permanent module or operator documentation.
2. Confirm no permanent document links here.
3. Delete `docs/RESEARCH_MIGRATION.md` in the same change that marks the Research
   migration complete.

The Git history remains the migration record. Keeping this guide afterward would
create a second, stale source of truth.
