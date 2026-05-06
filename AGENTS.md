# Repository Instructions

This is a Python quant trading platform. Reliability, auditability, offline tests, strict configuration, and live-trading safety matter more than fast implementation.

## Required Context

Before changing code, read the relevant project context:

- `CONTEXT.md` for shared domain language.
- `docs/index.md` for the canonical documentation map.
- `docs/engineering-rules.md` for coding, testing, config, and runtime safety rules.
- `docs/system-design.md` for the current trading system design.
- `docs/current-roadmap.md` when touching active production work, especially pair recalculation and eligible pair artifacts.

## Agent Skills

Project-specific Codex skills live under `.agents/skills/`. Use `improve-quant-architecture` when asked to review architecture, find refactoring opportunities, or make the codebase more testable, maintainable, or AI-navigable.
Use `quant-code-quality-auditor` when asked to sniff code quality, pre-merge maintainability, SOLID-style responsibility drift, file/function size, config-boundary leaks, test integrity, live-safety drift, or stale legacy references.
Use `quant-roadmap-maintainer` when asked to update `docs/current-roadmap.md`, close completed roadmap work, or choose the next implementation slice.

## Non-Negotiables

- No live exchange mutation from research or pair recalculation code.
- No automatic forced close hidden behind pair-set changes.
- No network calls in unit tests.
- No raw YAML dictionaries below the config boundary.
- No `.get("key", default)` for config-origin values.
- No hardcoded operational paths, exchanges, timeframes, environments, or storage
  locations below the config/runtime adapter layer.
- No broad live-trader rewrites inside unrelated slices.
- Prefer behavior tests through module interfaces over tests coupled to internals.
- Do not call the system production-ready for real capital until the production
  readiness gate in `docs/engineering-rules.md` is satisfied.

## Working Style

- Read the existing code before proposing a shape.
- Keep changes focused and aligned with the local module style.
- Keep production code agnostic, flexible, and modular: pass paths, stores,
  exchanges, clocks, and runtime policies through typed config objects,
  explicit parameters, or adapters instead of embedding environment assumptions.
- Add or update tests for production behavior changes.
- Preserve user changes and do not revert unrelated work.
- Use architecture terms from `.agents/skills/improve-quant-architecture/references/LANGUAGE.md` when discussing module shape.
