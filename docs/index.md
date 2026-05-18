# Documentation Index

This directory is the canonical documentation surface for humans and AI agents.
If a rule or design is not represented here, treat it as non-canonical unless the
current code clearly proves otherwise.

## Read By Task

For any code change:

- `docs/engineering-rules.md`
- `docs/system-design.md` if the change touches system behavior
- `docs/current-roadmap.md` if the change relates to current production work

Before real-capital operation:

- `docs/engineering-rules.md`, section "Production Readiness Gate"
- `docs/system-design.md`, especially execution, state, risk, and operator controls

For architecture reviews:

- `CONTEXT.md`
- `.agents/skills/improve-quant-architecture/SKILL.md`
- `.agents/skills/improve-quant-architecture/references/LANGUAGE.md`
- Pay special attention to operational seams: paths, storage, exchanges,
  clocks, credentials, and runtime policies should not be hardcoded inside
  domain modules.

For code quality audits:

- `CONTEXT.md`
- `docs/engineering-rules.md`
- `.agents/skills/quant-code-quality-auditor/SKILL.md`

For roadmap updates:

- `docs/current-roadmap.md`
- `docs/engineering-rules.md`
- `docs/system-design.md`
- `.agents/skills/quant-roadmap-maintainer/SKILL.md`

For pair recalculation or eligible pair artifacts:

- `docs/system-design.md`
- `docs/current-roadmap.md`

For pair validity, data refresh cadence, or drift diagnostics:

- `CONTEXT.md`
- `docs/system-design.md`, section "Pair Validity And Refresh Cycle"
- `docs/current-roadmap.md`
- `docs/local-operator-runbook.md`, section "Refresh Pair Data And Generate
  Validity Reports" for the local CLI flow

For local state-only operator drills:

- `docs/local-operator-runbook.md`

## Documentation Policy

- Keep canonical docs short and current.
- Describe the current system and the next intended changes.
- Do not preserve obsolete implementation history in canonical docs.
- Prefer changing these docs over adding long new planning files.
- Add a new document only when the existing three files become genuinely hard to
  navigate.
