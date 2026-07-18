# Market Data Module

## 1. Purpose

The Market Data module provides venue-independent, auditable observations to
Research, Trading, and operator workflows. It turns data obtained from external
sources or local fixtures into canonical datasets with explicit identity,
availability time, quality, continuity, and provenance.

Its central question is:

> What market information was available, for which instrument and interval, and
> is it complete and trustworthy enough for the requested calculation?

Market Data owns facts and dataset integrity. It does not decide whether an
instrument belongs in the research universe, whether a pair is cointegrated, or
whether a trade should be placed.

## 2. Responsibilities and Boundaries

### 2.1 Market Data owns

- canonical instrument references used by observations;
- timeframe and observation-window semantics;
- normalized candles, funding observations, and market snapshots;
- closed-candle and information-availability rules;
- validation, continuity, coverage, freshness, and gap evidence;
- immutable dataset identity and provenance;
- idempotent historical backfill, refresh, and gap repair;
- storage contracts and lifecycle policies independent of a backend;
- typed outcomes for partial acquisition and validation failures.

### 2.2 Market Data does not own

- CCXT or venue-specific payloads, authentication, rate limits, and sessions;
- research universe thresholds such as minimum volume or dominant-market
  exclusion;
- spread, cointegration, indicators, signals, or portfolio construction;
- order books transformed into execution decisions;
- exchange orders, positions, balances, or account reconciliation;
- filesystem paths, database engines, or cloud vendors as domain assumptions.

External-venue translation belongs to `exchange`. Research consumes market data
and applies eligibility policy. Trading consumes market data and applies signal,
risk, and execution policy.

### 2.3 Dependency direction

```text
external provider
      |
      v
exchange adapter -----> Market Data source contract
                              |
                              v
                     canonical observations
                              |
                  +-----------+-----------+
                  |                       |
                  v                       v
              Research                 Trading

Market Data -X-> exchange implementation details
Market Data -X-> Research policy
Market Data -X-> Trading state or mutation
```

The exchange adapter depends on the canonical contracts it implements. Market
Data does not import a concrete exchange adapter or raw provider type.

## 3. Components

Market Data is organized around capabilities rather than predetermined files.

| Capability | Responsibility |
|---|---|
| Observation contracts | Represent instruments, timeframes, candles, funding, and market facts |
| Normalization | Translate source values into canonical units, ordering, and identity |
| Validation | Detect invalid values, duplicates, gaps, open observations, and inconsistent metadata |
| Dataset assembly | Align observations and bind them to an exact requested window |
| Provenance | Identify source, market profile, acquisition, transformations, and content |
| Synchronization | Backfill, refresh, overlap, pagination, retry, and gap repair |
| Storage | Persist and retrieve datasets without leaking backend details to callers |
| Lifecycle | Evaluate freshness and apply explicit retention or cleanup policies |
| Query interface | Return bounded readonly datasets and observable unavailable results |

Physical modules follow cohesive implemented behavior. Closely related
capabilities remain together when splitting them would create shallow wrappers.

### 3.1 Logical package shape

```text
market_data/
├── api.py
├── config.py
├── models.py
├── ohlcv/
├── funding/
├── validation/
├── sync/
├── lifecycle/
└── storage/
    ├── memory.py
    ├── parquet.py
    └── database.py
```

This is the stable navigation model, not a requirement to scaffold every path.
Top-level models contain the canonical identities, timeframes, observations,
datasets, and provenance shared across capabilities. Observation-specific
behavior stays in `ohlcv` or `funding`; cross-dataset quality and coverage stay
in `validation`.

Synchronization, lifecycle, and storage remain distinct because request I/O,
retention policy, and backend persistence have different side effects. Storage
files are adapters behind one contract; domain callers do not select them by
importing backend-specific code.

## 4. Public Interface

The application-facing interface supports three semantic operations:

1. Obtain or construct a dataset for an explicit instrument set, timeframe, and
   information cutoff.
2. Synchronize a bounded historical window from a readonly source into a chosen
   store.
3. Validate and inspect an existing dataset without acquiring new data.

Inputs express:

- canonical instrument identities and market context;
- observation kind and timeframe;
- inclusive or half-open temporal bounds with unambiguous meaning;
- the information cutoff used to exclude unavailable observations;
- acquisition, overlap, retry, retention, and validation policy where relevant;
- explicit source, storage, and clock capabilities at operational seams.

Outputs contain observations plus coverage, continuity, quality, provenance,
warnings, and per-instrument outcomes. A missing or incomplete dataset is an
observable result and never masquerades as an empty but valid market.

## 5. Canonical Identity

An observation is identified by more than a display symbol. Its identity
includes the venue or source context needed to disambiguate:

- base and quote assets;
- market type, such as spot, future, or perpetual swap;
- linear or inverse contract behavior where applicable;
- settlement asset;
- native venue symbol and canonical system identity;
- contract multiplier or unit semantics when relevant.

Native symbols are preserved as provenance but do not become filenames or
cross-module identifiers by string replacement. Two distinct native symbols
cannot collide after persistence.

Symbol mappings are explicit and reversible. Market Data never reconstructs a
symbol from a sanitized path.

## 6. Timeframe and Availability Semantics

A timeframe represents an exact duration or a separately modeled calendar
interval. Time arithmetic is centralized and rejects unsupported or
non-divisible values rather than approximating silently.

For fixed-duration candles:

```text
candle interval = [open_time, close_time)
close_time       = open_time + timeframe duration
```

The canonical candle timestamp denotes interval open time. A candle is available
to a consumer only when its close time is less than or equal to the consumer's
information cutoff.

At an exact boundary, the candle that has just ended is closed; the candle that
opens at that boundary is not. Every acquisition and replay operation freezes
its cutoff once and carries it through the complete run.

Source timestamps are converted to UTC instants without guessing units from
ambiguous magnitudes once the source contract is known. The original source
unit and transformation remain part of provenance.

## 7. Candle Contract

A canonical candle records:

- instrument identity;
- timeframe;
- open time and derived close time;
- open, high, low, close, and volume;
- source and market-profile provenance;
- availability/finality evidence when the provider exposes revisions.

For each candle:

- all prices are finite and strictly positive;
- volume is finite and non-negative;
- high is greater than or equal to open, close, and low;
- low is less than or equal to open, close, and high;
- timestamps are aligned to the declared timeframe;
- one dataset contains at most one canonical row per timestamp.

Normalization and validation are distinct. Normalization may perform lossless
unit conversion, column mapping, stable sorting, and deterministic duplicate
resolution when the source policy explicitly permits it. Invalid rows are not
silently dropped. Every discarded or replaced row is counted and explained.

Duplicate resolution preserves the source ordering or revision rule used to
choose the retained row. Conflicting duplicates without an authoritative rule
invalidate the affected dataset.

## 8. Funding Contract

A funding observation records:

- canonical derivative-market identity;
- effective or settlement timestamp;
- funding rate and its unit convention;
- funding interval or next settlement information when available;
- source and acquisition provenance.

Funding is stored as its own event series. It is not expanded into arbitrary
candle rows or converted to an hourly rate without the actual settlement
semantics. Missing historical funding remains missing evidence and is not
silently replaced by zero.

## 9. Market Facts and Snapshots

Readonly market facts describe source observations such as:

- whether a market is active;
- market type, settlement, and contract properties;
- current price or reference price when available;
- base and quote volume with their declared units;
- provider observation time.

Missing volume is distinct from zero volume. Research may use these facts for
universe construction, but the eligibility thresholds and dominant-market rules
belong to Research.

Snapshots are time-qualified. A current ticker without an observation or fetch
time cannot be treated as historical evidence.

## 10. Dataset Contract

A dataset binds canonical observations to one exact request and includes:

- observation kind;
- ordered instrument set;
- timeframe where applicable;
- requested and effective temporal bounds;
- information cutoff;
- source and market profile;
- validation and continuity evidence;
- acquisition and transformation provenance;
- stable content identity.

Dataset identity changes when any observation or meaningfully relevant semantic
input changes. Generated timestamps and storage locations do not alter semantic
identity unless explicitly included in a separate envelope.

Consumers receive the exact dataset associated with the run. They do not scan a
directory, infer the universe from available files, or mix datasets with
different market profiles or cutoffs.

## 11. Validation, Coverage, and Continuity

Validity, coverage, continuity, completeness, and freshness are different facts:

- **Validity:** every observation satisfies its canonical contract.
- **Coverage:** observations span the requested temporal bounds.
- **Continuity:** expected timestamps are present or gaps are explicitly known.
- **Completeness:** the acquisition reached its declared terminal boundary.
- **Freshness:** the newest available observation is recent enough for a
  particular consumer policy.

A dataset can be valid but incomplete, complete but stale, or continuous over a
shorter window than requested. These states are never collapsed into one generic
quality flag.

For fixed timeframes, expected timestamps derive from the requested interval and
timeframe grid. Gap evidence records count, duration, location, and whether the
gap lies at a boundary or inside the series.

Market Data does not interpolate missing OHLCV by default. Any synthetic
observation requires an explicit transformation policy and remains visibly
synthetic to consumers.

## 12. Historical Synchronization

### 12.1 Backfill

Backfill acquires a bounded historical window and is idempotent for the same
semantic request. Pagination must make monotonic progress, respect the frozen
information cutoff, and stop on a declared terminal condition.

Every page is normalized and validated before merge. The synchronizer rejects a
provider that repeatedly returns the same page or observations beyond the
requested cutoff.

Existing data is reused only after its identity, metadata, and content prove
coverage of the request. Metadata claims alone are insufficient when the stored
payload cannot validate them.

### 12.2 Refresh

Refresh updates the newest portion of an existing dataset using an explicit
overlap. Overlap handles provider revisions and makes duplicate resolution
deterministic.

Tail refresh and interior-gap repair are separate operations. A dataset is not
declared complete merely because its final timestamp reaches the requested end.
Interior gaps remain visible until repaired or accepted by policy.

### 12.3 Partial outcomes and retry

Synchronization returns a per-instrument outcome as well as the aggregate run
result. One failed instrument does not erase successful evidence for others, but
the aggregate result cannot claim complete success.

Readonly transient failures may be retried under bounded backoff and pacing
policy. Authentication, invalid requests, unsupported capabilities, and data
contract failures are not retried as transient network failures.

## 13. Storage and Atomicity

The storage contract is independent of Parquet, a relational database, object
storage, or memory. A store preserves canonical identity, observations,
metadata, and content hashes together.

Writes validate before publication and become visible atomically. A failed write
cannot leave a valid-looking partial dataset. Concurrent writers are rejected or
coordinated explicitly; last-writer-wins behavior is not implicit.

Storage keys are collision-safe and do not rely on lossy symbol sanitization.
Reading metadata does not create directories or mutate storage.

Backend-specific metadata is separated from canonical dataset provenance.
Round-tripping through a store preserves semantic observations, identity,
ordering, dtypes/units, and quality evidence.

## 14. Lifecycle, Freshness, and Retention

Freshness is evaluated relative to an explicit clock and consumer policy. It is
not embedded as a universal number inside a dataset.

Retention and cleanup are explicit operational policies. They report planned and
performed changes, support dry-run behavior, and never silently delete the only
copy of required provenance.

After retention, coverage and continuity metadata are recomputed from retained
content. A pruned dataset cannot continue claiming the wider window it once
contained.

Cleanup and retention do not run during import or ordinary reads. Destructive
actions identify exact targets and remain separate from synchronization success.

## 15. Provenance

Dataset provenance records enough information to reproduce or explain the data:

- schema and normalization versions;
- source, venue, market profile, and native identities;
- observation kind and timeframe;
- request bounds and information cutoff;
- acquisition time and page/window evidence;
- validation, duplicate, gap, and revision outcomes;
- transformation and retention policies;
- row count and effective bounds;
- stable content hash.

Provider responses may also have immutable raw-response references when the
acquisition workflow preserves them. Canonical data does not need to embed raw
payloads to retain traceability.

## 16. Error Semantics

Expected outcomes are represented distinctly:

- source unavailable or rate limited;
- unsupported market-data capability;
- invalid request or timeframe;
- no observations returned;
- partial coverage;
- invalid observations;
- continuity gaps;
- stale data;
- storage conflict or corruption;
- unexpected infrastructure failure.

An empty dataset, an unavailable dataset, and a valid market with no activity
are different outcomes. Callers do not infer meaning from an empty DataFrame or
an exception message.

## 17. Determinism and Reproducibility

Identical semantic inputs and source responses produce identical canonical
datasets. Determinism includes:

- stable instrument and row ordering;
- explicit duplicate and revision policy;
- fixed information cutoffs;
- explicit clocks;
- canonical serialization and hashing;
- versioned normalization rules;
- stable aggregation of per-instrument results.

Retry timing, generated timestamps, and storage paths do not alter semantic
dataset content.

## 18. Side-Effect and Concurrency Boundaries

Normalization, validation, merging, continuity analysis, and hashing are pure
over supplied values. Network and storage effects remain at explicit seams.

No import creates a provider session, reads credentials, creates directories,
contacts a network, or prunes data. Source sessions and stores have explicit
lifecycle ownership and close reliably on success, failure, or cancellation.

Synchronization applies bounded concurrency and provider-aware rate limits.
Result ordering remains stable even when requests execute concurrently.

## 19. Safety Invariants

- Market Data is readonly with respect to exchange orders and positions.
- Historical acquisition never requires order-mutation credentials.
- Open or unavailable candles cannot enter a decision dataset.
- Invalid rows are never silently converted into economic signals.
- Synchronization cannot trigger Research, promotion, or Trading mutation.
- Retention cannot hide lost coverage or continuity.
- Default tests use deterministic sources and do not call external networks.
- Dataset existence is not evidence that its quality or freshness is sufficient
  for a particular consumer.
