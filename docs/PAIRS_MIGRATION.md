# Pairs Migration Guide

> **TEMPORARY DOCUMENT**
>
> This guide maps the frozen implementation into the Pairs module. It records
> provisional implementation choices, open questions, and completion gates. It
> is deleted after migration; accepted behavior remains in `docs/PAIRS.md`.

## 1. Purpose and Authority

The frozen source is available at tag `legacy-v1-before-rewrite` and in
`/Users/lucastkacz/Documents/quant-v1-reference`. It is evidence, not an API or
compatibility target.

Authority order:

1. Lucas's explicit instruction for the current task.
2. `.agents/AGENTS.md` for durable implementation and safety rules.
3. `docs/_IMPLEMENTATION_AGENT_GUIDE.md` for route order and completion state.
4. `ARCHITECTURE_REFACTOR.md` and the relevant canonical module documents.
5. `docs/current-roadmap.md` for current status and near-term scope.
6. This guide for migration traceability, open decisions, slices, and gates.
7. Frozen tests as clues about intended V1 behavior.
8. Frozen implementation and config as clues about actual V1 behavior.

The physical target remains provisional. Create only files justified by an
implemented vertical and avoid compatibility facades.

Path convention: abbreviated `runtime/`, `reporting/`, `signals/`, and `cli/`
source paths are relative to `src/engine/trader/`; abbreviated `runtime/`,
`signals/`, `trader/`, and `interfaces/` test paths are relative to
`tests/engine/trader/` or `tests/` as named by the table.

## 2. Working Capability Map

```text
pairs
├── identity and orientation
├── calibrated specification
├── candidate/promoted pair sets
├── schema, compatibility, and integrity
├── lifecycle and promotion audit
└── storage adapters
```

This map does not require one file or subpackage per line.

## 3. Migration Actions

- **KEEP**: behavior remains correct with focused tests.
- **ADAPT**: retain intent but change contract or ownership.
- **SPLIT**: separate mixed responsibilities.
- **MERGE**: combine shallow or duplicated behavior.
- **MOVE**: retain behavior under a different concept owner.
- **REPLACE**: intent remains but implementation is unsuitable.
- **DROP**: remove obsolete or unsafe behavior.
- **DEFER**: postpone until its consumer milestone.
- **OPEN**: requires an explicit decision.

## 4. Existing Flow

The frozen implementation approximately performs:

```text
research rows
-> permissive row validation
-> candidate JSON at a timeframe-derived path
-> age/scope validation
-> atomic rename to a promoted filename
-> JSONL promotion audit
-> runtime load and Sharpe filtering
```

Pair identity, fitted-model semantics, artifact lifecycle, runtime filtering,
filesystem layout, and operator policy are mixed under
`engine/trader/runtime/artifacts`. The useful candidate/promoted separation is
present, but the contract is too weak for an auditable research-to-trading
handoff.

## 5. Source Inventory: Pair Mathematics and Identity

| Frozen source | Evidence | Action | Destination concept |
|---|---|---|---|
| `src/engine/analysis/spread_math.py` | Positive log prices, hedged log spread, rolling z-score | SPLIT | Research owns estimation/math; Pairs owns formula version and fitted representation |
| `src/engine/analysis/cointegration.py` | Produces oriented hedge ratio and diagnostics | MOVE | Research; output converted to typed pair specification |
| `src/universe/pairs.py` | Pair candidates from clusters | MOVE | Research discovery; canonical unordered identity from Pairs |
| `src/universe/discovery.py` | Writes pair rows and fitted values | SPLIT | Research produces typed results; Pairs validates aggregate |
| `src/research/pair_baseline.py` | Baseline fields and performance evidence | MOVE | Research; normalized into Pairs evidence contract |
| `src/research/pair_stress_filter.py` | Produces surviving rows | MOVE | Research candidate acceptance; no direct JSON row mutation |

No frozen type provides a complete unordered identity distinct from fitted
orientation. Pair labels are assembled from strings and used as database keys,
display labels, and artifact identity. V2 must replace that ambiguity.

## 6. Source Inventory: Artifact Contract

| Frozen source | Evidence | Action | Reason |
|---|---|---|---|
| `runtime/artifacts/contract.py` | Strict envelope, metadata scope, age check, pair-count check | ADAPT | Good fail-loud shape; metadata and provenance are incomplete |
| `runtime/artifacts/rows.py` | Validates minimum nested fields | REPLACE | Aliased title-case JSON and `extra="allow"` can hide semantic drift |
| `runtime/artifacts/loading.py` | Loads promoted file and filters by Sharpe | SPLIT | Load belongs Pairs; runtime eligibility threshold belongs Trading |
| `runtime/artifacts/__init__.py` | Broad re-export facade | DROP | Canonical owning imports should be direct and small |
| `runtime/pair_validity/artifact.py` | Reads research baseline fields from rows | SPLIT | Typed specification eliminates ad-hoc optional dictionary parsing |
| `runtime/pair_validity/statistics.py` | Re-estimates recent diagnostics | MOVE | Trading runtime validity; it must reference immutable Pairs parameters |

The existing envelope records schema version, generated time, timeframe,
exchange, and count. It omits run id, dataset/universe identity, information
cutoff, orientation semantics, intercept, estimator contract, multiplicity,
code/config identity, complete validation evidence, lifecycle id, and content
hash.

## 7. Source Inventory: Lifecycle and Promotion

| Frozen source | Evidence | Action | Reason |
|---|---|---|---|
| `runtime/artifacts/lifecycle.py` | Candidate/promoted separation, temp write, atomic replace, freshness validation | ADAPT | Preserve intent; remove hardcoded names/path layout and candidate move semantics |
| `runtime/artifacts/promotion_audit.py` | SHA-256 and append-only JSONL event | ADAPT | Record immutable ids, CAS conflict, previous version, principal, and outcome |
| `engine/trader/cli/promote_pairs.py` | Explicit operator command | SPLIT | Use case in Operations; parsing/rendering in Interfaces; domain transition in Pairs |
| `runtime/artifacts/loading.py` | Promoted lookup by timeframe path | REPLACE | Lookup by typed scope and pointer, not constructed filename |

The frozen promotion moves the candidate file into the promoted path. That
destroys the candidate location as an immutable historical reference and treats
a path as identity. V2 stores immutable content once and moves only a validated
pointer.

Promotion audit is optional in the frozen call. It must be inseparable from a
successful lifecycle transition.

## 8. Caller Inventory and Ownership Corrections

| Frozen caller | Current use | Target owner |
|---|---|---|
| `pipeline/master_flow.py` | Resolves candidate paths | Research API returns candidate identity; Operations wires store |
| `engine/trader/runtime/trader_runner.py` | Loads and filters promoted rows | Trading loads exact promoted set through Pairs API |
| `runtime/pair_queue/ranking.py` | Reads Sharpe, identity, validity evidence | Trading consumes typed specification and its own runtime diagnostics |
| `runtime/pair_validity/*` | Parses optional baseline keys and artifact time | Trading validity receives typed Pairs values |
| `reporting/backtest_lookup.py` | Reopens JSON and extracts performance | Reporting uses Trading/Pairs read model |
| `interfaces/telegram/handlers/pairs.py` | Reads artifact file directly | Interface calls an Operations query |
| `interfaces/telegram/rendering/pairs.py` | Understands legacy row shape | Renderer consumes a delivery DTO |
| `cli/report_generator.py` | Passes artifact path into report assembly | Operations resolves scope; report receives typed snapshot |

No delivery adapter should know the pair-set storage path or legacy JSON field
shape.

## 9. Configuration Inventory

| Frozen config | Relevant fields | Action |
|---|---|---|
| `configs/pipelines/*.yml` | `artifact_base_dir`, `min_sharpe`, pair refresh policy | SPLIT into store wiring, Trading eligibility, and lifecycle policy |
| `configs/runs/*.yml` | Indirect pipeline selection | MOVE to application composition only if a real entrypoint needs profiles |
| `configs/telegram/*.yml` | `promoted_pairs_path` | DROP; interfaces query by typed consumer scope |

Artifact paths must not appear in quantitative, Trading, or interface config.
Freshness at Research review, promotion, and Trading boot are different policies
and must not share one hidden default.

## 10. Test Inventory

| Frozen tests | Useful behavior | Action |
|---|---|---|
| `runtime/test_pairs.py` | Envelope rejection, count and scope validation | ADAPT to typed pair set and strict schema |
| `runtime/test_pair_artifact_lifecycle.py` | Candidate does not replace promoted; invalid promotion preserves current | KEEP intent and strengthen with immutable versions/CAS |
| `trader/test_promote_pairs.py` | Explicit command and audit record | SPLIT into Pairs lifecycle, Operations use case, CLI contract tests |
| `signals/test_spread_math_alignment.py` | Same spread across paths | KEEP as cross-module contract test |
| `runtime/test_pair_validity.py` | Baseline fields feed diagnostics | MOVE to Trading with typed specification fixture |
| `runtime/test_pair_queue.py` | Promoted pairs feed future-entry queue | MOVE to Trading |
| `interfaces/telegram/test_daemon.py` | Promoted-pair view | REPLACE with delivery contract test, no direct artifact path |

Do not port test count or private helper assertions. Build behavior tests around
identity, round-trip, lifecycle, atomicity, and consumer isolation.

## 11. Quality Audit Findings

### High

1. **Semantic boundary leak**: dict rows with title-case aliases are the de facto
   cross-module API.
2. **Incomplete fitted model**: the artifact records hedge ratio but does not
   require the canonical intercept or a versioned spread formula.
3. **Permissive compatibility**: `extra="allow"` accepts unknown fields that may
   change trading meaning.
4. **Path-as-identity**: timeframe-derived filenames stand in for immutable
   version ids and consumer scope.
5. **Destructive promotion model**: moving candidate content loses a stable
   candidate reference and cannot safely detect concurrent promotion.
6. **Optional audit**: a promotion can succeed without its audit record.

### Medium

1. Hidden wall clocks make build, freshness, and promotion tests less
   deterministic.
2. A universal 24-hour artifact age is embedded in lifecycle code.
3. Runtime Sharpe filtering changes the approved universe after promotion.
4. Pair labels conflate display, identity, and database lookup.
5. Hashing file bytes without a specified canonical serializer can make
   semantically identical artifacts different.
6. Lifecycle, validation, persistence, policy, and path construction are
   concentrated in a runtime package owned by the wrong domain.

## 12. Implementation Slices

### PR0 — Resolve semantics

- Answer the blocking questions below.
- Freeze identity, orientation, version, and consumer-scope vocabulary.
- Define candidate, promoted, superseded, and retired semantics.

### PR1 — Identity and fitted specification

- Implement stable canonical instrument and unordered pair identity.
- Model explicit $X/Y$ orientation and the full fitted spread contract.
- Prove orientation and round-trip invariants.

### PR2 — Candidate pair set

- Define the typed aggregate and evidence/provenance requirements.
- Accept Research output without raw dictionaries.
- Validate duplicate identities, temporal scopes, finite values, and formulas.

### PR3 — Canonical JSON adapter

- Specify deterministic serialization and hash bytes.
- Implement atomic immutable publication in a local test store.
- Add corruption, collision, and round-trip tests.

### PR4 — Lifecycle store

- Separate immutable versions, promoted pointer, and audit log.
- Implement compare-and-set promotion and conflict behavior.
- Prove a failed transition preserves current promotion and history.

### PR5 — Research integration

- Return the typed candidate from the Research public API.
- Persist it through the Pairs store at the application seam.
- Remove Research knowledge of artifact filenames.

### PR6 — Operations promotion use case

- Add an explicit authenticated application command.
- Keep CLI parsing outside Pairs.
- Record principal, reason, previous/new ids, policy, and outcome atomically.

### PR7 — Trading consumer contract

- Load the exact promoted version by scope.
- Record pair-set/specification identity in runtime positions.
- Prove replacement applies only to future entries and preserves natural exit.

### PR8 — Consolidate

- Remove legacy row aliases, direct JSON reads, and path construction.
- Delete this migration guide after accepted behavior is in canonical docs.

## 13. Questions for Lucas

- **PRQ-001 (blocking):** Which canonical instrument attributes distinguish pair
  identity across spot, linear, inverse, and settlement variants?
- **PRQ-002 (blocking):** May one pair set contain both fitted orientations of
  the same unordered pair, or exactly one accepted orientation?
- **PRQ-003 (blocking):** Is the canonical spread contract always
  $x-\alpha-\beta y$, with intercept required?
- **PRQ-004 (blocking):** Which evidence fields are mandatory before a candidate
  can be serialized?
- **PRQ-005 (blocking):** What defines a promotion scope: strategy, venue market
  profile, timeframe, environment, or a combination?
- **PRQ-006:** Should candidate versions be content-addressed, run-addressed, or
  both?
- **PRQ-007:** What operator identity is sufficient locally before a login/API
  identity exists?
- **PRQ-008:** Is a promotion freshness limit required, and should it be measured
  from generation time, information cutoff, or both?
- **PRQ-009:** Can an empty candidate be promoted intentionally to block all new
  entries?
- **PRQ-010:** Which compatible schema upgrades may occur automatically on read?
- **PRQ-011:** How long must superseded and retired pair sets be retained?
- **PRQ-012:** Does rollback create a new promotion event pointing to an older
  immutable version, rather than rewriting history? The recommended answer is
  yes.

## 14. Scope Exclusions During Migration

- automatic promotion;
- hot reload inside an active Trading process;
- rebalancing or forced closes after promotion;
- remote object storage before the local contract is proven;
- UI-specific artifact models;
- arbitrary backward compatibility with frozen row shapes;
- runtime re-estimation inside Pairs.

## 15. Completion Gates

- Pair identity and orientation are distinct and deterministic.
- Every fitted specification contains one complete versioned spread contract.
- Candidate and promoted pair sets are typed and strict.
- Identical semantic content produces identical canonical bytes and hash.
- Immutable versions, promoted pointers, and audit events are separate.
- Promotion is atomic, audited, conflict-aware, and exchange-read-only.
- Research and Trading use the same typed Pairs contract.
- No caller reads raw artifact dictionaries or constructs storage paths.
- Pair-set replacement is proven to affect future entries only.
- Superseded specifications remain available for natural exit and audit.
- Offline contract tests cover at least two store adapters or one store plus a
  faithful in-memory test adapter.
- Accepted behavior is reflected in `docs/PAIRS.md`, and this file is deleted.
