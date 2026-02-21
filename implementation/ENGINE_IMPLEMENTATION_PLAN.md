# Implementation Plan: Vectorized Engine

## Goal
Implement a modular, high-performance vectorized backtesting engine for statistical arbitrage, following the users request for detailed organization and flexibility (rebalancing/compounding).

## Proposed Structure
```
src/engine/
├── core/           # The heart of the simulation
│   ├── engine.py   # VectorizedBacktester class
│   └── types.py    # Shared Enums (Side, OrderType, etc.)
├── data/           # Data Ingestion
│   └── loader.py   # DataLoader class (Implemented)
├── strategy/       # Alpha Logic
│   └── base.py     # BaseStrategy abstract class
├── portfolio/      # Portfolio Construction
│   └── optimizer.py # Signal -> Weights logic
├── analysis/       # Performance Reporting
│   └── stats.py    # Sharpe, Drawdown, etc.
```

## Step-by-Step Implementation

### 1. Core Engine (`src/engine/core/engine.py`)
**Responsibilities**:
-   Takes `aligned_prices` and `target_weights` as input.
-   Simulates execution loop (vectorized).
-   Handles **Compounding vs Linear** capital growth.
-   Handles **Signal-based vs Bar-based** rebalancing.
-   Calculates `Capital`, `Positions`, `Trades`, `Costs`.

**Key Logic**:
```python
def run(self, prices, weights, funding_rates=None):
    # Shift weights (Signal t -> Trade t+1)
    target_pos = weights.shift(1)
    
    # Rebalancing Logic
    if self.rebalance_mode == 'signal':
        # Only change position if target changed significantly
        mask = (target_pos != target_pos.shift(1))
        target_pos = target_pos.where(mask).ffill()
        
    # Cost & PnL Calculation...
```

### 2. Strategy Interface (`src/engine/strategy/base.py`)
-   `calculate_signals(data: DataLoader) -> pd.DataFrame`

### 3. Verification Plan
-   **Unit Tests**:
    -   Create `tests/test_engine_core.py`.
    -   Test 1: **Identity**: Buy & Hold 1 Asset. Engine PnL == Asset PnL?
    -   Test 2: **Costs**: 100% Turnover every bar. Does Equity decay correctly?
    -   Test 3: **Funding**: Long Perp with high funding. Does Equity decay?

## User Review Required
-   **Rebalancing**: I will implement `rebalance_mode='signal' | 'bar'` options.
-   **Compounding**: I will implement `compounding=True | False`. 
    -   `True`: `position_size = current_equity * weight`
    -   `False`: `position_size = initial_capital * weight`
