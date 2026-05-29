---
name: python-sustainability-sniffer
description: Use when reviewing this Python quant trading repository for Pythonic design, OOP/SOLID sustainability, API ergonomics, cohesive modules/classes, side-effect boundaries, dependency direction, dataclass/value-object usage, protocol/adapter seams, or long-term maintainability smells. Complements quant-code-quality-auditor by focusing on design quality rather than broad safety/config/test scanning.
---

# Python Sustainability Sniffer

Use this skill when the user asks whether code is sustainable, Pythonic,
OOP-friendly, SOLID-ish, maintainable, or likely to decay into "slop." The goal
is specific, repo-aware design feedback with practical refactor suggestions.

## Relationship To Existing Skills

- Use `quant-code-quality-auditor` for broad repository audits: safety,
  config-boundary leaks, live/network test risk, stale imports, oversized files,
  and pre-merge risk.
- Use this skill for deeper Python design judgment: object boundaries,
  dependency shape, cohesion, side effects, protocols/adapters, domain model
  clarity, and API ergonomics.
- Use both skills when the user asks for a serious quality gate before a merge
  or a major architecture slice.

## Required Reading

Read only what matches the review scope:

- `.agents/CONTEXT.md` for domain terms.
- `docs/engineering-rules.md` for coding, config, testing, and live-safety
  constraints.
- `docs/system-design.md` when reviewing runtime, research, execution, state,
  reporting, artifacts, or operator controls.
- `.agents/skills/improve-quant-architecture/references/LANGUAGE.md` when
  naming module-shape and seam problems.
- `references/CHECKLIST.md` for the sustainability smell checklist.

## Workflow

1. Define the review scope: changed files, one module, one package, or whole
   repo.
2. Inspect the public interfaces first: constructors, function signatures,
   dataclasses, config models, CLI entrypoints, and package exports.
3. Trace side effects: network, filesystem, database, exchange mutation,
   notifier calls, clocks, and global settings.
4. Inspect implementation only after the interfaces and side effects are clear.
5. Report only material findings. Do not nitpick style that formatters or local
   conventions already handle.

## Review Lenses

- **Cohesion**: one class/module should have one reason to change.
- **Explicit dependencies**: prefer typed config, parameters, adapters,
  protocols, and injected stores/clocks over hidden globals.
- **Pythonic APIs**: clear names, small signatures, dataclasses/value objects for
  records, context managers for resources, iterables/mappings where natural.
- **OOP restraint**: use classes for stateful collaborators or stable concepts;
  prefer functions for stateless transformations.
- **SOLID pragmatism**: avoid god classes, inheritance ladders, broad interfaces,
  and conditionals that should be policy objects only when real variation
  exists.
- **Side-effect boundaries**: keep pure math, state mutation, I/O, orchestration,
  and presentation separate when behavior is substantial.
- **Error and auditability**: fail loudly at boundaries, preserve actionable
  context, and avoid swallowing exceptions that hide operator risk.
- **Testability**: behavior should be testable through module interfaces without
  network, live exchange mutation, sleeps, or fragile internals.

## Reporting Shape

Use this structure:

- **Findings**: severity, file, smell, why it matters, smallest useful fix.
- **Good Patterns To Preserve**: brief note on designs that are working.
- **Refactor Candidates**: optional, ordered by leverage.
- **Do Not Change Yet**: boundaries where a refactor would increase risk or
  exceed the requested scope.

If there are no meaningful issues, say that clearly and name residual risks.

## Guardrails

- Do not recommend abstract base classes, factories, or inheritance unless they
  remove actual duplication or isolate real runtime variation.
- Do not demand "pure OOP" in places where simple functions are clearer.
- Do not suggest broad rewrites during live-trading safety work.
- Preserve natural-exit and no-live-mutation rules.
- Prefer small, behavior-covered refactors over aesthetic reshaping.
