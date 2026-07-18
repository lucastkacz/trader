# Market Data Migration Guide

> **TEMPORARY DOCUMENT — DELETE AFTER MIGRATION.**
>
> This guide inventories the frozen data implementation, records corrections,
> and sequences the Market Data rebuild. Transfer accepted behavior to
> `docs/MARKET_DATA.md` and delete this file when every completion gate passes.

**Status:** planning and source audit; no Market Data production code exists in
the new namespace.

**Last reviewed:** 2026-07-18

## 1. Purpose and Authority

The permanent module behavior lives in [`MARKET_DATA.md`](MARKET_DATA.md). This
guide owns temporary concerns:

- source-by-source inventory;
- behavior worth preserving;
- defects and ambiguous semantics to correct;
- provisional implementation destinations;
- implementation slices, questions, and completion gates.

When sources disagree, authority order is:

1. Lucas's explicit instruction for the current task.
2. `.agents/AGENTS.md` for durable implementation and safety rules.
3. `docs/_IMPLEMENTATION_AGENT_GUIDE.md` for route order and completion state.
4. `ARCHITECTURE_REFACTOR.md` and the relevant canonical module documents.
5. `docs/current-roadmap.md` for current status and near-term scope.
6. This guide for migration traceability, open decisions, slices, and gates.
7. Frozen tests as clues about intended V1 behavior.
8. Frozen implementation and config as clues about actual V1 behavior.

The expected readonly source worktree is
`/Users/lucastkacz/Documents/quant-v1-reference`, corresponding to tag
`legacy-v1-before-rewrite`. Do not patch it or create runtime imports to it.

## 2. Working Capability Map

Potential implementation homes include observation contracts, validation,
dataset assembly, synchronization, lifecycle, and storage under
`stat_arb.market_data`.

This is not a file contract. Do not create `api.py`, `models.py`, `sync/`, or any
other path merely because it appears in a plan. Each slice chooses the smallest
cohesive physical shape supported by behavior and tests.

## 3. Migration Actions

| Label | Meaning |
|---|---|
| `KEEP-CONCEPT` | Preserve the behavior behind a new canonical contract |
| `ADAPT` | Preserve useful behavior after correcting semantics or ownership |
| `SPLIT` | Separate multiple reasons to change |
| `MERGE` | Combine duplicated behavior behind one deeper interface |
| `MOVE-OWNER` | Keep the behavior in a different top-level module |
| `REPLACE` | Reimplement from the accepted contract rather than porting code |
| `DROP` | Do not migrate |
| `DEFER` | Keep outside the current implementation slice |
| `OPEN` | Requires explicit user judgment |

## 4. Existing Flow

```text
typed YAML
-> CCXT market-data adapter
-> paginated OHLCV/funding fetch
-> DataFrame normalization
-> backfill or tail refresh
-> merge and optional retention
-> Parquet payload + embedded metadata
-> research/universe/runtime readers
```

Useful concepts are present: canonical OHLCV columns, closed-candle cutoff,
typed metadata, readonly source seams, idempotent-looking backfill, overlap
refresh, per-symbol outcomes, retention, and local fixtures.

The main structural problem is ownership inversion. Data sync imports
`MarketTicker` from Exchange while Exchange imports OHLCV normalization from
Data. The target direction is one-way: Market Data owns canonical observations
and source contracts; Exchange implements them.

## 5. Source Inventory: Observation Semantics

| Source | Existing behavior | Action | Required correction |
|---|---|---|---|
| `src/data/ohlcv/frames.py` | Canonical columns, casting, sorting, duplicate removal, merge | `ADAPT` | Separate lossless normalization from validation; do not silently drop invalid rows; validate OHLC and positivity |
| `src/data/ohlcv/metadata.py` | Dataset identity, coverage/gap metadata, market context | `SPLIT` + `ADAPT` | Separate canonical provenance from derived quality evidence and backend metadata; inject clock; reject unknown canonical fields |
| `src/data/ohlcv/retention.py` | Age/bar-count trimming | `ADAPT` | Explicit clock; recompute coverage after pruning; no hidden wall clock or misleading completeness |
| `src/data/ohlcv/__init__.py` | Re-exports the complete OHLCV surface | `DROP` or narrow | Export only the proven public interface |
| `src/utils/timeframe_math.py` | Duration parsing, alignment, last closed candle | `MOVE-OWNER` + `REPLACE` | Central timeframe value in Market Data; reject invalid divisibility; document exact-boundary semantics |

### Important semantic defects

1. Normalization coerces non-numeric values to null and drops them without
   retaining rejection evidence.
2. Validation checks shape, duplicates, sorting, and parseability but not
   positive prices, non-negative volume, or OHLC relationships.
3. Numeric timestamp units are guessed from magnitude instead of supplied by
   the source contract.
4. Metadata uses `extra="ignore"`, allowing schema drift to disappear.
5. Metadata generation reads the wall clock internally.
6. Coverage may be marked complete from the last timestamp while interior gaps
   still exist.
7. `get_bars_per_day` truncates unsupported intraday divisors rather than proving
   exact divisibility.

## 6. Source Inventory: Storage and Funding

| Source | Existing behavior | Action | Required correction |
|---|---|---|---|
| `src/data/storage/local_parquet.py` | Local OHLCV paths, Parquet read/write, embedded metadata | `REPLACE` behind storage contract | Atomic writes, collision-safe identity, no constructor mkdir, typed metadata, content validation, concurrency policy |
| `src/data/storage/local_funding.py` | Funding Parquet persistence and metadata | `MERGE` with canonical storage behavior | Funding event contract, source/market/coverage provenance, strict validation, missing distinct from empty |

Storage problems to correct:

- replacing `/` and `:` with `_` is lossy and can collide;
- symbols are later reconstructed from filenames;
- direct Parquet writes can expose partial/corrupt output;
- store construction creates directories as a hidden side effect;
- arbitrary custom metadata is merged into canonical metadata;
- OHLCV and funding stores duplicate lifecycle and schema behavior;
- there is no writer coordination or content hash;
- funding has no settlement interval, market profile, coverage, or quality
  evidence.

Parquet remains a reasonable local adapter, not a domain commitment. An in-memory
adapter should establish the behavioral storage contract first.

## 7. Source Inventory: Synchronization

| Source | Existing behavior | Action | Required correction |
|---|---|---|---|
| `src/data/sync/models.py` | Store/source protocols, requests, policies, results | `SPLIT` + `ADAPT` | Remove Exchange imports; canonical source contract belongs to Market Data; use structured outcome/error semantics |
| `src/data/sync/config.py` | Strict YAML loader for retry/pacing | `MOVE-OWNER` | YAML parsing at application config boundary; sync receives validated policy |
| `src/data/sync/helpers.py` | Result aggregation, coverage helpers, missing-file handling | `MERGE` | Keep cohesive behavior near sync/dataset contract; metadata must be typed |
| `src/data/sync/backfill.py` | Sequential pagination, retry, save, per-symbol outcomes | `SPLIT` + `ADAPT` | Strict progress/terminal rules, page evidence, validate before save, typed source errors, atomic publish |
| `src/data/sync/refresh.py` | Tail refresh with overlap, merge, retention | `ADAPT` | Separate tail refresh from interior-gap repair; avoid broad exception strings; do not infer completeness from final row |
| `src/data/sync/__init__.py` | Broad convenience exports | `DROP` or narrow | Publish only the stable synchronization interface |

### Synchronization risks

- pagination advances by one millisecond rather than one canonical bar and can
  loop if a provider rounds `since` back to the same candle;
- retry catches every exception, including invalid requests and unsupported
  capabilities;
- metadata is trusted to skip acquisition without verifying stored content;
- backfill may replace data outside its requested window;
- tail refresh does not repair interior gaps;
- broad exceptions become free-form notes, losing error taxonomy;
- `NO_DATA`, `NO_NEW_DATA`, partial coverage, and failure aggregation are not a
  fully explicit state model;
- sequential symbol processing is safe but its resource policy is implicit.

## 8. Configuration Inventory

| Source | Existing concern | Action |
|---|---|---|
| `configs/data/ohlcv_backfill/default.yml` | fetch limit, retries, backoff, request pause | Preserve values as evidence; rebuild only behind typed application config |
| `configs/data/lifecycle/default.yml` | retention, freshness, cleanup | Audit 5-day retention carefully; split consumer freshness from destructive lifecycle policy |
| `src/data/lifecycle/config.py` | strict config and retention conversion | `SPLIT`; loader outside domain, policies inside appropriate capability |
| `src/data/lifecycle/__init__.py` | re-exports | `DROP` or narrow |

The current 5-day retention can destroy the historical window Research needs.
Retention must be use-case-specific and cannot be a universal default shared by
research history and short-lived runtime caches.

## 9. Test Inventory

| Source | Useful evidence | Migration rule |
|---|---|---|
| `tests/data/test_ohlcv.py` | normalization, duplicate merge, retention, closed-candle boundary | Preserve accepted invariants; add invalid OHLC/price/volume and timestamp-unit cases |
| `tests/data/test_local_parquet.py` | round-trip, metadata, missing reads, read-without-mkdir | Rebuild as storage contract tests shared by memory and Parquet adapters |
| `tests/data/test_local_funding.py` | funding round-trip and missing behavior | Replace missing-as-empty ambiguity and expand event semantics |
| `tests/data/test_sync.py` | pagination, persistence, refresh overlap, retention, per-symbol failure | Retain behavior scenarios through public sync interface; add no-progress/gap/atomic failure cases |
| `tests/data/test_lifecycle_config.py` | strict config | Move to application config tests |
| `tests/data/test_sync_config.py` | policy conversion | Keep only if a real loader exists |
| `tests/data/test_live_backfill_probe.py` | end-to-end provider/local-store evidence | `DEFER`; explicit live probe only |
| `tests/data/test_live_refresh_completion_probe.py` | waiting for new candle and refresh | `DROP` as default test; replace waiting with injected clock/source; optional probe later |
| `tests/data/test_ohlcv_live_probe.py` | local acquisition smoke test | `DEFER` to explicit probes |
| `tests/data/test_parquet_metadata_probe.py` | manual metadata inspection | Replace with assertions or an operator inspection command |

Do not migrate print-based announcements or the number of tests. Preserve
behavioral risk coverage.

## 10. Cross-Module Ownership Corrections

| Concern | Target owner | Rule |
|---|---|---|
| Canonical symbol, timeframe, candle, funding, ticker facts | `market_data` | Exchange adapters return these contracts |
| Native venue payload and market mapping | `exchange` | Never leaks to Market Data consumers |
| Volume/liquidity metrics used as data facts | `market_data` or Research calculation | Preserve unit and window provenance |
| Minimum volume and dominant-market exclusion | `research` | Eligibility policy, not data validity |
| Spread, returns matrix, indicators | `research` | Derived quantitative evidence |
| Execution quotes/order books for fills | shared Market Data contracts, consumed by `trading` | No order mutation in Market Data |
| Storage backend and paths | adapter/application config | Not canonical dataset identity |

## 11. Quality Audit Findings

### High

- **Boundary cycle:** `data.sync.models` imports an Exchange-owned ticker type
  while Exchange imports Data normalization. Correct dependency direction before
  adding new adapters.
- **Silent data loss:** normalization drops coercion failures and duplicates
  without complete evidence, which can make bad provider data look clean.
- **Storage identity loss:** filename sanitization is non-reversible and permits
  symbol collisions.
- **Atomicity:** direct Parquet replacement can publish partial data.

### Medium

- metadata, backfill, and refresh are oversized because validation,
  orchestration, persistence, and result assembly are mixed;
- hidden wall-clock access weakens reproducibility;
- broad exception handling erases retryability and failure category;
- live probes contain long, stateful workflows and must remain outside default
  verification;
- config loaders are embedded inside domain packages rather than one application
  config boundary.

The scanner's `.get()` warnings in metadata/provider dictionaries are not all
config leaks. Raw external mappings legitimately need defensive parsing, but
that parsing belongs at the adapter boundary and should produce typed outcomes.

## 12. Implementation Slices

Every target name is provisional. Create only the smallest physical surface that
earns its interface.

### MD0 — Resolve semantics

Decide canonical instrument identity, supported observation kinds, timeframe
semantics, timestamp units, duplicate policy, invalid-row policy, information
cutoff, and first storage adapter.

**Gate:** one hand-written dataset example has unambiguous identity,
availability, validity, coverage, continuity, and provenance.

### MD1 — Canonical observations and validation

Implement timeframe, instrument, candle, funding, and market-fact behavior with
pure normalization/validation.

**Gate:** deterministic fixtures prove closed-candle, invalid OHLC, missing
volume, duplicate conflict, gaps, and stable ordering.

### MD2 — Dataset and in-memory store

Bind observations to requests, cutoffs, quality evidence, provenance, and a
stable semantic hash. Establish storage behavior with an in-memory adapter.

**Gate:** dataset round-trip preserves every semantic fact and cannot confuse
missing, empty, incomplete, or invalid data.

### MD3 — Local persistent adapter

Add Parquet only after the storage contract exists. Use collision-safe keys,
validated atomic publication, and explicit writer behavior.

**Gate:** interrupted writes do not replace the last valid dataset; native
derivative symbols round-trip without reconstruction.

### MD4 — Backfill

Compose a readonly source, bounded pagination, normalization, validation,
per-symbol results, retry taxonomy, and atomic storage.

**Gate:** repeated requests are idempotent; non-progressing providers terminate
explicitly; no observation after the cutoff is stored.

### MD5 — Refresh and gap repair

Add overlap-based tail refresh, provider revision handling, interior-gap
detection/repair, and recomputed quality evidence.

**Gate:** reaching the end timestamp cannot hide an interior gap; partial
results remain observable.

### MD6 — Lifecycle

Add explicit freshness queries, retention, cleanup dry-run, and provenance-safe
destructive actions only when actual consumers require them.

**Gate:** pruning recomputes coverage and cannot run during import/read.

### MD7 — Readonly exchange integration

Wire an Exchange source adapter behind the already-proven Market Data contract.
Keep live probes explicit and separate.

**Gate:** the same contract suite passes with the local fake and normalized
adapter payload fixtures; offline acceptance never reaches network.

### MD8 — Consolidate

Remove unused scaffolding, reconcile permanent docs and roadmap, verify package
dependency direction, and delete this guide after all gates pass.

## 13. Questions for Lucas

| ID | Question | Why it matters | Recommended starting answer |
|---|---|---|---|
| `MDQ-001` | Which observation kinds are required for the first Research run? | Prevents building unused streams/order books | Closed OHLCV first; funding only if derivative costs are evaluated |
| `MDQ-002` | What canonical instrument identity should persist across venues? | Avoids filename and native-symbol ambiguity | Structured base/quote/type/settle plus venue listing identity |
| `MDQ-003` | Confirm candle timestamps mean interval open? | Determines cutoff and look-ahead behavior | Yes; available only at close |
| `MDQ-004` | Should invalid source rows reject the page or the complete dataset? | Controls silent loss versus availability | Reject affected dataset by default and report exact rows |
| `MDQ-005` | How should conflicting duplicate candles be resolved? | Providers can revise recent bars | Explicit source revision rule within refresh overlap; otherwise fail |
| `MDQ-006` | Is Parquet the first persistent adapter? | Shapes local inspection and atomicity work | Yes, after memory contract; keep backend outside domain |
| `MDQ-007` | Do we retain raw provider responses? | Improves forensic reproducibility at storage cost | Optional immutable reference for acquisition runs, not embedded in domain data |
| `MDQ-008` | What gap policy does first Research accept? | Statistical validity depends on continuity | Never synthesize silently; Research declares its tolerance |
| `MDQ-009` | Is 5-day retention still desired anywhere? | It destroys research history | No universal default; separate research archive from runtime cache |
| `MDQ-010` | What historical funding source is trustworthy? | Net returns require actual event timing | Defer until venue/profile chosen, then validate settlement semantics |
| `MDQ-011` | Should refresh repair interior gaps automatically? | Tail-only refresh can claim false completeness | Detect always; repair explicitly with bounded requests |
| `MDQ-012` | How should concurrent sync runs coordinate? | Prevents lost/corrupt writes | Single writer per dataset identity for local operation |

## 14. Scope Exclusions During Migration

- research universe eligibility and volume thresholds;
- exchange-specific payload parsing inside Market Data;
- streaming infrastructure before historical correctness;
- order submission, account mutation, or reconciliation;
- cloud/database selection before the local storage contract;
- synthetic gap filling as a hidden convenience;
- scheduling, UI, Telegram, or deployment.

## 15. Completion Gates

- [ ] Canonical symbols survive source, storage, and dataset round-trips.
- [ ] Candle availability and information cutoffs mechanically prevent open-bar
  look-ahead.
- [ ] Invalid rows cannot disappear silently.
- [ ] Validity, coverage, continuity, completeness, and freshness remain
  separate observable facts.
- [ ] Backfill is bounded, progressive, idempotent, and cutoff-safe.
- [ ] Refresh detects interior gaps and source revisions.
- [ ] Storage publication is validated, collision-safe, and atomic.
- [ ] Funding and missing market facts preserve correct semantics.
- [ ] Market Data does not import Exchange implementations, Research, or Trading.
- [ ] Research thresholds remain outside Market Data.
- [ ] Deterministic fake-source acceptance and storage contract tests pass.
- [ ] Live probes are opt-in and absent from the default suite.
- [ ] Permanent documentation describes only accepted module behavior.

After the checklist passes, transfer any remaining rationale or tested operator
commands to permanent documentation, remove links to this file, and delete it.
