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

For pair recalculation or eligible pair artifacts:

- `docs/system-design.md`
- `docs/current-roadmap.md`

## Documentation Policy

- Keep canonical docs short and current.
- Describe the current system and the next intended changes.
- Do not preserve obsolete implementation history in canonical docs.
- Prefer changing these docs over adding long new planning files.
- Add a new document only when the existing three files become genuinely hard to
  navigate.
