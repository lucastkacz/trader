---
name: quant-structure-guardian
description: Use before creating, moving, renaming, or reorganizing files/packages in this Python quant trading repository; use when reviewing folder structure, package ownership, loose modules, compatibility facades, architectural drift, runtime/state/reporting boundaries, or whether a refactor improves long-term maintainability without weakening live-trading safety.
---

# Quant Structure Guardian

Use this skill as a lightweight architecture gate before structural changes.
The goal is to prevent package drift, loose-file accumulation, shallow facades,
and aesthetic reshuffles that do not make the trading system safer or easier to
maintain.

## Required Reading

Read only what matches the affected area:

- `.agents/CONTEXT.md` for domain terms.
- `docs/engineering-rules.md` for safety and config rules.
- `docs/system-design.md` for canonical system shape.
- `.agents/skills/improve-quant-architecture/references/LANGUAGE.md` for
  module/interface/depth/seam vocabulary.

When touching active queue, pair-validity, promoted-artifact, natural-exit, or
execution behavior, also read `docs/current-roadmap.md`.

## Structural Gate

Before adding or moving a production file, answer these privately:

1. **Concept owner**: which domain concept owns this code?
2. **Package home**: does an existing subpackage already own that concept?
3. **Interface depth**: does this change hide complexity behind a smaller
   interface, or does it just move code around?
4. **Caller knowledge**: will callers need to know less after the change?
5. **Safety boundary**: could this blur research/execution, reporting/mutation,
   state-only/live, or pair-recalculation/natural-exit rules?
6. **Config boundary**: are typed config objects or explicit parameters still
   the only way operational policy enters lower layers?
7. **Test surface**: what behavior test proves the new structure, without
   coupling to private helper names?

If the answers are weak, do not create a new file yet. Prefer strengthening an
existing module interface or identifying the missing package concept first.

## Smells To Flag

- A root package gains another loose `.py` file when a subpackage owns the
  concept.
- A file becomes a compatibility facade without a short migration reason.
- A module mixes orchestration, I/O, state mutation, math, policy, and rendering.
- A refactor changes imports broadly but leaves callers with the same complexity.
- Tests need private helpers because the public module interface is too shallow.
- A package has multiple names for the same concept, such as generic `pairs`
  versus promoted/candidate/eligible pair artifacts.
- A structural cleanup touches live-order, reconciliation, or natural-exit
  behavior without focused tests.

## Preferred Refactor Shape

Work in small, behavior-preserving slices:

1. Map current callers and tests with `rg`.
2. Move one cohesive concept at a time.
3. Keep a temporary compatibility facade only when many callers would otherwise
   churn at once.
4. Update imports toward the canonical package path.
5. Add or preserve behavior tests at the module interface.
6. Run targeted pytest for the moved area.
7. Remove compatibility facades in a later slice once callers have migrated.

## Repo-Specific Boundaries

- Research flow may produce candidate artifacts, never live exchange mutation.
- Pair recalculation affects future entries only; it must not force close or
  rebalance open positions.
- Reporting and pair-validity diagnostics are read-only.
- Runtime queue decisions may block/rank future entries, not natural exits.
- Live exchange mutation belongs only behind explicit execution modules and
  explicit execution mode.
- Raw YAML dictionaries must stay at the config boundary.
- Operational paths, exchanges, timeframes, clocks, credentials, and storage
  locations enter through typed config, explicit parameters, or adapters.

## Output Shape

For reviews, report:

- **Candidate**: the package/file shape being considered.
- **Verdict**: keep, move, split, merge, or defer.
- **Why**: concept ownership, interface depth, caller impact, and safety risk.
- **Smallest safe slice**: the next behavior-preserving change.
- **Tests**: focused tests to run or add.

For implementation, keep final summaries short: moved files, updated imports,
tests run, and any remaining compatibility facade.
