import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple, Union
from src.engine.core.types import Side, TradeType

class VectorizedEngine:
    """
    High-performance Vectorized Backtester.
    
    Key Features:
    - Vectorized operations (Pandas/NumPy) for speed.
    - Support for Compounding (Growth) vs Linear (Fixed) capital.
    - Built-in Cost Modeling (Fees + Slippage).
    - Handling of Funding Rates for Perps.
    """
    
    def __init__(
        self, 
        initial_capital: float = 10_000.0,
        fee_rate: float = 0.0005,  # 0.05% per trade
        slippage: float = 0.0001,  # 0.01% estimated slippage
        compounding: bool = True,
        rebalance_mode: str = 'signal' # 'signal' or 'bar'
    ):
        self.initial_capital = initial_capital
        self.fee_rate = fee_rate
        self.slippage = slippage
        self.compounding = compounding
        self.rebalance_mode = rebalance_mode
        self.total_cost_rate = self.fee_rate + self.slippage
        
        # State Tracking for Deep Inspector
        self._prices_cache = None
        self._weights_cache = None
        self._equity_cache = None

    def run(
        self, 
        prices: pd.DataFrame, 
        target_weights: pd.DataFrame, 
        funding_rates: Optional[pd.DataFrame] = None,
        stop_loss_pct: Optional[float] = None,
    ) -> pd.DataFrame:
        """
        Executes the backtest.
        
        Args:
            prices: DataFrame of Close prices (aligned).
            target_weights: DataFrame of target portfolio weights (-1.0 to 1.0).
            funding_rates: DataFrame of funding rates (aligned).
            
        Returns:
            stats_df: DataFrame containing Equity, PnL, Costs, etc. per bar.
        """
        # 1. Align Data
        # Ensure weights match price index
        weights = target_weights.reindex(prices.index).fillna(0.0)
        
        if funding_rates is None:
            funding_rates = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
        else:
            funding_rates = funding_rates.reindex(prices.index).fillna(0.0)

        # 2. Shift Signals (Execution Delay)
        # Signal at Close t -> Trade at Open t+1
        # In vector land: We hold the position determined at t-1 during bar t.
        # Position_t = Weight_{t-1}
        allocated_weights = weights.shift(1).fillna(0.0)
        
        # Cache for Trade Inspector Extraction
        self._prices_cache = prices
        self._weights_cache = allocated_weights
        
        # 3. Handle Rebalancing Logic
        if self.rebalance_mode == 'signal':
            # Only change weights if they explicitly changed in the signal
            # This prevents rebalancing just because price moved (reducing turnover)
            # Logic: If Weight_t == Weight_{t-1}, maintain previous *physical* exposure?
            # Actually, "Signal Based" usually means we stick to the target weight derived from signal.
            # If standard vector backtest, we assume we rebalance to target every bar.
            # Minimizing turnover requires a buffer or logic to "drift".
            # For "Signal Mode": We forward fill the previous weight if the new weight is identical?
            # Or simplified: if strategy outputs same weight, we still re-balance to that weight.
            # To strictly NOT trade, we need 'Drift' mode provided by user.
            # Let's assume standard rebalance to target for now, but optimization can be done in signal generation.
            pass

        # 4. Calculate Asset Returns
        # Return_t = (Price_t - Price_{t-1}) / Price_{t-1}
        asset_returns = prices.pct_change().fillna(0.0)
        
        # 5. Calculate Portfolio Returns (Gross)
        # Port_Ret_t = Sum(Weight_{t-1, i} * Asset_Ret_{t, i})
        # Note: This assumes linear return approximation. For log returns it's different.
        # Linear is standard for PnL.
        weighted_returns = allocated_weights * asset_returns
        gross_returns = weighted_returns.sum(axis=1)
        
        # 6. Deduct Funding Costs
        # Funding Cost = Position_Value * Funding_Rate
        # Approx: Weight * Funding_Rate (since Weight ~ Position/Equity)
        # We pay funding if Long, Receive if Short? 
        # Crypto Rules: Long pays Short if Rate > 0.
        # Cost = Position * Rate. (If Long (+1) and Rate > 0, Cost > 0 (Expense))
        # Logic: PnL -= Position * Rate
        funding_costs = (allocated_weights * funding_rates).sum(axis=1)
        
        # 7. Calculate Turnover & Transaction Costs
        # Turnover = |Weight_t - Weight_{t-1}|
        # We trade to get from allocated_weights[t-1] (post-drift) to allocated_weights[t].
        # Simplify: Delta = |allocated_weights - allocated_weights.shift(1)|
        current_weights = allocated_weights
        previous_weights = current_weights.shift(1).fillna(0.0)
        
        turnover = (current_weights - previous_weights).abs().sum(axis=1)
        transaction_costs = turnover * self.total_cost_rate
        
        # 8. Net Returns
        net_returns = gross_returns - funding_costs - transaction_costs
        
        # 9. Equity Curve
        if self.compounding:
            # Equity_t = Equity_{t-1} * (1 + Net_Ret_t)
            equity_curve = self.initial_capital * (1 + net_returns).cumprod()
        else:
            # Equity_t = Initial + Sum(Net_Ret_t * Initial)
            # Fixed capital allocation
            equity_curve = self.initial_capital + (net_returns * self.initial_capital).cumsum()
            
        # ------------------------------------------------------------------
        # 10. OPTIONAL: Per-Trade Equity Stop-Loss (post-process)
        # ------------------------------------------------------------------
        self._stop_events = []  # list of (stop_bar_ts, trade_entry_ts)

        if stop_loss_pct is not None and stop_loss_pct > 0:
            allocated_weights, equity_curve, net_returns, transaction_costs, turnover = (
                self._apply_stop_loss(
                    prices, allocated_weights, asset_returns,
                    funding_rates, equity_curve, stop_loss_pct,
                )
            )

        # 11. Compile Stats
        self._equity_cache = equity_curve
        self._weights_cache = allocated_weights
        
        active_bars = (allocated_weights.abs().sum(axis=1) > 0.0)
        time_in_market_bars = active_bars.sum()
        total_bars = len(prices)
        time_in_market_pct = (time_in_market_bars / total_bars) * 100 if total_bars > 0 else 0.0
        
        results = pd.DataFrame({
            'equity': equity_curve,
            'returns': net_returns,
            'gross_returns': gross_returns,
            'cost_funding': funding_costs,
            'cost_trading': transaction_costs,
            'turnover': turnover,
            'drawdown': (equity_curve / equity_curve.cummax() - 1)
        })
        
        results.attrs['time_in_market_pct'] = time_in_market_pct
        results.attrs['total_bars'] = total_bars
        results.attrs['active_bars'] = time_in_market_bars
        results.attrs['stop_events'] = self._stop_events
        
        return results

    # ------------------------------------------------------------------
    # Stop-Loss Post-Process
    # ------------------------------------------------------------------

    def _apply_stop_loss(
        self, prices, allocated_weights, asset_returns,
        funding_rates, equity_curve, stop_pct,
    ):
        """
        Post-process pass: for each round-trip trade, check if intra-trade
        drawdown exceeds stop_pct. If so, zero the weights from the stop
        bar onward and recompute equity.

        Returns updated (allocated_weights, equity_curve, net_returns,
        transaction_costs, turnover).
        """
        weights = allocated_weights.copy()
        is_active = weights.abs().sum(axis=1) > 0

        # Find trade boundaries: groups of consecutive active bars
        trade_groups = (is_active != is_active.shift()).cumsum()
        trade_groups = trade_groups[is_active]

        modified = False

        for _, group_idx in trade_groups.groupby(trade_groups):
            entry_bar = group_idx.index[0]

            # Equity at the bar BEFORE the trade opens (the capital we risk)
            entry_loc = equity_curve.index.get_loc(entry_bar)
            entry_equity = equity_curve.iloc[entry_loc - 1] if entry_loc > 0 else self.initial_capital

            # Scan bars within this trade
            for bar in group_idx.index:
                bar_equity = equity_curve.loc[bar]
                dd = (bar_equity - entry_equity) / entry_equity

                if dd < -stop_pct:
                    # Stop triggered: zero weights from this bar onward until trade ends
                    remaining_bars = group_idx.index[group_idx.index >= bar]
                    weights.loc[remaining_bars] = 0.0
                    self._stop_events.append((bar, entry_bar))
                    modified = True
                    break  # move to next trade

        if not modified:
            net_returns = (weights * asset_returns).sum(axis=1)
            funding_costs = (weights * funding_rates).sum(axis=1)
            prev_w = weights.shift(1).fillna(0.0)
            turnover = (weights - prev_w).abs().sum(axis=1)
            transaction_costs = turnover * self.total_cost_rate
            return weights, equity_curve, net_returns, transaction_costs, turnover

        # Recompute everything with modified weights
        net_returns = self._compute_net_returns(weights, asset_returns, funding_rates)
        if self.compounding:
            equity_curve = self.initial_capital * (1 + net_returns).cumprod()
        else:
            equity_curve = self.initial_capital + (net_returns * self.initial_capital).cumsum()

        prev_w = weights.shift(1).fillna(0.0)
        turnover = (weights - prev_w).abs().sum(axis=1)
        transaction_costs = turnover * self.total_cost_rate

        return weights, equity_curve, net_returns, transaction_costs, turnover

    def _compute_net_returns(self, weights, asset_returns, funding_rates):
        """Recompute net returns from weights (used after stop-loss modifies weights)."""
        gross = (weights * asset_returns).sum(axis=1)
        funding = (weights * funding_rates).sum(axis=1)
        prev_w = weights.shift(1).fillna(0.0)
        turnover = (weights - prev_w).abs().sum(axis=1)
        costs = turnover * self.total_cost_rate
        return gross - funding - costs

    # ------------------------------------------------------------------
    # Trade History Reconstruction
    # ------------------------------------------------------------------

    def get_trade_history(self) -> pd.DataFrame:
        """
        Reconstructs discrete trade list from vector weights.
        Returns a rich Pandas DataFrame detailing every transactional event.
        """
        if self._weights_cache is None or self._prices_cache is None:
            return pd.DataFrame()
            
        # We find exactly where weights change (Delta != 0)
        weight_deltas = self._weights_cache.diff().fillna(self._weights_cache.iloc[0])
        
        trades = []
        
        # Iterate over columns (assets) finding non-zero deltas
        for asset in weight_deltas.columns:
            asset_deltas = weight_deltas[asset]
            trade_mask = asset_deltas != 0.0
            
            # Filter the exact dates trades happened
            trade_dates = asset_deltas[trade_mask].index
            
            for t in trade_dates:
                delta_w = asset_deltas.loc[t]
                
                # Determine Side
                side = "BUY" if delta_w > 0 else "SELL"
                
                # Get pricing
                price = self._prices_cache.loc[t, asset]
                
                # Get Account Balance at time of execution (previous bar close approx)
                # If t is not the first bar, get equity from previous bar, else intial
                prev_idx = self._equity_cache.index.get_loc(t) - 1
                if prev_idx >= 0:
                    exec_capital = self._equity_cache.iloc[prev_idx]
                else:
                    exec_capital = self.initial_capital
                    
                # Calculate Notional Value (Size of trade in $)
                # Delta Weight * Total Capital
                notional = abs(delta_w) * exec_capital
                
                # Fee Paid
                fee_paid = notional * self.fee_rate
                
                # Slippage Cost (approximate hidden cost)
                slippage_cost = notional * self.slippage
                
                trades.append({
                    "Date": t,
                    "Asset": asset,
                    "Action": side,
                    "Price": price,
                    "Delta Weight": delta_w,
                    "Notional ($)": round(notional, 2),
                    "Fees Paid ($)": round(fee_paid, 2),
                    "Target Weight (Post)": self._weights_cache.loc[t, asset],
                    "Current Equity ($)": round(exec_capital, 2)
                })
                
        # Create DataFrame and sort chronologically
        trades_df = pd.DataFrame(trades)
        if not trades_df.empty:
            trades_df = trades_df.sort_values(by=["Date", "Asset"]).reset_index(drop=True)
            
        return trades_df
