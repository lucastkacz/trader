# stat-arb

Clean rebuild of an exchange-agnostic statistical-arbitrage research and
trading platform.

## Current Status

The active branch contains project setup and architecture documentation only.
No Research V2 production code, CLI, trader, deployment, or supported operator
workflow exists yet.

The first objective is a deterministic offline research flow that produces a
typed and auditable candidate pair-set artifact. See:

- [`.agents/AGENTS.md`](.agents/AGENTS.md)
- [`docs/_IMPLEMENTATION_AGENT_GUIDE.md`](docs/_IMPLEMENTATION_AGENT_GUIDE.md)
- [`docs/index.md`](docs/index.md)
- [`docs/RESEARCH.md`](docs/RESEARCH.md)
- [`docs/PAIRS.md`](docs/PAIRS.md)
- [`docs/MARKET_DATA.md`](docs/MARKET_DATA.md)
- [`docs/EXCHANGE.md`](docs/EXCHANGE.md)
- [`docs/TRADING.md`](docs/TRADING.md)
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md)
- [`docs/INTERFACES.md`](docs/INTERFACES.md)
- [`docs/CORE.md`](docs/CORE.md)
- [`docs/current-roadmap.md`](docs/current-roadmap.md)

## Repository Layout

```text
src/stat_arb/   future installable Python package
tests/          future V2 behavior tests
configs/        future operator configuration after typed contracts exist
docs/           canonical design and roadmap
```

The previous implementation is frozen at tag `legacy-v1-before-rewrite` and in
the sibling worktree `/Users/lucastkacz/Documents/quant-v1-reference`. V2 will
use it as reference material but will not import it or pursue automatic feature
parity.

## Safety

There is currently no supported Observe, Paper, Demo Exchange, or Production
Exchange path. Research must remain read-only with respect to exchanges. The
production-capital phase in `docs/_IMPLEMENTATION_AGENT_GUIDE.md`, the Trading
gates, and Lucas's explicit authorization remain mandatory for any capital use.
