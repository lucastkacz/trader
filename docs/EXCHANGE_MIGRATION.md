# Exchange Migration Guide

> **TEMPORARY DOCUMENT — DELETE AFTER MIGRATION.**
>
> This guide inventories the frozen Exchange implementation and sequences its
> replacement. Transfer accepted behavior to `docs/EXCHANGE.md` and delete this
> file only after readonly and mutation completion gates pass.

**Status:** source audit and migration planning; no Exchange production code
exists in the new namespace.

**Last reviewed:** 2026-07-18

## 1. Purpose and Authority

[`EXCHANGE.md`](EXCHANGE.md) is the permanent description of venue integration.
This guide owns provisional layout, source mapping, defects, implementation
slices, open questions, and verification gates.

Authority order is:

1. Lucas's explicit instruction for the current task.
2. `.agents/AGENTS.md` for durable implementation and safety rules.
3. `docs/_IMPLEMENTATION_AGENT_GUIDE.md` for route order and completion state.
4. The relevant canonical module documents for accepted behavior and ownership.
5. `docs/current-roadmap.md` for current status and near-term scope.
6. This guide for migration traceability, open decisions, slices, and gates.
7. Frozen tests as clues about intended V1 behavior.
8. Frozen implementation and config as clues about actual V1 behavior.

Reference source is the readonly worktree
`/Users/lucastkacz/Documents/quant-v1-reference` at tag
`legacy-v1-before-rewrite`. Never import or patch it from the new package.

## 2. Migration Phases

Exchange migration has two deliberately separated phases:

1. **Readonly integration:** market catalog, tickers, OHLCV, funding, public
   capabilities, and session lifecycle required by Market Data.
2. **Private execution integration:** account snapshots and order mutation,
   introduced only after Trading has paper fills, risk, intent, idempotency,
   reconciliation, and recovery contracts.

The second phase must not be scaffolded merely to make the package appear
complete. Physical paths and adapter names remain provisional until their
behavior slice is implemented.

## 3. Migration Actions

| Label | Meaning |
|---|---|
| `KEEP-CONCEPT` | Preserve the idea behind a corrected contract |
| `ADAPT` | Preserve behavior after fixing semantics or ownership |
| `SPLIT` | Separate capabilities or reasons to change |
| `MERGE` | Consolidate duplicated transport/session behavior |
| `MOVE-OWNER` | Keep behavior under another top-level module |
| `REPLACE` | Rebuild from the permanent contract |
| `DROP` | Do not migrate |
| `DEFER` | Keep outside the active phase |
| `OPEN` | Requires explicit user judgment |

## 4. Existing Flow

```text
venue YAML + market-profile YAML + credentials
-> CCXT client factory
-> market/ticker/OHLCV/funding translation
-> DataFrame or ticker models

live runtime config
-> CCXT account snapshot or order adapter
-> raw provider response normalization
-> trader lifecycle/state handling
```

Good concepts include strict venue profiles, configurable spot/linear/inverse
markets, async client closure, injected clients in tests, preserved native CCXT
symbols, funding capability checks, readonly account snapshots, client order
ids, and explicit order submission/status/cancel operations.

The main correction is to make capabilities narrow and one-directional:
Exchange implements canonical Market Data or Trading contracts; those modules
do not import Exchange-owned domain types.

## 5. Source Inventory: Configuration

| Source | Existing behavior | Action | Required correction |
|---|---|---|---|
| `src/exchange/config/venue.py` | Strict venue and CCXT market-profile config, client kwargs, raw market matching | `SPLIT` + `ADAPT` | Keep provider config inside adapter; separate canonical market profile, secret input, capability authority, and raw payload parsing |
| `src/exchange/config/__init__.py` | Empty/broad package surface | `DROP` or narrow | Expose only implemented adapter construction behavior |

Config files:

| Source | Evidence | Action |
|---|---|---|
| `configs/exchange/market_profiles/spot.yml` | Spot CCXT options | Preserve as profile evidence |
| `configs/exchange/market_profiles/linear_usdt_swap.yml` | Linear USDT settlement | Candidate first derivative profile |
| `configs/exchange/market_profiles/linear_usdc_swap.yml` | Linear USDC settlement | `DEFER` until needed |
| `configs/exchange/market_profiles/inverse_coin_swap.yml` | Inverse contracts with variable settle | `DEFER`; requires explicit unit/contract tests |
| `configs/exchange/venues/dev.yml`, `uat.yml`, `prod.yml` | Venue and `readonly`/`live` credential tier | `REPLACE`; environment name and credential authority must not imply execution authorization |

`credential_tier: live` conflates what a key can do with what the process is
authorized to do. Secrets should expose scoped capabilities; application wiring
must separately authorize any mutation adapter.

## 6. Source Inventory: Readonly Data

| Source | Existing behavior | Action | Required correction |
|---|---|---|---|
| `src/exchange/data/ccxt_adapter.py` | Context-managed CCXT readonly facade, optional injected client | `ADAPT` | Implement Market Data source contract; avoid storing unnecessary secret copies; explicit public access; stable session ownership |
| `src/exchange/data/market_data.py` | Client factory, market/ticker filtering, OHLCV and funding normalization, logging | `SPLIT` + `REPLACE` | Separate session construction, native market mapping, observation translation, and error mapping; remove Research-specific logging |
| `src/exchange/data/__init__.py` | Empty package export | `DROP` or narrow | Export only capability-specific adapter interface |

### Readonly defects

1. Exchange defines `MarketTicker`, while Market Data sync imports it; Exchange
   also imports Data normalization, creating ownership inversion.
2. Missing `quoteVolume` becomes zero, losing the difference between absent and
   observed zero.
3. Market matching operates on permissive raw dictionaries inside config models.
4. Error behavior is inconsistent: some network errors become generic
   `RuntimeError`, others leak provider exceptions, and causes are not always
   preserved.
5. The adapter hardcodes a Research-specific `UNIVERSE_SCAN` log context.
6. Funding normalization drops malformed rows without complete rejection
   evidence.
7. Capability checks use raw provider dictionaries and untyped operation names.
8. Pagination semantics are split between Exchange and Data sync without one
   explicit page contract.

## 7. Source Inventory: Account Reads

| Source | Existing behavior | Action | Required correction |
|---|---|---|---|
| `src/exchange/execution/account.py` | CCXT position snapshot, zero filtering, normalized side, guaranteed close | `ADAPT` + `DEFER` | Trading-facing canonical account facts, explicit quantity units/contract size, strict payload evidence, no local spread id |

Useful behavior to preserve:

- account snapshot is readonly;
- non-zero rows missing side fail explicitly;
- owned client closes after success or failure;
- tests inject a fake factory.

Corrections:

- permissive extra fields can hide provider schema changes;
- `contracts` is copied to `qty` without contract multiplier or unit semantics;
- normalized side accepts arbitrary strings rather than a closed domain result;
- local `spread_id` does not belong in a venue snapshot;
- balances and open orders are absent from reconciliation evidence;
- a new CCXT client is constructed for each snapshot.

## 8. Source Inventory: Order Mutation

| Source | Existing behavior | Action | Required correction |
|---|---|---|---|
| `src/exchange/execution/orders.py` | Submit market order, status lookup, cancellation, precision helper, client id | `REPLACE` + `DEFER` | Wait for Trading contracts; validate canonical request, market limits, units, reduce-only/position mode, errors, ambiguous outcomes, session reuse |
| `src/exchange/execution/__init__.py` | Empty package surface | `DROP` or narrow | Mutation interface only when explicitly authorized |

The deterministic scanner labels mutation terms in this file as blockers, but
their location is correct: it is the explicit Exchange execution adapter. The
real blockers are behavioral:

- order request fields lack strong side/type/unit/positive-quantity validation;
- only `amount_to_precision` is applied; minimum notional, amount limits,
  contract size, and rounding exposure are not validated;
- derivative symbol translation is a no-op;
- reduce-only, position side, margin mode, time-in-force, and price/trigger
  semantics are absent;
- raw order statuses are strings with an unsafe default of `open`;
- provider rejection is not consistently translated to `OrderRejected`;
- transport timeout after submission has no ambiguous-outcome state;
- retry safety is delegated without a lookup-by-client-id contract;
- a new authenticated client is opened and closed for every operation;
- returned fees and requested-versus-submitted values are absent.

Do not port this adapter before the paper Trading lifecycle proves the required
canonical intent and reconciliation interface.

## 9. Caller and Ownership Inventory

| Caller group | Existing coupling | Migration direction |
|---|---|---|
| `src/data/sync/` | Imports Exchange ticker/source types | Reverse: Exchange implements Market Data contracts |
| `src/universe/` | Imports Exchange ticker and concrete adapter | Research consumes canonical market facts supplied by application wiring |
| `src/pipeline/master_flow.py` | Constructs config, CCXT, storage, Research | Replace with application composition outside domain modules |
| `src/engine/trader/execution/market_data.py` | Wraps Exchange data adapter | Trading consumes Market Data interface; remove pass-through facade |
| `src/engine/trader/execution/orders.py` | Drives polling/cancel/state over Exchange gateway | Keep lifecycle in Trading; gateway stays narrow |
| `src/engine/trader/reconciliation/service.py` | Consumes account snapshots | Preserve readonly seam with richer canonical facts |
| runtime runner/tick/signal transition | Constructs or passes concrete adapters | Application constructs capabilities; Trading receives only authorized interfaces |

## 10. Test Inventory

| Source | Useful evidence | Migration rule |
|---|---|---|
| `tests/exchange/config/test_venue.py` | shipped profile parsing and strict config | Rebuild around selected profiles and application config boundary |
| `tests/exchange/data/test_exchange_market_data.py` | market filtering, symbol preservation, bounds, injected ownership, funding normalization/errors | Split into focused adapter contract tests using payload fixtures |
| `tests/exchange/execution/test_account.py` | position normalization and reliable close | Preserve when private readonly phase begins; add units/capabilities |
| `tests/engine/trader/execution/test_orders.py` | no-mutation mode, ids, polling, partial/cancel/reject lifecycle | Trading tests own lifecycle; Exchange tests own only request/response translation |
| `tests/exchange/data/test_live_market_data.py` | Bybit connectivity | `DEFER`; explicit probe, no ordinary synchronous network calls |
| `tests/exchange/data/test_live_multi_symbol_funding_probe.py` | multi-symbol funding history | `DEFER`; bounded opt-in probe |
| `tests/exchange/data/test_live_selected_ohlcv_probe.py` | selected OHLCV access | `DEFER`; contract already proven offline |
| `tests/exchange/data/test_live_universe_probe.py` | end-to-end universe filtering | `MOVE-OWNER`; Research acceptance plus optional Exchange connectivity probe |

The 419-line data test is a cohesion signal: split by capability and test
observable adapter contracts, not helper functions.

## 11. Quality Audit Findings

### High

- **Capability ambiguity:** readonly/live credential tiers do not enforce which
  adapter can be constructed.
- **Dependency inversion:** canonical ticker/data types are Exchange-owned and
  imported backward by Market Data and Research.
- **Mutation ambiguity:** a submission timeout cannot distinguish not-sent from
  accepted-but-unacknowledged; blind retry could duplicate an order.
- **Unit/limit gap:** order amounts and account quantities lack complete contract
  units and venue-limit validation.

### Medium

- the 248-line data module mixes factory, translation, provider parsing,
  observability, and error policy;
- sessions are repeatedly constructed and secrets retained on adapter objects;
- raw strings/permissive models can hide provider schema drift;
- provider exceptions are normalized inconsistently;
- live probes are long and network/state dependent;
- config-specific market matching and adapter translation are mixed.

## 12. Implementation Slices

Target names are working hypotheses, not a required package tree.

### EX0 — Resolve venue semantics

Choose first venue/library/market profile, canonical symbol mapping, public
versus authenticated reads, capability model, error taxonomy, and session
ownership.

**Gate:** representative native market/ticker/OHLCV/funding payloads map
unambiguously to Market Data contracts on paper.

### EX1 — Provider-independent adapter contract tests

Build payload fixtures and behavior tests for capabilities, market mapping,
missing fields, bounds, errors, and session closure before network integration.

**Gate:** no test imports Research or calls a network; raw payloads cannot leave
the adapter.

### EX2 — Readonly market-data adapter

Implement the minimum provider adapter needed by the Market Data source
contract. Support market catalog and bounded OHLCV first; add tickers/funding
only when consumers require them.

**Gate:** local fixture acceptance passes through Market Data normalization and
provenance with stable symbol identity and no credentials when endpoints permit.

### EX3 — Explicit live probes

Add bounded, opt-in connectivity probes with readonly credentials, redacted
output, timeouts, and no storage mutation unless the probe explicitly owns a
temporary target.

**Gate:** probes are excluded from default CI and cannot reach order endpoints.

### EX4 — Private readonly account adapter

After Trading defines reconciliation facts, implement positions, balances, and
open-order snapshots with units and strict malformed-payload outcomes.

**Gate:** boot reconciliation can use a fake and adapter fixture interchangeably;
snapshot failure remains readonly and fail-closed.

### EX5 — Order mutation gateway

Only after paper Trading and readiness prerequisites, implement canonical order
translation, capabilities, precision/limits, client-id lookup, ambiguous
outcomes, status, and cancellation.

**Gate:** offline contract tests prove idempotency, partial fills, rejection,
timeout ambiguity, lookup-before-retry, reduce-only, position mode, and rounding.

### EX6 — Demo adapter verification

Exercise testnet/demo with separately scoped credentials and recovery drills.
This validates integration, not alpha or production readiness.

### EX7 — Consolidate

Remove speculative scaffolding and compatibility paths, reconcile permanent
docs/roadmap, and delete this guide only after both readonly and mutation phases
are complete.

## 13. Questions for Lucas

| ID | Question | Why it matters | Recommended starting answer |
|---|---|---|---|
| `EXQ-001` | Is Bybit still the first venue? | Determines payload fixtures and capability gaps | Yes for one readonly adapter, without claiming multi-venue support |
| `EXQ-002` | Which first market profile: spot or linear USDT perpetual? | Changes identity, funding, units, and later orders | Match the Research decision; avoid implementing both initially |
| `EXQ-003` | Keep CCXT as the integration library? | Affects portability and error/precision behavior | Yes initially behind a narrow adapter; replace only with measured reason |
| `EXQ-004` | Should public endpoints run without credentials? | Reduces secret exposure | Yes whenever the venue supports it |
| `EXQ-005` | What canonical/native symbol mapping is authoritative? | Prevents suffix invention and storage collisions | Derive from loaded market metadata and preserve both identities |
| `EXQ-006` | Who owns retry policy for reads? | Avoids duplicated retry loops | Market Data owns bounded acquisition policy; Exchange classifies provider errors and honors rate limits |
| `EXQ-007` | How long should sessions live? | Impacts rate limits, secrets, and performance | One owned session per bounded workflow, reusable within it |
| `EXQ-008` | Which account facts are required for reconciliation? | Avoids shallow snapshot models | Positions, balances, open orders, units, margin/position mode |
| `EXQ-009` | Which order types are initially supported? | Controls mutation surface | Market orders only for demo, but model reduce-only and position side explicitly |
| `EXQ-010` | One-way or hedge position mode? | Side and reduce-only semantics differ | Choose one venue/account mode and fail if observed mode differs |
| `EXQ-011` | What client-order-id format and lookup capability exist? | Central to idempotent recovery | Durable intent-derived id within venue limits |
| `EXQ-012` | Can an ambiguous submission ever auto-retry? | Duplicate-order risk | No; lookup/reconcile first |
| `EXQ-013` | Who owns leverage/margin changes? | These are dangerous account mutations | Separate explicit operator workflow, not ordinary order adapter |
| `EXQ-014` | When may private/live credentials enter the project? | Safety and secret management | Only after paper gates and immediately before the relevant demo slice |

## 14. Scope Exclusions During Readonly Phase

- order submission or cancellation;
- private account reads unless required by Research, which they are not;
- live credentials, leverage, margin, or position-mode mutation;
- multi-venue abstraction beyond one proven adapter;
- direct provider SDK alongside CCXT without measured need;
- Trading lifecycle, risk, reconciliation, or paper fills;
- Research filtering or Market Data storage policy.

## 15. Readonly Completion Gates

- [ ] Exchange implements Market Data contracts without ownership cycles.
- [ ] Native and canonical market identity round-trip unambiguously.
- [ ] Missing facts remain missing rather than becoming zero/default values.
- [ ] Capabilities and unsupported operations are typed and observable.
- [ ] Session ownership and closure are deterministic.
- [ ] Provider errors preserve category, cause, retryability, and redacted
  context.
- [ ] Public reads do not require placeholder secrets.
- [ ] Offline payload/adapter contract tests pass without network.
- [ ] Live probes are bounded, readonly, opt-in, and separate.

## 16. Mutation Completion Gates

- [ ] Readonly credentials cannot construct a mutation capability.
- [ ] Application execution authorization is separate from credential scope.
- [ ] Canonical orders include units, client id, reduce-only, position side, and
  supported type semantics.
- [ ] Precision, contract size, amount, and notional limits validate before send.
- [ ] Requested and submitted values remain auditable.
- [ ] Rejection, partial fill, cancellation, not-found, and ambiguous outcomes
  remain distinct.
- [ ] Ambiguous submission triggers lookup/reconciliation before any retry.
- [ ] Trading owns polling, multi-leg handling, compensation, state, and risk.
- [ ] Account snapshots carry complete units and no local strategy identity.
- [ ] Demo recovery drills pass before any real-capital consideration.
- [ ] Every production-readiness gate remains separately required.

After both checklists pass, transfer accepted contracts and tested operator
guidance to permanent docs, remove references to this file, and delete it.
