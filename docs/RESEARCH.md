# Research Module

## 1. Purpose

The Research module turns an explicit, immutable historical dataset and an
explicit research configuration into auditable evidence about candidate
statistical-arbitrage pairs.

Its central question is:

> Given exactly these markets, observations, temporal boundaries, statistical
> policies, and cost assumptions, which pairs have enough reproducible evidence
> to be considered for a separate operator promotion decision?

Research produces evidence. It does not place orders, manage positions, mutate
trading state, approve capital, or claim that an observed historical edge will
continue.

## 2. Responsibilities and Boundaries

### 2.1 Research owns

- constructing a reproducible search universe from validated observations;
- discovering statistically plausible pair relationships;
- validating those relationships on later, untouched time periods;
- applying stress and economic-simulation policies;
- accepting or rejecting candidates with machine-readable reasons;
- producing typed research results and human-readable reports;
- orchestrating the above stages through one public API.

### 2.2 Research does not own

- exchange authentication, request signing, or network transport;
- canonical symbol, candle, dataset, or storage implementations;
- pair identity or the cross-module candidate artifact contract;
- order intents, execution, fills, portfolio state, or PnL accounting for a
  running trader;
- user interfaces, Telegram, HTTP, scheduling, or login;
- database selection or cloud infrastructure;
- promotion approval.

Those concerns belong to `exchange`, `market_data`, `pairs`, `trading`,
`interfaces`, or infrastructure adapters. Research consumes only their public
types and does not reach through their internals.

### 2.3 Dependency direction

```text
interfaces / schedulers
          |
          v
 Research public interface
          |
          +------> Research stages and pure quantitative functions
          |
          +------> pairs public contracts
          +------> market_data public contracts
          +------> minimal core primitives

research -X-> exchange mutation
research -X-> trading runtime
research -X-> interface implementations
```

Research consumes historical datasets through a readonly contract. Local
fixtures, Parquet readers, databases, and exchange-backed readers implement the
`market_data` seam; none becomes part of Research.

## 3. Components

Research is organized around capabilities rather than predetermined files. The
physical package layout follows the cohesive behaviors that emerge from these
responsibilities.

| Capability | Responsibility |
|---|---|
| Public interface and orchestration | Run the complete flow without exposing its internal choreography |
| Configuration boundary | Validate quantitative and operational policies before calculations begin |
| Research evidence | Represent inputs, stage outcomes, warnings, rejections, and final results |
| Universe construction | Apply eligibility, volume, liquidity, dominance, data-quality, return-matrix, and clustering rules |
| Pair discovery | Define orientation, estimate the spread, test cointegration, and control multiple testing |
| Temporal validation | Separate formation, validation, and final out-of-sample evidence |
| Stress evaluation | Measure sensitivity to parameters, costs, delays, liquidity, and subperiod changes |
| Historical simulation | Replay a declared historical decision policy with causal timing, portfolio weights, friction, and performance accounting |
| Reporting | Present already-computed evidence without making quantitative decisions |

This separation describes ownership, not a required one-file-per-capability
layout. Closely related behavior remains together when splitting it would only
create shallow modules or additional caller knowledge.

### 3.1 Logical package shape

```text
research/
├── api.py
├── config.py
├── models.py
├── universe/
├── discovery/
├── validation/
├── backtest/
├── stress/
└── reporting/
```

This tree defines stable conceptual homes and a navigation model. It does not
require every path to exist before its behavior does. A capability may begin in
one cohesive module and deepen into a package when that reduces caller
knowledge and keeps its interface small.

`api.py`, `config.py`, and `models.py` identify structural roles: the public
research use case, typed research policy, and cross-stage result contracts.
They do not prescribe private helper files. Statistical behavior remains with
its purpose in `discovery`, `validation`, `backtest`, or `stress`; Research does
not create a generic `statistics` or `utils` package.

## 4. Public API

Research presents an application-facing interface for complete research runs
rather than requiring callers to coordinate its internal stages.

Its semantic inputs are:

- run identity and temporal boundaries;
- validated quantitative configuration;
- normalized, readonly historical observations and their provenance;
- explicit operational dependencies, such as generated time and persistence,
  when the requested flow needs them.

Dependencies enter explicitly rather than through a generic service locator.
Quantitative evaluation remains usable without persistence, allowing callers to
keep computation and publishing as separate failure boundaries.

Quantitative functions receive values and return values. They do not read
environment variables, resolve paths, access a database, call an exchange, read
the wall clock, or serialize JSON.

### 4.1 Run result

The run result contains:

- run identity and terminal status;
- configuration, code, dataset, and universe provenance;
- exact temporal splits;
- counts entering and leaving every stage;
- accepted and rejected pairs;
- machine-readable rejection reasons and warnings;
- statistical estimates and diagnostics;
- backtest and stress evidence where completed;
- an optional candidate pair set only when all mandatory stages succeed;
- a presentation-neutral report model.

An invalid or incomplete run must never return a valid-looking candidate set.

## 5. Domain Model

The domain model uses focused values rather than one oversized run object or raw
dictionaries passed between stages.

### 5.1 Run inputs

Run inputs represent:

- a stable identity for one evaluation;
- timeframe, temporal boundaries, and quantitative policies;
- normalized observations and their provenance;
- the exact ordered universe and its selection evidence;
- non-overlapping formation, validation, and final OOS windows.

### 5.2 Stage results

Every stage records status, input and output counts, diagnostics, warnings, and
rejections. Expected domain failure is observable evidence, not an exception
hidden in a log. Stage results cover universe construction, pair discovery,
temporal validation, stress evaluation, historical simulation, and the complete
run.

### 5.3 Status and rejection semantics

The result distinguishes successful completion, completion with warnings, a
valid run with no candidates, insufficient data, an invalid request, and an
unexpected failure.

Insufficient data is never equivalent to a flat trading signal or a rejected
economic hypothesis. Rejections use stable machine-readable reasons for cases
such as insufficient coverage, failed stationarity evidence, multiple-testing
rejection, unstable hedge ratios, or failed out-of-sample evidence.

### 5.4 Pair identity and orientation

Identity and orientation are separate concepts.

- Pair identity represents an unordered relationship and prevents duplicate
  search of the same two instruments.
- Pair orientation identifies the dependent asset $X$ and hedge asset $Y$ used
  by the model.
- Every estimate, spread series, report row, and artifact records orientation.
- Reversing orientation creates a different fitted model but not a new unordered
  search candidate.
- Research evaluates both orientations as separate hypotheses. Both count in
  the whole-run multiple-testing family and retain their own evidence.
- At most one orientation of an unordered pair can enter one candidate pair
  set. If both survive every gate, Research chooses the lower BH-adjusted
  p-value, then the more negative ADF statistic, then canonical instrument
  ordering as an exact deterministic tie-breaker.

The `pairs` module owns the cross-module representation. Research owns the
policy for choosing or comparing orientations.

## 6. Configuration

Configuration is typed, immutable after validation, and rejects unknown fields.
It separates policies for universe construction, data quality, clustering,
cointegration, multiple testing, temporal validation, historical decision
evaluation, portfolio construction, friction, stress, and candidate acceptance.

Config loading from YAML, environment variables, CLI flags, or a database is an
adapter concern. Quantitative code receives the validated objects.

Every policy that affects output is included in provenance. Material research
choices have no hidden code or library defaults; a library upgrade must not
silently change statistical behavior.

### 6.1 Configuration layers

Application composition uses two distinct configuration layers:

1. A **run configuration** selects the venue market profile, timeframe,
   immutable dataset request or reference, exact universe manifest, research
   policy identity, and information cutoff.
2. A reusable **research policy** declares temporal windows, discovery rules,
   estimator, stationarity and multiplicity policy, historical simulation,
   friction, stress scenarios, and candidate-acceptance gates.

The venue selection belongs to application configuration and adapters. Research
does not contain `bybit`, `binance`, `kucoin`, `USDT`, `swap`, or `1m` branches.
A configured linear-USDT-perpetual profile may initially resolve through Bybit,
but the quantitative code sees canonical instruments and market data only.

YAML is one input adapter, not a domain contract. It is parsed once at the
entrypoint into strict typed values. Domain functions never receive raw
dictionaries, paths, environment names, or partially validated configuration.

The following is a semantic shape, not a promise of these exact YAML field
names:

```yaml
run:
  venue_profile: bybit
  market_profile: linear_usdt_perpetual
  timeframe: 1m
  dataset: {request_or_immutable_reference: explicit}
  universe_manifest: {instrument_ids: explicit}
  research_policy: baseline_v1
  information_cutoff: explicit_utc_instant

research_policy:
  temporal_plan:
    formation: {duration: explicit, minimum_observations: explicit}
    validation: {duration: explicit, minimum_observations: explicit}
    final_oos: {duration: explicit, minimum_observations: explicit}
    warmup: derived
  universe:
    eligibility: explicit
    clustering: {method: louvain, seed: explicit, resolution: explicit}
  spread_estimator: {method: ols, intercept: true, time_trend: false}
  stationarity:
    method: residual_adf
    max_lag: schwert
    autolag: aic
    nominal_alpha: 0.05
  multiplicity: {method: bh_fdr, family: whole_run, q: 0.05}
  historical_simulation:
    decision_policy: {method: rolling_zscore, parameters: explicit}
    fills: {decision: after_close, price: next_open, slippage: explicit}
    holding:
      hard_max_duration: null
      maximum_half_life: explicit
      maximum_holding_p90: explicit
  friction: {fees: explicit, slippage: explicit, funding: explicit}
  stress: {scenarios: explicit}
  candidate_acceptance:
    mode: diagnostic
    # candidate_evaluation instead requires an explicit policy id and all gates
```

### 6.2 Diagnostic and candidate-evaluation modes

A diagnostic run may omit candidate-acceptance thresholds. It can produce
stage evidence, rejected alternatives, and a report, but cannot produce a
`CandidatePairSet`.

A candidate-evaluation run requires one complete, explicit, versioned
acceptance policy. Missing or unknown gates fail validation. Real-data gate
values have deliberately not been approved yet and therefore have no product
defaults. Test configurations may contain clearly marked artificial values to
exercise acceptance and rejection; those values do not authorize promotion or
become recommendations for real research.

## 7. End-to-End Flow

```text
research request + validated historical dataset
                    |
                    v
          exact universe manifest
                    |
                    v
       quality-screened aligned prices
                    |
                    v
       returns graph and deterministic clusters
                    |
                    v
       unordered pair search space
                    |
                    v
       both fitted orientations and canonical spreads
                    |
                    v
       cointegration + FDR acceptance
                    |
                    v
       temporal validation and stability checks
                    |
                    v
       causal historical replay and friction model
                    |
                    v
       stress/scenario robustness gates
                    |
                    v
       candidate pair set + research report
```

Each arrow is an observable stage boundary. Counts and rejection reasons must
make it possible to answer why a symbol or pair disappeared.

## 8. Market-Data Contract

Research accepts canonical observations from `market_data`. At minimum, every
candle identifies:

- canonical instrument identity;
- venue/market profile where relevant;
- timeframe;
- timezone-aware timestamp;
- timestamp meaning;
- open, high, low, close, and volume;
- whether the observation is closed and final.

A candle timestamp represents interval open time. A decision using that candle
occurs only after its close time. The earliest simulated fill is the next
executable event allowed by the execution model.

Before use, the dataset validates:

- unique, monotonic timestamps per instrument;
- finite and positive prices;
- valid OHLC relationships and non-negative volume;
- expected frequency and explicit gaps;
- required coverage for every temporal window;
- no observation beyond the run's information boundary;
- no open or partially formed candle;
- stable symbol identity through persistence.

Discovery consumes only the dataset and exact manifest attached to the run. It
must not scan a directory and implicitly include unrelated or stale files.

Dataset provenance includes source identity, canonical symbols, boundaries,
timeframe, validation result, and a content hash or equivalent immutable
identity.

## 9. Universe Construction

Universe construction limits the statistical search to instruments that are
eligible, sufficiently liquid, and supported by comparable data.

### 9.1 Eligibility and liquidity

Universe construction applies two kinds of screens:

1. Market metadata and ticker screens before expensive history acquisition:
   active market, supported quote/settlement asset, contract type, price,
   notional volume, and optional exclusion of a configurable number of dominant
   instruments.
2. Historical quality and liquidity screens on the exact dataset: coverage,
   gap rate, zero-volume rate, stale-close rate, and robust daily/intraday
   notional-volume statistics.

No quote asset such as USDT or USDC is hard-coded inside quantitative logic.
Market profiles provide eligibility rules.

Historical conclusions inherit survivorship and listing bias when the universe
is selected from current active instruments. Reports state whether the input
manifest is point-in-time accurate and surface the limitation whenever it is
not.

### 9.2 Return matrix

For closing price $P_{i,t} > 0$, the one-period log return is

$$
r_{i,t} = \log(P_{i,t}) - \log(P_{i,t-1}).
$$

Alignment and missing-value policy are explicit. Any clipping or winsorization
is a configured preprocessing decision and must be recorded because it changes
the graph. The unmodified price levels remain available for pair estimation.

### 9.3 Correlation graph and clusters

Research computes pairwise Spearman correlations on the formation return
matrix, adds an undirected edge when the configured correlation condition and
overlap requirement pass, and uses Louvain community detection to reduce the
pair search space.

The graph uses stable node ordering. Louvain receives an explicit seed and
recorded resolution. A degenerate graph or singleton cluster produces an
observable result, not an exception or invented candidate.

Only unordered pairs within eligible clusters proceed to discovery. The report
records the full possible pair count and the reduced tested count.

## 10. Spread and Cointegration

### 10.1 Canonical regression

For one explicit orientation, define log prices

$$
x_t = \log(P^X_t), \qquad y_t = \log(P^Y_t).
$$

The formation window estimates

$$
x_t = \alpha + \beta y_t + \varepsilon_t
$$

using ordinary least squares, and defines the only canonical spread for that
fitted model as

$$
s_t = x_t - \alpha - \beta y_t.
$$

The same $\alpha$, $\beta$, orientation, and formula are used for the
residual stationarity test, half-life, z-score, validation, backtest, reporting,
and artifact. It is invalid to test residuals from one estimator and trade a
spread produced by another.

The baseline includes the intercept $\alpha$ and excludes a deterministic time
trend such as $\gamma t$. "No time trend" never means "no intercept."

If both orientations are evaluated, each receives its own fitted model and
diagnostics. The orientation policy must not take the best p-value from one
regression and combine it with coefficients from the other.

OLS is the first implemented estimator, not a permanent assertion that it is
best. WLS or EW-WLS, robust/M-estimators, DOLS, and FM-OLS are acknowledged
future alternatives. They are unsupported in the first vertical and their
configuration names must fail rather than silently fall back to OLS. Each
additional estimator would create another searched hypothesis and must preserve
the complete-model invariant above.

### 10.2 Engle-Granger procedure

The first vertical uses an augmented two-step Engle-Granger procedure:

1. Fit the canonical OLS regression on formation data.
2. Apply the Augmented Dickey-Fuller test to that exact residual series.

Its frozen statistical baseline is:

- first-stage OLS with an intercept and no deterministic time trend;
- residual ADF on the exact fitted residual;
- Schwert maximum lag
  $\lfloor 12(n/100)^{1/4}\rfloor$;
- AIC selection among allowed ADF lags;
- raw nominal significance level $\alpha=0.05$;
- whole-run Benjamini-Hochberg FDR control at $q=0.05$.

The cointegration configuration fixes and records:

- deterministic terms in the cointegrating regression;
- ADF regression terms for residuals;
- lag-selection method and maximum lag;
- minimum observations and overlap;
- nominal significance level;
- critical-value/p-value source;
- behavior for constants, singular matrices, non-finite values, and numerical
  failures.

Library defaults are insufficient as a contract. The report records method and
semantic version, sample size, maximum and selected lag, test statistic,
p-value, critical values, coefficients, and failure reason.

Fixed-lag, BIC, and t-stat lag policies and Phillips-Perron or KPSS diagnostics
are acknowledged future options, not first-vertical behavior. KPSS has the
opposite null hypothesis from ADF, so adding it as a mandatory gate requires an
explicit conflict/combination policy. Unsupported methods fail configuration.

### 10.3 Multiple testing

Searching many pairs and possibly multiple orientations inflates false
discoveries. A permissive unadjusted p-value is not an acceptance policy.

The first hypothesis family is the whole run: every tested unordered pair times
each orientation and estimator. Research applies the Benjamini-Hochberg
procedure at false-discovery rate $q=0.05$. For ordered p-values
$p_{(1)} \le \dots \le p_{(m)}$, it selects the
largest $k$ such that

$$
p_{(k)} \le \frac{k}{m}q,
$$

and accepts ranks $1$ through $k$ for subsequent validation. Both raw and
adjusted evidence, family identity, and $m$ are recorded.

The raw 5% level is a test threshold, not a 95% probability that a pair is
cointegrated. Likewise, FDR 5% controls the expected false-discovery proportion
under its assumptions; it does not certify any individual pair with 95%
confidence.

### 10.4 Half-life

For the canonical spread, estimate the mean-reversion approximation

$$
\Delta s_t = c + \lambda s_{t-1} + \eta_t.
$$

When $\lambda < 0$, the implied half-life in observations is

$$
h = -\frac{\ln(2)}{\lambda}.
$$

Non-negative $\lambda$, insufficient observations, or invalid fits produce an
explicit unavailable/rejected diagnostic. Half-life bounds are validation
policy, not silent clipping.

### 10.5 Rolling z-score

For lookback $L$, the calculation uses only information available at time $t$:

$$
z_t = \frac{s_t - \mu_{t,L}}{\sigma_{t,L}},
$$

where $\mu_{t,L}$ and $\sigma_{t,L}$ are rolling statistics over the declared
trailing window ending at $t$. Degrees of freedom, minimum periods,
and zero-variance behavior are explicit policy. The first usable timestamp must
be mechanically derivable from the lookback.

## 11. Temporal Validation

Parameter selection and performance measurement cannot use the same future
observations.

Every evaluable pair uses ordered, non-overlapping windows:

- **formation:** universe relationships, orientation, coefficients, and initial
  statistical evidence;
- **validation:** model and parameter acceptance without refitting on final OOS;
- **final OOS:** one untouched estimate of the selected procedure.

Boundaries are explicit. Warm-up is derived from the largest declared rolling
requirement and is not counted as an evaluation or profit period. Each
evaluation window starts flat so earlier positions cannot leak returns into it.
The first vertical has no mandatory embargo beyond the closed-candle and
next-open causal boundary; adding one later is an explicit temporal-policy
change.

Validation chooses from a small predeclared historical-decision-policy grid. It
never chooses solely by maximum PnL and requires minimum trade count, stability,
and friction-aware evidence. The selected model and parameters are frozen
before their single final-OOS evaluation.

Window sizes are not universal candle counts. A 1-minute, 1-hour, and 1-day
profile observe very different calendar history and numbers of mean-reversion
cycles. Real profiles therefore declare timeframe-aware durations and minimum
observations. No production formation, validation, OOS, or warm-up values are
approved by this baseline.

When configured, walk-forward validation repeats formation/validation cycles
while preserving a final holdout that remains untouched by selection.

Validation measures, at minimum:

- residual stationarity and coefficient stability;
- half-life plausibility;
- spread variance and crossing behavior;
- sensitivity to window and threshold perturbations;
- OOS trade count and exposure;
- performance before and after declared friction;
- concentration in a small number of trades or periods.

## 12. Historical Decision Policies and Causal Backtest

Research replays decisions only to test whether statistical evidence survives
a declared trading interpretation and realistic friction. These are historical
counterfactual decisions, not current actionable signals. Trading later owns
the current z-score calculation, runtime state, entry eligibility, risk checks,
and order intents.

The first historical decision policy is a rolling z-score with mean and
standard-deviation bands, equivalent to a basic Bollinger-style spread rule.
Explicit Bollinger variants and Ornstein-Uhlenbeck-fitted or optimal decision
policies are acknowledged future alternatives and are not implemented by the
first vertical. Any future OU parameters must be fitted on formation data and
frozen before OOS. Unsupported decision-policy names fail configuration.

### 12.1 State machine

A single-pair historical replay uses explicit states `FLAT`, `LONG_SPREAD`, and
`SHORT_SPREAD`.

- enter long spread when $z_t \le -z_{entry}$;
- enter short spread when $z_t \ge z_{entry}$;
- exit when the spread crosses the configured exit band;
- optionally stop when an explicitly supported extreme or model-validity
  condition is reached.

Entry and exit rules are side-aware and test equality at boundaries. Missing or
invalid observations produce `UNAVAILABLE`, not `FLAT`.

### 12.2 Information and fill timing

A decision from candle $t$ can use only information known after that candle is
closed. Its return cannot be earned before the next permitted simulated fill.
Signal time, decision time, order time, fill time, and mark time are distinct
concepts even in a vectorized test.

The baseline decides after candle close and fills at the next candle open with
explicitly configured slippage. Other fill conventions require a separately
versioned policy. Intrabar high/low cannot trigger a decision that also fills
earlier on the same bar. In live operation, actual execution reports replace
research assumptions.

### 12.3 Portfolio weights

Statistical spread coefficients and economic holdings must tell a coherent
story.

For canonical spread $x - \alpha - \beta y$, the raw exposure vector is

$$
w^{raw} = (1, -\beta).
$$

The portfolio policy normalizes this vector according to an explicit
gross-notional rule while preserving its ratio and side. Any volatility scaling
applies to the pair as a unit. Independently assigning inverse-volatility
weights to both legs would create a different portfolio from the tested spread.

The report records gross, net, and leg notionals and states whether the strategy
is beta-neutral, dollar-neutral, or neither. These terms are not interchangeable.

### 12.4 Returns, turnover, and friction

Portfolio return over an interval is computed from positions that were already
executable at the interval start. Any change in weights creates turnover:

$$
\text{turnover}_t = \sum_i |w_{i,t} - w_{i,t-1}|.
$$

The friction model separates:

- trading fees by actual simulated execution type;
- spread/slippage assumptions;
- configured market-impact assumptions;
- funding by instrument, direction, historical rate, and elapsed funding
  interval;
- borrow or other carrying costs where applicable.

Funding is not converted to an hourly number and charged once per arbitrary
candle. It accrues using actual elapsed time or historical settlement events.
Configured but unused fee fields are validation errors.

PnL metrics include both gross and net results. The simulator never presents a
theoretical signal return as a realized fill-derived return.

### 12.5 Holding-duration evidence

The baseline does not force an exit solely because a universal maximum age was
reached. Instead, profiles may constrain the fitted half-life and historical
holding evidence relative to the intended trading horizon. Research reports
completed holding median, p90, maximum, and unresolved positions. Half-life is
an estimate of likely mean-reversion speed, not a promise that a position will
close within that duration.

A hard time-based exit remains an optional future decision policy. If added, it
must be explicit in configuration and evaluated as part of the same historical
policy; it cannot appear as a hidden safety constant.

## 13. Stress Evaluation

Stress answers whether a result is robust to plausible variations; it is not a
search for the most flattering parameter combination.

The scenario set covers:

- nearby z-score lookbacks and entry/exit thresholds;
- increased fees and slippage;
- delayed fills;
- reduced liquidity or capped notional;
- missing-bar/data perturbations that remain semantically valid;
- shifted formation/validation boundaries;
- coefficient and spread-stability checks across subperiods.

The grid is declared before evaluation. The report contains the full response
surface, not only the winner. Candidate-acceptance criteria set the required
share of viable neighboring scenarios, minimum trade evidence, drawdown bounds,
and net-performance evidence. Maximum total PnL alone is insufficient.

The structure of these gates is mandatory for candidate evaluation, but their
real-data numeric values are intentionally deferred to the candidate-acceptance
slice. Too few trades produces `INSUFFICIENT_EVIDENCE`, not an ordinary
rejection or a flat signal. Failure of any mandatory gate prevents candidate
creation and remains visible in provenance and reporting.

Stress does not overwrite discovery evidence. The lifecycle is explicit:

```text
DISCOVERED
-> TEMPORALLY_VALIDATED
-> ECONOMICALLY_EVALUATED
-> STRESS_EVALUATED
-> CANDIDATE
-> OPERATOR_PROMOTED (outside Research)
```

## 14. Candidate Artifact and Provenance

The in-memory boundary is a typed candidate pair set owned by `pairs`. JSON is a
serialization format at an adapter boundary, not the domain model and not a
crypto asset.

JSON is the human-inspectable, portable, diffable serialization used for
candidate artifacts. Strict schemas, versioning, canonical serialization, and
hashes address its weak typing at the storage boundary. A database or columnar
adapter can replace JSON without changing the domain contract.

A candidate artifact is immutable and records at least:

- schema and lifecycle-stage versions;
- research run id and generated time from an explicit clock;
- code version when available;
- complete relevant config identity;
- dataset and universe identity;
- venue/market profile and timeframe;
- temporal boundaries and information cutoff;
- unordered pair identity and fitted orientation;
- canonical spread formula, intercept, hedge ratio, and estimator;
- statistical diagnostics, multiplicity evidence, and sample sizes;
- chosen historical-decision/portfolio/friction policies;
- validation, OOS, and stress evidence;
- warnings, limitations, and acceptance reason;
- stable content hash.

Serialization validates on write and read. Persistence uses atomic replacement
for mutable pointers, while immutable content-addressed or run-addressed
artifacts preserve history.

Research produces candidates but cannot promote them. Promotion is a distinct
operator action with its own audit trail.

## 15. Reporting

Reporting renders already-computed evidence. It does not re-run calculations or
invent acceptance logic.

The canonical report model answers:

- what exact request and dataset ran;
- which stages completed;
- how many instruments/pairs entered and left each stage;
- why every rejected pair failed;
- which assumptions and known limitations apply;
- whether results are formation, validation, or final OOS;
- how sensitive results are to parameters and costs;
- where the machine-readable artifact is stored and how it is identified.

Markdown, HTML, console, and UI renderers consume the public report model or an
application API rather than importing quantitative internals.

## 16. Determinism and Reproducibility

Identical semantic inputs must produce identical semantic outputs, excluding
explicitly identified operational metadata.

Required controls include:

- stable symbol and pair ordering;
- explicit random seeds;
- pinned statistical choices rather than library defaults;
- immutable configs and temporal plans;
- explicit clock injection;
- canonical serialization and hashing;
- dataset and universe provenance;
- deterministic tie-breaking;
- recorded dependency/code versions where relevant.

Generated timestamps must not change the semantic candidate content hash unless
the artifact contract explicitly includes them in a separate envelope hash.

## 17. First Offline Acceptance Story

The first executable vertical is a deterministic test fixture, not a market
recommendation or a set of production defaults. It proves that the contracts
compose end to end:

- configured profile semantics: linear USDT perpetual swap at `1m`;
- exactly four synthetic canonical instruments in an explicit manifest;
- 1,500 formation bars, 500 validation bars, and 500 final-OOS bars;
- derived warm-up, closed valid candles, no gaps, and a frozen information
  cutoff;
- OLS/intercept/no-trend, residual ADF with Schwert/AIC, and whole-run BH-FDR;
- both orientations evaluated independently;
- one pair and orientation accepted, with every alternative rejected for an
  observable machine-readable reason;
- rolling-z-score/Bollinger-style historical decisions, next-open fills, and
  explicit artificial slippage, cost, stress, and acceptance values;
- deterministic synthetic funding-settlement events for derivative net
  evidence;
- no network, exchange credentials, ambient path scan, prior artifact, or venue
  mutation.

The fixture's bar counts and gates are deliberately test-only and
non-promotable. They exercise code paths; they do not answer how much real
history or what performance threshold a `1m`, `1h`, or `1d` strategy needs.
Real policy remains explicit per profile and cannot inherit these values.

The expected semantic output is one typed synthetic candidate, marked with test
provenance and incompatible with promotion, plus complete run and rejection
evidence. Repeating identical semantic inputs produces the same semantic result
and content hash, excluding declared operational envelope metadata. The exact
test command is documented only when that test exists and has been executed
successfully.

## 18. Error and Side-Effect Boundaries

Expected data and hypothesis outcomes use typed results. Exceptions are reserved
for violated programmer invariants or infrastructure failures that cannot be
represented locally.

Side effects are restricted to orchestration edges:

- quantitative modules are pure over supplied arrays/models;
- storage is accessed through small readonly/write interfaces justified by a
  real local adapter and test double;
- reports and artifacts are written only after typed validation;
- no import starts network, reads credentials, creates directories, or mutates
  process-wide state.

Composition is preferred at real capability seams. Pure mathematical functions
do not need protocols, factories, or classes merely for architectural symmetry.
Framework model inheritance is acceptable when it expresses validation rather
than substitutable business behavior.

## 19. Computational Characteristics

Research uses clear vectorized operations and bounded loops. Optimization is
based on measured bottlenecks and preserves deterministic results.

Large arrays need intentional alignment and copy behavior. Parallel evaluation
maintains stable result ordering, explicit resource limits, and deterministic
seeds.

## 20. Safety Invariants

- Research is readonly with respect to venues and trading state.
- Research never requires trading credentials.
- Research cannot submit, amend, cancel, or close orders.
- Candidate generation cannot promote itself.
- A recalculation cannot change already-open trading positions.
- Invalid or missing data cannot become a trading action.
- Default tests never call external networks.
- No Research result is evidence of real-capital readiness by itself.
