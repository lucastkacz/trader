import streamlit as st
from src.dashboard.styles import apply_compact_styles

# Import sub-pages
from src.dashboard.pages.data.downloader import render_downloader_tab
from src.dashboard.pages.data.scanner import render_scanner_tab
from src.dashboard.pages.data.universe import render_universe_tab
from src.dashboard.pages.data.manager import render_manager_tab
from src.dashboard.pages.data.qc import render_qc_tab
from src.dashboard.pages.data.baskets import render_baskets_tab

def render_data_page():
    # Apply shared styles
    apply_compact_styles()

    st.title("Data Management")

    tab_download, tab_scan, tab_manage, tab_universe, tab_baskets, tab_qc = st.tabs([
        "⬇️ Downloader", "🔍 Market Scanner", "🗄️ File Manager", "🌌 Universes", "🗃️ Baskets", "🕵️ QC & Inspect"
    ])

    with tab_download:
        render_downloader_tab()
    
    with tab_scan:
        render_scanner_tab()
        
    with tab_manage:
        render_manager_tab()

    with tab_universe:
        render_universe_tab()
        
    with tab_baskets:
        render_baskets_tab()
        
    with tab_qc:
        render_qc_tab()

