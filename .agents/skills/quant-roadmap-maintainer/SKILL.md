---
name: quant-roadmap-maintainer
description: Use when updating docs/current-roadmap.md, closing or advancing roadmap work, choosing the next implementation slice, preserving near-term scope, or reconciling completed code changes with the active quant platform roadmap.
---

# Quant Roadmap Maintainer

Use this skill to keep `docs/current-roadmap.md` short, current, and useful after roadmap work changes. The roadmap is not a changelog; Git records history. The roadmap should say what matters next.

## Required Reading

Read only what is needed for the roadmap update:

- `docs/current-roadmap.md` for the active roadmap.
- `docs/engineering-rules.md` for production readiness gates and safety limits.
- `docs/system-design.md` for current system behavior and intended flow.
- `CONTEXT.md` for domain terms.
- Recent `git diff`, `git status`, or `git log` when updating after completed work.

## Update Rules

- Keep the document short and focused on active or near-term work.
- Preserve explicit "Do not implement" boundaries when they still protect safety.
- Preserve agnostic modularity: roadmap slices should call out when paths,
  stores, exchanges, clocks, or runtime policies need typed config, explicit
  parameters, or adapters instead of hardcoded assumptions.
- Do not describe obsolete implementation history.
- Do not add a new roadmap document unless `docs/current-roadmap.md` becomes genuinely hard to navigate.
- Do not mark the system production-ready or safe for increased capital unless every gate in `docs/engineering-rules.md` is satisfied.
- Use domain terms from `CONTEXT.md`: research flow, execution flow, eligible pair artifact, pair recalculation, candidate artifact, promoted artifact, natural exit.

## Workflow

1. Identify whether the current `Now` item is complete, partially complete, or still active.
2. If complete, promote the next safest near-term item into `Now`.
3. If partially complete, rewrite `Now` around the remaining behavior instead of appending history.
4. Move deferred work into `Next` or `Later` only when it is still relevant and safe.
5. Keep scope exclusions visible when accidental implementation would create live-trading risk.
6. After editing, reread the full file and remove drift, duplication, and stale promises.

## Reporting

Summarize roadmap edits by explaining:

- what changed in `Now`
- what moved to `Next` or `Later`
- which safety boundaries remain
- any uncertainty that needs user judgment

Prefer a small, honest roadmap over a comprehensive plan that becomes stale.
