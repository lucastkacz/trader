import streamlit as st
import pandas as pd
import plotly.express as px
from src.engine.core.engine import VectorizedEngine

def render_execution(df_pair: pd.DataFrame, signals: pd.DataFrame, rolling_beta: pd.Series, 
                     asset_a: str, asset_b: str, capital: float, fee_rate: float, slippage: float):
    """
    Renders Module 4: Engine Execution.
    Translates the filtered Long/Short signals into Target Portfolio Weights,
    runs the Vectorized Engine, and visualizes the Final Equity Curve.
    """
    st.write("### 💵 Module 4: Engine Execution")
    st.markdown(
        "Translating Signals into **Target Portfolio Weights** and simulating real-world execution "
        "complete with exchange fees and slippage."
    )
    
    if signals.empty or df_pair.empty:
        st.warning("No signals available to execute.")
        return

    with st.spinner("Executing Vectorized Backtest..."):
        # 1. Translate Signals to Weights
        pos = signals['filtered_position']
        
        # We need a Weights DataFrame mapping exact Assets to their Target Percentage (-1.0 to 1.0+)
        weights = pd.DataFrame(0.0, index=df_pair.index, columns=df_pair.columns)
        
        # When Long Spread (pos = +1): Buy A, Sell B (* Beta)
        # When Short Spread (pos = -1): Sell A, Buy B (* Beta)
        weights[asset_a] = pos
        weights[asset_b] = pos * (-rolling_beta)
        
        # Clean up NaNs
        weights = weights.fillna(0.0)
        
        # 2. Initialize Engine
        engine = VectorizedEngine(
            initial_capital=capital,
            fee_rate=fee_rate,
            slippage=slippage
        )
        
        # 3. Run Strategy
        # (The VectorizedEngine accepts the raw df directly right now, let's just pass it)
        try:
            results_df = engine.run(df_pair, weights)
        except Exception as e:
            st.error(f"Engine failed to execute: {e}")
            return
            
    # Calculate KPIs
    final_equity = results_df['equity'].iloc[-1]
    total_return = (final_equity / capital - 1) * 100
    peak = results_df['equity'].cummax()
    drawdown = (results_df['equity'] - peak) / peak * 100
    max_dd = drawdown.min()
    
    # Simple Sharpe (Annualized approx for hours)
    returns = results_df['equity'].pct_change().dropna()
    mean_ret = returns.mean()
    std_ret = returns.std()
    sharpe = (mean_ret / std_ret) * (8760 ** 0.5) if std_ret > 0 else 0.0 # 8760 hours in a year
    
    # 4. KPI Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Final Equity", f"${final_equity:,.2f}", f"{total_return:,.2f}%")
    col2.metric("Sharpe Ratio", f"{sharpe:.2f}")
    col3.metric("Max Drawdown", f"{max_dd:.2f}%")
    
    # Count exact number of trades taken (where position flipped)
    trades_taken = (pos != pos.shift(1)).sum() - 1 # Subtract 1 for initial 0
    if trades_taken < 0: trades_taken = 0
    col4.metric("Trades Executed", f"{trades_taken}")

    # 5. Equity Curve Plot
    fig = px.line(
        results_df, 
        x=results_df.index, 
        y='equity', 
        title="Strategy Equity Curve (Net of Fees & Slippage)"
    )
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Equity ($)",
        template="plotly_dark",
        hovermode="x unified",
        margin=dict(l=40, r=40, t=40, b=40)
    )
    
    # Shade the area under the curve
    fig.update_traces(fill='tozeroy', line_color='#00E676')
    
    st.plotly_chart(fig, use_container_width=True)
