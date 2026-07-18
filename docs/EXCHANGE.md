# Exchange Module

## 1. Purpose

The Exchange module is the anti-corruption layer between the platform and
external trading venues. It translates venue-specific protocols, symbols,
capabilities, payloads, precision rules, errors, and credentials into the
canonical contracts consumed by Market Data and Trading.

Its central question is:

> How does the platform communicate with this venue without allowing
> venue-specific details or unsafe mutation behavior to leak into domain logic?

Exchange performs translation and transport. It does not decide which markets
to research, when to trade, how much risk to take, or how a portfolio lifecycle
should evolve.

## 2. Responsibilities and Boundaries

### 2.1 Exchange owns

- venue profiles, capabilities, and session construction;
- native-market discovery and canonical symbol mapping;
- translation of readonly market observations into Market Data contracts;
- translation of readonly account facts into Trading-facing snapshots;
- precision, limits, contract units, and venue-required order parameters;
- explicit order submission, status lookup, and cancellation adapters;
- normalized provider errors and ambiguous-outcome semantics;
- credential capability enforcement and client lifecycle;
- rate-limit and venue-specific transport behavior;
- redacted, correlation-aware exchange observability.

### 2.2 Exchange does not own

- canonical candle, funding, dataset, or continuity policy;
- research universe filters, cointegration, or candidate acceptance;
- signal generation, portfolio sizing, or pre-trade risk approval;
- order-intent lifecycle, multi-leg compensation, or reconciliation policy;
- paper fills or simulated brokerage behavior;
- promotion, scheduling, UI, Telegram, or operator authorization workflows;
- secret storage as a domain concern.

Market Data owns observation meaning. Trading owns intents, risk, state,
reconciliation, and the decision to invoke a mutation capability. Exchange owns
the exact translation of an approved request to and from a venue.

### 2.3 Dependency direction

```text
Market Data contracts <----- readonly exchange adapter -----> venue API

Trading contracts     <----- account/order adapters --------> venue API

Research -X-> exchange adapters
Exchange -X-> Research policy
Exchange -X-> Trading decision logic or state
```

Application wiring selects a concrete venue adapter. Domain modules do not
construct CCXT clients or parse provider dictionaries.

## 3. Components

Exchange is organized around external capabilities rather than predetermined
files or one large exchange client.

| Capability | Responsibility |
|---|---|
| Venue profile | Identify venue, market family, settlement, contract behavior, and supported operations |
| Capability discovery | Make supported and unsupported provider operations explicit |
| Session lifecycle | Construct, own, reuse, and close authenticated or public clients safely |
| Market translation | Map native markets, tickers, candles, and funding to canonical observations |
| Symbol mapping | Preserve reversible native/canonical identity and contract units |
| Account snapshots | Normalize balances, positions, and open orders without mutation |
| Order gateway | Translate approved submissions, status requests, and cancellations |
| Precision and limits | Apply amount, price, notional, and contract constraints before transport |
| Error translation | Classify network, rate-limit, auth, rejection, unsupported, and ambiguous outcomes |
| Observability | Record redacted request identity, latency, provider identifiers, and outcomes |

Readonly data access, private account reads, and order mutation are separate
capabilities. Sharing transport internals does not require exposing one broad
interface to every caller.

### 3.1 Logical package shape

```text
exchange/
├── config.py
├── models.py
├── capabilities.py
└── adapters/
    └── ccxt/
        ├── session.py
        ├── mapping.py
        ├── market_data.py
        ├── account.py
        └── orders.py
```

Exchange is organized as an adapter collection rather than one application
API. `config.py`, `models.py`, and `capabilities.py` describe venue profiles and
supported behavior. Provider-library details remain under `adapters`; another
native provider receives a sibling package instead of leaking conditionals
through domain callers.

Session ownership and native/canonical mapping are shared provider mechanics.
Readonly public data, authenticated account reads, and order mutation remain
separate files and injected capabilities even when they reuse the same session.

## 4. Venue and Market Profiles

A venue profile identifies the provider and the market family being accessed.
It records or resolves:

- venue identity;
- spot, future, option, or swap market type;
- linear or inverse behavior;
- quote and settlement assets;
- contract multiplier and amount units;
- position mode and margin capabilities;
- supported market-data and order operations;
- rate limits and provider-specific transport options.

A market profile is not an environment and does not authorize trading. The same
market family can be used with public data, readonly private access, paper
execution, testnet, or live execution through different application wiring and
credentials.

Provider-library configuration remains inside Exchange. Canonical callers do
not know concepts such as CCXT `defaultType`, `fetchMarkets`, or raw `has`
dictionaries.

## 5. Capabilities and Credential Authority

Capabilities are explicit and least-privileged:

- public market reads;
- authenticated readonly market/account reads;
- order submission;
- order cancellation;
- account configuration changes when separately supported.

Credential authority and runtime execution mode are different concepts.
Credentials describe what the venue will permit; application policy describes
what the process is allowed to attempt.

A readonly flow cannot obtain an order-mutation interface. Constructing a
mutation-capable adapter requires both appropriately scoped credentials and an
explicit execution authorization outside Exchange.

Secrets enter at session construction, are never included in models, logs,
exceptions, reports, or persisted config, and are retained only as long as the
owned session requires them. Public endpoints do not require placeholder API
keys.

## 6. Session Lifecycle

The owner of a provider session is explicit. An adapter either owns and closes
the session or receives a caller-owned session and leaves it open.

Sessions close reliably after success, failure, timeout, and cancellation.
Imports and object inspection do not create sessions or contact the network.

Connection reuse is bounded and intentional. Read paths may reuse a session for
pagination or batches. Mutation paths preserve enough session and request
context to resolve ambiguous outcomes without blindly resubmitting.

Time synchronization, receive windows, proxy settings, and provider-specific
transport options are validated configuration at the Exchange boundary.

## 7. Native and Canonical Symbol Mapping

Exchange preserves both canonical and native identities. Mapping accounts for:

- base, quote, and settlement assets;
- market type and expiry;
- linear or inverse contracts;
- contract multiplier and lot unit;
- provider-specific aliases and symbols.

Mapping is explicit, reversible, and based on loaded market metadata. Exchange
does not invent derivative suffixes, strip settlement information, or rebuild a
native symbol from a display pair.

All responses are verified against the requested market identity. A provider
symbol that maps ambiguously or changes meaning fails explicitly.

## 8. Readonly Market-Data Adapter

The readonly adapter exposes source capabilities required by Market Data,
including applicable subsets of:

- market catalog and active status;
- ticker and volume facts;
- bounded OHLCV windows;
- funding history and settlement information;
- provider time and market capabilities.

It returns canonical Market Data values, never provider dictionaries or
untyped DataFrames whose meaning depends on CCXT columns.

The adapter preserves request bounds and reports provider pagination behavior.
It does not decide universe eligibility, data retention, gap acceptance, or
research freshness thresholds.

Missing provider fields remain missing. A missing quote volume is not converted
to zero, and unsupported funding history is distinct from an empty valid
history.

## 9. Readonly Account Snapshots

Private readonly adapters expose normalized venue facts needed for boot and
reconciliation, such as:

- non-zero positions with canonical symbol, side, amount, and units;
- balances by asset and account context;
- open orders with provider and client identifiers;
- margin, leverage, and position-mode facts where available.

Snapshots contain venue facts only. They do not include local spread ids,
strategy labels, inferred ownership, or reconciliation decisions.

Quantities record whether they represent contracts, base units, quote notional,
or another provider unit. Trading performs comparison and reconciliation using
the canonical contract multiplier and entry-time state.

Malformed non-zero positions are rejected as incomplete account evidence rather
than silently skipped. Zero positions may be omitted under an explicit snapshot
contract.

## 10. Order Mutation Gateway

The order gateway accepts an already-approved canonical request containing:

- canonical and resolved native market identity;
- side and order type;
- amount with explicit unit;
- price or trigger information where required;
- time-in-force and post/reduce-only intent;
- position-side or hedge-mode parameters where applicable;
- a stable client order id and correlation identity.

Exchange applies provider precision and validates market limits before sending.
Rounding cannot increase exposure beyond the approved amount. A rounded amount
below the venue minimum is rejected locally with structured evidence.

The gateway returns provider order identity, normalized state, executed amount,
average price, fees when available, and raw-response provenance or a redacted
reference.

Exchange does not poll until a strategy outcome is achieved, decide whether a
partial fill is acceptable, submit the second leg, compensate an imbalance, or
update portfolio state. Those are Trading lifecycle responsibilities.

## 11. Idempotency and Ambiguous Outcomes

Every mutation carries a stable client order id derived outside the adapter from
a durable intent. Repeating the same intent uses the same id.

An error before provider acknowledgement, a provider rejection, and an unknown
outcome after transport timeout are different results. The last case is
ambiguous: the order may exist.

Exchange never automatically resubmits an ambiguous mutation. It first queries
by client id or provider order id. If the venue cannot resolve the outcome, the
result remains ambiguous and Trading fails closed until reconciliation.

Cancellation is also idempotent. Already-filled, already-cancelled, missing, and
unknown outcomes remain distinguishable.

## 12. Precision, Limits, and Contract Units

Before mutation, Exchange obtains authoritative market metadata and enforces:

- amount and price precision;
- minimum and maximum amount;
- minimum and maximum notional;
- contract size and integer-contract requirements;
- supported order types and time-in-force values;
- reduce-only and position-mode constraints;
- market status.

Precision formatting alone is not validation. Provider helpers that round a
number do not prove the result satisfies limits or matches the intended unit.

The normalized result records both requested and submitted values so any
rounding is auditable.

## 13. Error Semantics

Provider exceptions are translated into a stable taxonomy:

- network unavailable;
- timeout before request transmission;
- rate limited;
- authentication failed;
- permission denied;
- unsupported capability;
- invalid canonical request;
- provider rejected;
- market closed or unavailable;
- order not found;
- ambiguous mutation outcome;
- malformed provider response;
- unexpected adapter failure.

The normalized error preserves the original exception as its cause and includes
redacted venue, operation, market, retryability, and correlation context.

Readonly transient requests may be retried with bounded policy. Mutation retry
depends on acknowledgement state and idempotent lookup, never only on exception
type.

## 14. Rate Limits and Concurrency

Exchange respects provider weight, endpoint, and market-specific limits. Rate
limiting is shared across sessions when required by the venue rather than
assumed safe per object.

Concurrency is bounded by configured capability and provider constraints.
Cancellation propagates cleanly and closes only sessions owned by the cancelled
operation.

Batch operations preserve stable caller-visible ordering while recording actual
request timing separately.

## 15. Configuration

Configuration is typed, strict, and separated by concern:

- venue identity and endpoint/testnet selection;
- market profile and contract semantics;
- provider-library transport options;
- capability and rate-limit settings;
- session timeouts;
- public versus authenticated access.

Secrets are supplied separately from non-secret configuration. Raw YAML and
environment variables do not reach adapter behavior.

Exchange configuration does not contain strategy thresholds, capital sizing,
research universe policy, database paths, or UI settings.

## 16. Observability and Audit

Exchange records:

- venue and operation;
- canonical and native market identities;
- correlation and client order ids;
- start/end time and latency;
- normalized outcome and retryability;
- provider order id when acknowledged;
- requested versus submitted precision values;
- session ownership and close failures when relevant.

Logs and metrics redact credentials, signatures, sensitive headers, and raw
account payloads. Research-specific labels such as “universe scan” are supplied
by callers as context and are not hardcoded by the adapter.

## 17. Determinism and Testability

Translation of a fixed provider payload is deterministic. Provider clients,
clocks, and sleeps enter through explicit seams so behavior tests can use local
fakes without network access.

Contract tests cover canonical mapping, missing fields, capabilities, precision,
limits, error translation, session ownership, and ambiguous outcomes. Live
probes are explicitly selected, use separately scoped credentials, and never run
as part of the default offline suite.

## 18. Safety Invariants

- Research never receives an order-mutation capability.
- Readonly acquisition cannot construct or reach a mutation adapter.
- Public and readonly workflows do not require live credentials.
- Merely naming an environment `prod` does not authorize exchange mutation.
- Every mutation originates from a durable, risk-approved Trading intent.
- Unknown submission outcomes are reconciled before any retry.
- Provider precision never substitutes for pre-trade risk validation.
- Account snapshots are readonly and do not repair local state.
- Imports, config loading, reports, and tests cannot mutate a venue.
- Secrets never appear in logs, artifacts, exceptions, or persisted config.
- Exchange adapter existence is not evidence of real-capital readiness.
