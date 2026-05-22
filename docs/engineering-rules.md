# Engineering Rules

This project is a Python quant trading platform. Reliability, auditability,
offline verification, and live-trading safety matter more than fast changes.

## Code Shape

- Use type hints for all production function signatures.
- Prefer clear, boring modules with explicit interfaces.
- Production modules must be agnostic to exchange, timeframe, environment,
  filesystem layout, and storage backend unless that module is the explicit
  adapter for that concern.
- Do not hardcode operational paths, exchanges, timeframes, credentials,
  environments, clocks, or storage locations inside domain logic.
- Put environment-specific behavior behind typed config, explicit parameters,
  or adapters. If a default path is useful, keep it at an entrypoint, config
  model, or narrow local adapter seam.
- Keep pure math, state mutation, external I/O, runtime orchestration, and
  presentation in separate modules when the behavior is substantial.
- Avoid pass-through modules. A module should provide leverage or locality.
- Keep compatibility facades only as short-lived migration aids. Do not leave
  duplicate canonical import paths in place once callers can use the deeper
  package directly.
- Do not add broad rewrites while implementing a policy or behavior slice.

## Configuration

- YAML is parsed at the config boundary into typed config objects.
- Raw YAML dictionaries must not leak below the config boundary.
- Do not use `.get("key", default)` for config-origin values.
- Operational values must be explicit in YAML or typed secrets.
- Missing required operational config should fail at boot with a precise error.
- `null` is acceptable only when it is explicitly present and modeled as
  intentional.
- Paths and storage locations used by production flows are operational config or
  adapter inputs, not hidden constants in domain modules.

## Testing

- Use `pytest`.
- Unit tests must not call the network.
- Exchange clients, Telegram, clocks, and filesystem-heavy behavior should use
  mocks, fakes, or local test adapters.
- Tests belong under `tests/`. Production research modules may run simulations,
  stress filters, or validations, but they are not a substitute for behavior
  tests through module interfaces.
- Add or update tests for production behavior changes.
- Prefer behavior tests through module interfaces over tests coupled to internals.
- If a test or implementation loops without progress, stop and report the design
  blockage. Do not reset or revert user work without explicit permission.

## Quant And Runtime Safety

- Mathematical data processing should prefer vectorized pandas/numpy operations.
- Do not use row-by-row DataFrame iteration for historical price or indicator
  calculations.
- Long pandas/numpy work inside async flows must not block the event loop.
- No live exchange mutation is allowed from research, pair recalculation,
  reporting, config loading, or tests.
- Live exchange mutation belongs only behind explicit execution modules and
  explicit execution modes.
- Pair recalculation must not force-close or rebalance open positions.

## Production Readiness Gate

Do not treat the system as ready for real capital until all of these are true:

- Offline tests are green.
- Lint/static checks are green.
- Config contract tests prove required YAML is explicit and strict.
- Live exchange mutation is disabled by default and enabled only by explicit
  production config.
- Execution modes are tested separately: state-only, paper/UAT, and live.
- Pre-trade risk controls are implemented and tested: max order notional, max
  position exposure, max leverage, price/size precision, liquidity checks, and
  order rejection behavior.
- Kill-switch behavior is implemented, tested, and operator-accessible.
- Reconciliation is implemented and tested for missing fills, partial fills,
  stale orders, unexpected positions, and exchange/API failures.
- Order lifecycle is auditable from signal through intent, order submission,
  fill, cancel, close, and report.
- API keys are scoped by environment, withdrawals are disabled, and live keys are
  not present in dev/UAT.
- Reports and alerts prove the system is observable enough to diagnose failures.
- The strategy has passed offline backtests, replay/stress tests, and a paper or
  very-small-capital canary period.

If any item is missing, the next correct task is to implement the missing gate,
not to increase capital.

## Secrets And External Systems

- Secrets live outside YAML strategy/config files and are loaded through typed
  settings.
- Do not print secrets, tokens, or raw credentials.
- Network integration tests must be explicitly marked and separated from offline
  tests.

## Agent Workflow

- Read existing code before designing changes.
- Keep edits focused on the requested behavior.
- Preserve unrelated user changes.
- Do not use destructive git commands unless explicitly requested.
- When touching architecture, use the vocabulary in
  `.agents/skills/improve-quant-architecture/references/LANGUAGE.md`.
