# Market Generation

Synthetic market generation should be random enough to expose path dependency
and deterministic enough to debug every failure.

## Library Strategy

Use focused scientific Python libraries for primitives:

- `numpy` for vectorized random paths and transforms.
- `pandas` for OHLCV frames, indexes, parquet-friendly data shapes, and time
  alignment.
- `scipy` for distributions, calibration helpers, and statistical utilities.
- `statsmodels` for cointegration and time-series diagnostics where useful.
- `numba` only for hot kernels after the NumPy implementation is correct and
  profiled.

Avoid adopting heavy backtesting engines as generation dependencies. Libraries
such as vectorized backtesters or event-driven trading frameworks can inspire
data-feed, event, and plotting ideas, but synthetic market generation should
remain small, transparent, and specific to this platform's pair-trading
verification needs.

## Randomness Rule

Every generator must accept a seed.

```python
rng = np.random.default_rng(seed)
```

Every failing randomized scenario must report the seed and scenario id.

## Work In Log Prices

Most pair simulations should operate in log-price space:

```text
log_y[t] = base process
spread[t] = mean-reverting process
log_x[t] = alpha + beta * log_y[t] + spread[t]
price_x[t] = exp(log_x[t])
price_y[t] = exp(log_y[t])
```

This makes percentage moves natural and keeps prices positive unless a data
quality fault intentionally violates that rule.

## Geometric Brownian Motion

Use GBM for base asset paths:

```text
dlog_price = (mu - 0.5 * sigma^2) * dt + sigma * sqrt(dt) * epsilon
```

Controls:

- Drift.
- Volatility.
- Time step.
- Seed.
- Initial price.

Use cases:

- Baseline asset movement.
- Trend regimes.
- Volatility shifts.

## Ornstein-Uhlenbeck Spread

Use OU for mean-reverting spreads:

```text
spread[t+1] = spread[t] + theta * (mu - spread[t]) * dt
              + sigma * sqrt(dt) * epsilon
```

Controls:

- Mean.
- Reversion speed.
- Volatility.
- Initial spread.
- Shocked spread.

Use cases:

- Normal cointegrated pairs.
- Slow natural exit.
- Spread stuck away from mean.
- Recovery after shock.

## Cointegrated Pair Generator

Inputs:

- `asset_x`
- `asset_y`
- `alpha`
- `beta`
- `base_process`
- `spread_process`

Outputs:

- OHLCV for asset X.
- OHLCV for asset Y.
- Research baseline fields.
- True spread.
- True z-score.

Baseline fields should include:

- Research window start.
- Research window end.
- Research bars.
- Hedge ratio.
- Correlation.
- Spread mean.
- Spread standard deviation.
- Half-life estimate when available.
- Cointegration p-value when available.

## Regime Switching

Regime switches should alter parameters over bar intervals.

Examples:

- Increase `spread_sigma`.
- Decrease `theta`.
- Change `beta`.
- Replace cointegrated leg with independent GBM.
- Add jump diffusion.

Regime changes should be recorded in scenario metadata.

## Jump Diffusion

Jump diffusion can create rare extreme moves:

```text
return = normal_return + jump_indicator * jump_size
```

Controls:

- Jump probability.
- Jump size distribution.
- Target symbols.
- Start/end bars.

Use cases:

- Flash crashes.
- Gap moves.
- Stressing order/risk logic.

## Fat-Tail Returns

Student-t or mixture distributions can create heavier tails than Gaussian GBM.

Use cases:

- Tail-risk scenarios.
- Unexpected z-score spikes.
- Whipsaw around thresholds.

## OHLCV Builder

The first generator can build OHLCV from close prices:

```text
open[t] = close[t-1]
high[t] = max(open[t], close[t]) * (1 + wick_noise)
low[t]  = min(open[t], close[t]) * (1 - wick_noise)
volume[t] = base_volume * lognormal_noise
```

Requirements:

- UTC timestamps.
- Monotonic timestamps by default.
- Positive high/low consistency by default.
- Explicit fault injection for malformed bars.
- Per-symbol metadata.

Generated OHLCV should be written to parquet for replay and diagnostics when a
scenario output config enables it. This keeps simulation close to the existing
market-data storage shape and lets pair-validity/reporting code exercise the
same storage assumptions used elsewhere in the platform.

## Data Quality Faults

Faults should be applied after valid OHLCV generation.

Fault categories:

- Missing bars.
- Duplicate bars.
- Out-of-order bars.
- Stale symbol.
- NaN close.
- Zero close.
- Negative close.
- Extreme outlier.
- Missing volume.
- Zero volume.
- Mismatched timestamp alignment.

Faults should record:

- Affected symbols.
- Affected bars.
- Fault type.
- Expected system behavior.

## Scenario Examples

### Slow Natural Exit

```text
bars 0-120: normal cointegrated pair
bar 121: spread shock crosses entry threshold
bars 122-260: theta near zero, spread remains open
bars 261-330: recovery, spread returns to mean
expected: signal exit, no forced close
```

### Queue Invalidation

```text
bars 0-100: valid promoted pair
bars 101-180: correlation breakdown
pair validity flags operator review
queue blocks future entries
existing position still receives signal evaluation
```

### Missing Leg Data

```text
bars 0-100: normal data
bars 101-140: asset Y missing bars
expected: no unsafe entry, pair-validity notes missing data
```
