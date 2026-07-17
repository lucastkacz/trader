# Documentation Index

The documents in this directory are the canonical description of engineering
rules, system behavior, active work, and supported local operations. When a
document conflicts with executable code, the code is evidence of current
behavior and the documentation must be corrected.

## Current Product Status

The active target is a deterministic local paper trader. The current
`state_only` runtime is useful for signals, local state, queue, risk-gate, and
operator-control drills, but it is not a paper broker and is not approved for
real capital.

The reproducible cold-start path is still under construction. See
`docs/current-roadmap.md` before treating any research-to-execution procedure as
supported.

## Document Roles

| Document | Role | Authority |
|---|---|---|
| `docs/engineering-rules.md` | Non-negotiable engineering and safety rules | Normative |
| `docs/system-design.md` | Current behavior, target invariants, and known gaps | Canonical design |
| `docs/current-roadmap.md` | Active and near-term work only | Canonical plan |
| `docs/local-operator-runbook.md` | Verified local `state_only` commands and limitations | Operational, scope-limited |
| `TRADING_SYSTEM_FLOW.md` | Visual re-entry map of current and target flows | Supporting explanation |
| `PROJECT_REENTRY_AUDIT.md` | Dated evidence and diagnosis from 2026-07-17 | Historical snapshot |

The two re-entry documents live beside the canonical docs for easier discovery.
The audit is not a continuously updated source of truth; the roadmap and system
design take precedence as implementation changes.

## Read By Task

For any code change:

- `docs/engineering-rules.md`
- `docs/system-design.md` when system behavior or architecture changes
- `docs/current-roadmap.md` when the change advances active work

For understanding how the system fits together:

- `TRADING_SYSTEM_FLOW.md`
- `docs/system-design.md`
- `PROJECT_REENTRY_AUDIT.md` for the dated deep-dive evidence

For local `state_only` operation:

- `docs/local-operator-runbook.md`
- `docs/current-roadmap.md`, because a full cold start is not yet certified

For pair recalculation, artifacts, validity, or the dynamic pair queue:

- `.agents/CONTEXT.md`
- `docs/system-design.md`
- `docs/current-roadmap.md`
- `docs/engineering-rules.md`, especially natural-exit and live-mutation rules

For architecture or code-quality reviews:

- `.agents/CONTEXT.md`
- `docs/engineering-rules.md`
- the relevant skill under `.agents/skills/`

Operational seams deserve special attention: paths, stores, exchanges, clocks,
credentials, notification channels, and runtime policy should enter through
typed config, explicit parameters, or adapters.

Before any demo/testnet or real-capital work:

- `docs/engineering-rules.md`, section "Production Readiness Gate"
- `docs/current-roadmap.md`, sections "LATER" and "Standing gate"
- `docs/system-design.md`, especially execution, state, risk, and operator
  controls

None of these documents currently grants approval to enable `live` mode or use
real capital.

## Documentation Policy

- Distinguish `CURRENT`, `TARGET`, and `KNOWN GAP` statements.
- Keep canonical documents short enough to reread after each behavior change.
- Do not preserve obsolete implementation history in canonical documents; Git
  and dated audits hold history.
- Do not describe a planned invariant as if the runtime already enforces it.
- Commands belong in the runbook only after their paths and CLI arguments are
  verified.
- Prefer updating these documents over adding another overlapping plan.
- Add a new canonical document only when it owns a genuinely different reader
  task.
