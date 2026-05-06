# Review Language

Use these labels to keep quality audits consistent and actionable.

## Severity

- **Blocker**: likely live-trading mutation risk, hidden rebalancing, network in unit tests, config permissiveness that can boot unsafe behavior, or data/artifact corruption.
- **High**: maintainability or test weakness likely to cause production mistakes soon.
- **Medium**: clear friction, responsibility drift, oversized surface, or brittle tests with manageable blast radius.
- **Low**: cleanup that improves navigation or clarity but is not blocking.

## Smell Categories

- **Responsibility drift**: one module owns multiple reasons to change.
- **Boundary leak**: lower layers know raw config, YAML shape, exchange client details, filesystem artifact layout, or Telegram protocol details unnecessarily.
- **Shallow module**: a wrapper mostly mirrors another interface and does not reduce caller complexity.
- **Oversized surface**: file, function, or class needs too much context to audit safely.
- **Test coupling**: tests assert private structure instead of behavior through the module interface.
- **Accidental integration**: an offline test can touch network, exchange, Telegram, wall clock, or real filesystem state without an explicit adapter.
- **Legacy reference**: code, docs, comments, or tests point to removed surfaces such as `PLAN/` or stale domain names.

## Thresholds Are Signals

- File over 200 lines: inspect for cohesive domain ownership before calling it a problem.
- Function over 60 lines: inspect branching, side effects, and test surface.
- Class over 120 lines: inspect state ownership and whether responsibilities split naturally.
- Repeated `.get(`: inspect whether values originate from typed config or ordinary local dictionaries.

The finding should explain why the threshold matters in context. Threshold-only findings are weak.
