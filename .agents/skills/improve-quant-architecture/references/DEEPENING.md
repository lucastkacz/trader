# Deepening Reference

Use this when turning shallow modules into deeper modules.

## Dependency Categories

**In-process**: pure computation or in-memory state. Deepenable directly. Test through the new module interface.

**Local-substitutable**: local filesystem, SQLite, Parquet, or clock-like dependencies with a realistic test stand-in. Deepenable if tests can use the stand-in.

**True external**: exchanges, Telegram, internet APIs, and other systems not controlled by the repo. Use a small injected interface at the seam and provide a production adapter plus a test adapter or mock.

**Runtime state**: live positions, reconciliation state, command state, or active order lifecycle. Deepen carefully; state transitions and persistence expectations are part of the interface.

## Testing Strategy

- Replace scattered internal tests with behavior tests at the deeper module interface.
- Tests assert observable outcomes: returned values, persisted artifacts, emitted events, state transitions, and error modes.
- Tests must not call networks.
- Tests should survive internal refactors.

## Quant-Specific Shapes

Good deepening candidates usually gather one domain behavior:

- Artifact validation, freshness, schema, candidate promotion, and load errors.
- Pair recalculation policy separated from live position mutation.
- Config parsing and typed config objects before runtime code sees values.
- Exchange precision and order payload construction behind an execution-facing interface.
- Reconciliation as state transition behavior, not scattered dictionary mutation.

Avoid creating adapters for every pure function. In-process math usually needs a deep function or class with clear invariants, not a port.
