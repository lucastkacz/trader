---
name: improve-quant-architecture
description: Use when improving architecture, finding refactoring opportunities, reviewing maintainability, consolidating shallow modules, or making this Python quant trading codebase more testable, auditable, and AI-navigable.
---

# Improve Quant Architecture

Use this skill to surface architecture improvements in this repository. The goal is not generic cleanup; the goal is deeper modules with smaller, safer interfaces around trading concepts.

## Required Reading

Read only what is relevant to the area being reviewed:

- `.agents/CONTEXT.md` for project domain language.
- `docs/engineering-rules.md` for non-negotiable engineering rules and test flow.
- `docs/system-design.md` for the current trading system shape.
- `docs/current-roadmap.md` when touching pair recalculation, eligible pair artifacts, research/execution separation, or natural-exit policy.
- `references/LANGUAGE.md` for architecture vocabulary.
- `references/DEEPENING.md` when proposing how to reshape a candidate.

## Core Rules

- Preserve the research-to-execution separation.
- Do not propose live exchange mutation from research, recalculation, or artifact lifecycle code.
- Do not hide forced position closes behind pair recalculation.
- Do not introduce raw YAML dict access below the config boundary.
- Do not introduce `.get("key", default)` for config-origin values.
- Do not preserve hardcoded operational paths, exchanges, timeframes,
  environments, clocks, or storage locations inside domain modules.
- Prefer agnostic, flexible, modular seams: typed config, explicit parameters,
  or adapters should carry environment-specific concerns into the module.
- Prefer deep modules around domain concepts over broad pass-through wrappers.
- Treat the module interface as the test surface.
- For true external dependencies such as exchanges, Telegram, filesystem artifacts, or clocks, propose adapters only when there is a production adapter and a test adapter.

## Process

### 1. Explore

Start from the user's target area and trace callers, tests, configs, and persisted artifacts. Look for friction:

- Understanding one domain concept requires bouncing across many files.
- A module is shallow: its interface exposes nearly the same complexity as its implementation.
- Tests verify internals instead of behavior through the module interface.
- Config knowledge leaks below the config boundary.
- Operational path, exchange, storage, clock, or environment assumptions are
  hardcoded rather than entering through a seam.
- Artifact schema, validation, promotion, and loading are spread across callers.
- Runtime trading behavior mixes policy, I/O, state mutation, and calculation in one place.

Apply the deletion test: if deleting a module merely moves its complexity into callers, it was earning its keep. If deleting it removes complexity, it was pass-through code.

### 2. Present Candidates

Present a numbered list of deepening opportunities. For each candidate include:

- **Files**: the files/modules involved.
- **Problem**: why the current shape causes friction.
- **Solution**: what would change in plain English.
- **Benefits**: leverage for callers, locality for maintainers, and how tests improve.
- **Risk**: live-trading, artifact, config, or migration risks.

Use `.agents/CONTEXT.md` domain terms and `references/LANGUAGE.md` architecture terms. Do not propose concrete new interfaces yet. Ask which candidate to explore.

### 3. Design The Chosen Candidate

Once the user chooses a candidate, grill the design:

- What behavior belongs behind the module interface?
- Where should the seam live?
- Which dependencies are in-process, local-substitutable, true external, or runtime state?
- Which paths, storage stores, clocks, exchanges, or runtime policies must be
  supplied instead of hardcoded?
- Which adapters are justified?
- What tests should survive future implementation refactors?
- Which old tests become waste after testing through the deeper interface?

If a new domain term is needed, add it to `.agents/CONTEXT.md`. If the user rejects a candidate for a durable reason, offer to record that decision in a future ADR.

### 4. Implementation Bias

When implementation follows, keep it sliced:

- Add or update tests first for behavior changes.
- Keep external interfaces boring and explicit.
- Keep internal seams private unless callers truly need them.
- Do not combine architecture reshaping with unrelated live-trader rewrites.
- Run targeted pytest for the changed area.
