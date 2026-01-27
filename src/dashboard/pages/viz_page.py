import streamlit as st
import sys
from pathlib import Path

# Project root setup
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

# Import existing viz tools
from src.data.loader import get_aligned_close_prices
from src.dashboard.charts.prices import render_price_history, render_normalized_prices
from src.dashboard.charts.zscore import render_zscore
from src.dashboard.utils import calculate_zscore 
from src.dashboard.styles import apply_compact_styles

def render_viz_page():
    apply_compact_styles()
    st.title("Visualizer")
    
    # Sidebar local to this page effectively
    st.sidebar.markdown("---")
    st.sidebar.header("Viz Settings")
    
    # We need to detect what symbols are available in the data folder?
    # For now, let's keep the manual selection but ideally we scan data/
    # But to keep it simple and working with previous logic:
    symbols = st.sidebar.multiselect(
        "Select Symbols",
        ['BTC/USDT', 'ETH/USDT'],
        default=['BTC/USDT', 'ETH/USDT']
    )

    if not symbols:
        st.warning("Please select symbols.")
        return

    # Load Data (Memoize this later)
    with st.spinner("Loading data..."):
        try:
            df = get_aligned_close_prices(symbols)
            # Limit to recent 1000 rows
            df = df.tail(1000)
        except Exception as e:
            st.error(f"Error loading data: {e}")
            return
        
    if df.empty:
        st.error("No data found for selected symbols.")
        return

    # Visuals
    render_price_history(df)
    render_normalized_prices(df)

    if len(symbols) == 2:
        st.subheader(f"Ratio: {symbols[0]} / {symbols[1]}")
        ratio = df[symbols[0]] / df[symbols[1]]
        st.line_chart(ratio)

        window = st.sidebar.slider("Z-Score Window", 24, 500, 168)
        zscore = calculate_zscore(ratio, window)
        render_zscore(zscore, window)
