import streamlit as st
from src.dashboard.styles import apply_compact_styles

# Import sub-pages
from src.dashboard.pages.data.downloader import render_downloader_tab
from src.dashboard.pages.data.scanner import render_scanner_tab
from src.dashboard.pages.data.universe import render_universe_tab

def render_data_page():
    # Apply shared styles
    apply_compact_styles()

    st.title("Data Management")

    tab_download, tab_scan, tab_universe = st.tabs(["⬇️ Downloader", "🔍 Market Scanner", "🌌 Universes"])

    with tab_download:
        render_downloader_tab()
    
    with tab_scan:
        render_scanner_tab()
        
    with tab_universe:
        render_universe_tab()

