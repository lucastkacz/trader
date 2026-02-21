import streamlit as st
from src.dashboard.styles import apply_compact_styles
from src.data.universe import UniverseManager

def render_research_page():
    # Apply shared styles
    apply_compact_styles()

    st.title("Research & Prototyping")

    # 1. Universe Selection (Sidebar or Top Level)
    st.sidebar.header("Data Selection")
    
    universes = UniverseManager.list_universes()
    if not universes:
        st.warning("No universes found. Please create one in Data Management.")
        return

    universe_names = [u.get("name", "Unknown") for u in universes]
    selected_u_name = st.sidebar.selectbox("Select Universe", universe_names)
    
    selected_universe = next((u for u in universes if u.get("name") == selected_u_name), None)
    
    if selected_universe:
        st.sidebar.write(f"**Symbols:** {len(selected_universe.get('symbols', []))}")
        st.sidebar.write(f"**Timeframe:** {selected_universe.get('timeframe', 'Unknown')}")
        
    tab_correlation, tab_cointegration, tab_zscore = st.tabs([
        "🔗 Correlation Matrix", "⚖️ Cointegration Tests", "📈 Z-Score Analysis"
    ])

    with tab_correlation:
        from src.dashboard.pages.research.components.correlation_tab import render_correlation_tab
        render_correlation_tab(selected_universe)

    with tab_cointegration:
        from src.dashboard.pages.research.components.cointegration_tab import render_cointegration_tab
        render_cointegration_tab(selected_universe)

    with tab_zscore:
        from src.dashboard.pages.research.components.zscore_tab import render_zscore_tab
        render_zscore_tab(selected_universe)
