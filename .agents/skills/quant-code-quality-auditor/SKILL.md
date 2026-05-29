---
name: quant-code-quality-auditor
description: Use when reviewing this Python quant trading repository for code quality, maintainability smells, oversized files or functions, SOLID-style responsibility drift, config-boundary leaks, accidental live/network test behavior, stale legacy references, or pre-merge quality risk.
---

# Quant Code Quality Auditor

Use this skill for a focused quality audit before refactors, merges, or production-safety work. The goal is actionable findings, not generic style advice.

## Required Reading

Read only what matches the audit scope:

- `.agents/CONTEXT.md` for domain terms.
- `docs/engineering-rules.md` for non-negotiable coding, config, test, and live-safety rules.
- `docs/system-design.md` when reviewing runtime, research, execution, state, reporting, artifacts, or operator controls.
- `docs/current-roadmap.md` when reviewing pair recalculation or eligible pair artifacts.
- `.agents/skills/improve-quant-architecture/references/LANGUAGE.md` when naming architecture shape problems.
- `references/REVIEW_LANGUAGE.md` when classifying audit severity and smell categories.

## Workflow

1. Define the audit scope: whole repo, `src/`, `tests/`, a package, or a changed-file set.
2. Run the deterministic scanner:

```bash
python3 .agents/skills/quant-code-quality-auditor/scripts/audit_repo.py
```

For a narrow target:

```bash
python3 .agents/skills/quant-code-quality-auditor/scripts/audit_repo.py src/engine tests/engine
```

3. Read the scanner output as leads, not final truth. A long file or `.get(` call is a signal that needs local context.
4. Inspect the highest-risk files before reporting.
5. Present findings first, ordered by severity. Include file references, why the issue matters, and the smallest reasonable next action.

## Audit Lenses

- **Responsibility drift**: modules mixing policy, I/O, runtime state mutation, math, and presentation.
- **Oversized surfaces**: files over 200 lines, long functions, or classes that require too much context to change safely.
- **Shallow abstraction**: wrappers that add indirection without leverage, locality, validation, or a simpler interface.
- **Config boundary leaks**: raw YAML dicts, permissive defaults, or `.get("key", default)` below typed config parsing.
- **Hardcoded operational assumptions**: embedded filesystem paths, exchange
  names, timeframes, environments, clocks, or storage locations in domain logic
  instead of typed config, explicit parameters, or adapters.
- **Test integrity**: unit tests that can call the network, depend on internals, or skip behavior through mocks that prove little.
- **Live-safety drift**: exchange mutation outside explicit execution modules or hidden behind research, reporting, config, or pair refresh flows.
- **Legacy contamination**: references to removed planning surfaces or stale domain names.

## Reporting Shape

Use this structure unless the user asks for something else:

- **Findings**: severity, file, problem, impact, suggested next action.
- **Scanner Signals**: brief summary of counts or notable raw signals.
- **Open Questions**: only when a decision needs user judgment.
- **No-Issue Result**: if no material findings, say so and name residual risks or test gaps.

Do not demand refactors solely because a threshold is crossed. Prefer one or two high-leverage fixes over broad cleanup.
