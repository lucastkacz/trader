# Pairs Module

## 1. Purpose

The Pairs module owns the stable language used to describe a statistical-
arbitrage pair and to transfer an approved pair set between Research and
Trading.

It makes pair identity, fitted orientation, calibrated parameters, evidence,
artifact lifecycle, integrity, and compatibility explicit. Callers work with
typed values; JSON or another persistence format is an adapter representation.

The module prevents the same pair from changing meaning as it moves from
research results to operator review and, eventually, runtime consumption.

## 2. Responsibilities and Boundaries

### 2.1 Pairs owns

- unordered pair identity;
- fitted orientation and canonical instrument roles;
- immutable calibrated pair specifications;
- typed candidate and promoted pair-set models;
- schema validation and compatibility;
- artifact identity, canonical serialization, and content integrity;
- candidate, promotion, supersession, and retirement transitions;
- promotion audit evidence;
- storage contracts for immutable pair sets and mutable lifecycle pointers.

### 2.2 Pairs does not own

- universe construction or pair discovery;
- estimation policy, cointegration testing, or candidate acceptance;
- current signals, runtime pair ranking, capital slots, or entry eligibility;
- market-data acquisition or storage;
- order intents, routing, fills, positions, or reconciliation;
- CLI, Telegram, HTTP, or UI rendering;
- filesystem paths, object-store buckets, clocks, or operator identity sources.

Research decides which fitted models qualify as candidates. Pairs validates and
represents those results. An operator-controlled use case promotes a candidate.
Trading decides whether a promoted pair is currently eligible for a new entry.

### 2.3 Dependency direction

```text
research   -> pairs
trading    -> pairs
operations -> pairs lifecycle API
interfaces -> operations, never pair-set storage directly
pairs      -> core
```

Pairs imports neither Research nor Trading. Storage implementations satisfy a
Pairs-owned contract and receive their location through configuration or
explicit construction.

## 3. Conceptual Components

The module presents a small capability surface around these concepts:

- **Identity**: canonical unordered identity and explicit orientation.
- **Specification**: immutable fitted model, historical decision-policy
  contract, and sizing inputs.
- **Evidence**: research, temporal, economic, and stress evidence attached to a
  specification.
- **Pair set**: an exact, ordered collection with shared run provenance.
- **Lifecycle**: candidate validation, promotion, supersession, and retirement.
- **Integrity**: canonical representation, hashes, schema versions, and
  compatibility checks.
- **Store**: persistence and lookup without exposing backend layout to callers.

These are capabilities, not a mandatory one-file-per-concept layout.

### 3.1 Logical package shape

```text
pairs/
├── api.py
├── models.py
├── identity.py
├── specification.py
├── spread.py
└── artifacts/
    ├── models.py
    ├── validation.py
    ├── lifecycle.py
    ├── promotion.py
    └── stores/
        ├── memory.py
        ├── json_file.py
        └── object_store.py
```

The tree assigns stable homes without requiring every adapter or file to exist
at once. `identity.py` separates unordered identity from fitted orientation;
`specification.py` owns the immutable calibrated contract; and `spread.py`
evaluates the versioned fitted formula shared by Research and Trading without
owning estimation or signal policy.

The `artifacts` package keeps validation, lifecycle, promotion, and persistence
behind one cohesive interface. Backend files are adapters and are introduced
only for stores the product actually uses.

## 4. Public Interface

The public interface supports four workflows:

1. Build and validate a typed candidate pair set from Research output.
2. Persist and retrieve immutable pair-set versions.
3. Promote one exact candidate version through an explicit audited action.
4. Load the exact promoted version for a declared consumer scope.

Every workflow returns typed results with stable machine-readable error reasons.
The interface does not return unvalidated dictionaries or require callers to
construct paths.

Reading is side-effect free. Candidate publication and promotion are distinct
commands. Loading a candidate never promotes it, and loading a promoted pair set
never changes its lifecycle.

## 5. Pair Identity

A pair relates two canonical instrument identities. Its unordered identity is
independent of estimation orientation:

$$
\operatorname{pair\_id}(A,B) = \operatorname{pair\_id}(B,A).
$$

The identity uses complete canonical instruments, including venue-independent
market attributes needed to distinguish spot, linear swaps, inverse contracts,
settlement assets, or other economically different instruments. Display labels
are not identities.

Identity has a deterministic ordering rule and stable encoded form. It does not
depend on discovery order, filename sanitization, Python object hashes, or
locale-sensitive text ordering.

Duplicate unordered identities are invalid inside one pair set.

## 6. Orientation and Instrument Roles

A fitted pair specification declares an oriented dependent instrument $X$ and
hedge instrument $Y$. Orientation belongs to the fitted model:

$$
x_t = \log(P^X_t), \qquad y_t = \log(P^Y_t),
$$

$$
s_t = x_t - \alpha - \beta y_t.
$$

Reversing $X$ and $Y$ produces a different fitted model with different
coefficients and evidence, even though the unordered pair identity is the same.

Every calibrated value that depends on orientation is stored with that
orientation. No caller may infer roles from alphabetic ordering or a display
label. Artifact validation rejects missing, duplicated, or inconsistent roles.

Research may evaluate and preserve evidence for both orientations, but one pair
set contains at most one accepted fitted orientation for an unordered pair. If
both survive, Research's frozen ranking is lower BH-adjusted p-value, then more
negative ADF statistic, then canonical instrument ordering. Pairs validates the
single-orientation invariant; it does not recompute the ranking.

## 7. Calibrated Pair Specification

A pair specification is an immutable description of the model approved by
Research. It contains enough information to reproduce the spread and understand
the intended runtime policy without re-estimating parameters.

It includes:

- pair identity and fitted orientation;
- canonical instrument identities;
- price transformation and spread formula version;
- intercept $\alpha$ and hedge ratio $\beta$;
- formation and evaluation boundaries;
- estimator and deterministic-term conventions;
- stationarity method, lag policy, multiplicity family, and semantic versions;
- historical decision-policy method, normalization, and lookback;
- historical entry, exit, stop, and holding policies when approved;
- portfolio-weight or sizing-policy inputs;
- friction assumptions used for evidence;
- statistical and economic evidence references;
- warnings and limitations.

Trading consumes the immutable specification. It does not silently refit the
hedge ratio or select a different spread definition. A recalibrated model is a
new candidate specification and therefore a new pair-set version.

## 8. Evidence Contract

Evidence is structured, typed, and attributable to a stage and temporal window.
It distinguishes at least:

- formation evidence;
- validation and out-of-sample evidence;
- stationarity and multiple-testing evidence;
- parameter-stability evidence;
- backtest and friction evidence;
- stress evidence;
- warnings, rejection reasons, and known limitations.

Metric names carry units, sample sizes, window bounds, and calculation versions.
A p-value without its test convention, a Sharpe ratio without frequency and
friction assumptions, or a half-life without units is incomplete evidence.

The pair specification includes accepted evidence; the research report may
contain a richer diagnostic history. Pairs preserves rather than recomputes it.

Candidate evidence is incomplete unless it identifies the research run, code,
config, dataset, universe, information cutoff, temporal windows, exact fitted
model and formula, estimator and test versions, coefficients, orientation,
stationarity and FDR results, half-life units, historical decision/portfolio/
friction policies, validation and final-OOS outcomes, stress results, warnings,
limitations, and acceptance reason.

## 9. Pair-Set Contract

A pair set is an immutable aggregate containing:

- a stable pair-set id;
- schema and semantic-contract versions;
- lifecycle stage;
- exact ordered pair specifications;
- research run and code identities;
- generation time from an explicit clock;
- dataset and universe provenance;
- venue, market profile, and timeframe scope;
- information cutoff and all temporal boundaries;
- relevant configuration identity;
- warnings and limitations;
- content hash.

Candidate versions are both run-addressed and content-addressed. The run
identity preserves experimental history; the content hash proves semantic
identity. A mutable convenience pointer may identify the current candidate, but
it never replaces either immutable identity.

Ordering is deterministic and semantically defined. A pair count is derived and
validated against the collection, never accepted as an independent truth.

An empty candidate pair set is valid when Research completed successfully and
found no accepted pairs. It is distinct from a failed run or missing artifact.

## 10. Lifecycle

The lifecycle is explicit:

```text
CANDIDATE
-> PROMOTED
-> SUPERSEDED
-> RETIRED
```

- **Candidate**: immutable Research output awaiting review.
- **Promoted**: exact version authorized as the source for future entries.
- **Superseded**: formerly promoted version replaced by a newer promotion.
- **Retired**: version explicitly removed from future-entry eligibility.

Lifecycle stage does not alter artifact content. Transitions create immutable
audit events and update a scope-specific pointer atomically.

Promotion never mutates exchange state, closes positions, or rebalances a
portfolio. Replacing the promoted pointer affects only future entries. Trading
retains the specification needed for every open position until its natural exit
and reconciliation are complete.

## 11. Promotion

Promotion requires:

- an existing immutable candidate identity;
- full schema and integrity validation;
- compatible venue, market, timeframe, and consumer scope;
- acceptable freshness under an explicit promotion policy;
- an identified operator or authorized automation principal;
- a reason or review reference;
- an atomic compare-and-set against the expected current promoted version.

The promotion result identifies the previous and new versions. Concurrent or
stale promotion attempts fail rather than silently overwriting a newer decision.

Automatic research completion does not imply automatic promotion.

The initial consumer-scope vocabulary is strategy identity, canonical market
profile, and timeframe. Venue listing identity remains inside the instruments
and dataset provenance; deployment environment is a separate application axis,
not part of pair meaning. Extending this vocabulary is a semantic-contract
change. Promotion is outside the first Research vertical.

## 12. Promotion Audit

Every lifecycle transition records an append-only event containing:

- event id and event type;
- pair-set id and content hash;
- previous lifecycle state and new state;
- consumer scope;
- operator/principal identity;
- event time from an explicit clock;
- review reason and policy identity;
- expected and resulting promoted versions;
- software/schema version when available;
- outcome and failure reason.

Audit records reference immutable identities rather than relying only on paths.
They must be queryable without parsing application log messages.

## 13. Serialization

Serialization is deterministic. Semantically identical pair sets produce the
same canonical content and content hash, excluding lifecycle events stored
separately.

JSON is the default human-inspectable adapter for small pair sets. It uses:

- explicit schema versions;
- canonical field names and ordering;
- finite numeric values only;
- timezone-aware UTC timestamps;
- deterministic numeric and enum representations;
- strict read and write validation;
- canonical byte generation for hashing.

JSON is not the in-process interface. A database or object-store adapter may be
added without changing domain callers.

## 14. Storage

The storage contract separates immutable content from mutable lifecycle
pointers:

```text
immutable pair-set versions
        +
scope-specific promoted pointer
        +
append-only lifecycle audit
```

Stores provide atomic publication, collision-safe identities, integrity checks,
and explicit not-found/conflict errors. Reads never create directories or
repair data implicitly.

Filesystem, object storage, and database layouts are adapter details. A path is
not a pair-set id, and replacing a filename is not sufficient promotion audit.

## 15. Compatibility and Evolution

Schema version and semantic-contract version are separate:

- the schema version describes serialized structure;
- the semantic version describes meanings such as orientation, spread formula,
  units, and lifecycle rules.

Readers reject unknown incompatible major semantics. Compatible additive
changes are normalized into the current typed model through explicit adapters.
No permissive `extra=allow` behavior may hide an unknown trading-relevant field.

Compatibility transformations are deterministic, tested, and
provenance-preserving. They never fabricate missing quantitative evidence.

## 16. Runtime Consumption

Trading loads a promoted pair set by exact consumer scope and records its id and
hash at boot. Every opened position records the pair specification version it
uses.

A newer promoted version may govern future entries while existing positions
continue using their original specification. Runtime pair validity, ranking,
opportunity evidence, and capital-slot policy are Trading concerns and do not
modify the promoted artifact.

If the promoted pointer is missing, corrupt, incompatible, or changes
unexpectedly during a guarded load, entry evaluation fails closed.

## 17. Error Semantics

Errors distinguish:

- malformed or incompatible schema;
- invalid identity or orientation;
- duplicate pair identity;
- inconsistent fitted parameters or evidence;
- integrity/hash mismatch;
- missing candidate or promoted version;
- scope mismatch;
- stale candidate under promotion policy;
- lifecycle conflict;
- concurrent promotion conflict;
- storage unavailable or publication incomplete.

Errors preserve the exact pair-set id, scope, stage, and reason without leaking
credentials or backend internals unnecessarily.

## 18. Determinism and Testability

Behavior tests prove that:

- identity is stable and unordered while orientation remains explicit;
- fitted model round-trips preserve every trading-relevant value;
- duplicate and inconsistent specifications fail;
- canonical serialization and hashes are deterministic;
- failed candidate writes cannot appear valid;
- failed promotions preserve the previous promoted pointer;
- concurrent promotion conflicts are detected;
- promoted replacement affects future entries only;
- open-position specifications remain loadable after supersession;
- stores satisfy one shared contract without network access in unit tests.

## 19. Safety Invariants

- Pairs never calls an exchange.
- Candidate creation never authorizes trading.
- Promotion never creates, modifies, cancels, or closes an order or position.
- Pair recalculation never forces rebalancing.
- Runtime consumers fail closed on invalid, incompatible, or ambiguous content.
- Every trading-relevant pair value has explicit orientation, units, and
  provenance.
- A mutable pointer never replaces immutable history or its audit trail.
