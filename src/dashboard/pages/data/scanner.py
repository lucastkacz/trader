import streamlit as st
import pandas as pd
from datetime import datetime
from src.data.fetcher import fetch_data, fetch_top_markets
from src.data.universe import UniverseManager
import json
from src.dashboard.pages.data import EXCHANGES

# Assuming EXCHANGES is defined elsewhere, e.g., in a config or constants file
# For the purpose of this edit, I'll add a placeholder if it's not in the original content.
# If EXCHANGES is not defined, this code will cause an error.
# Let's assume it's available globally or imported.
# Example placeholder for EXCHANGES if it's not in the original file:
# EXCHANGES = [
#     {"id": "binance", "name": "Binance"},
#     {"id": "bybit", "name": "Bybit"},
#     {"id": "okx", "name": "OKX"},
# ]

def render_scanner_tab():
    st.subheader("Market Scanner & Batch Fetcher")
    
    # Defaults
    selected_exchange_id = "binance" 
    
    # Determine default index from session state (shared with Downloader)
    default_idx = 0
    if 'selected_exchange_name' in st.session_state:
        try:
             # Find index of saved name in current list
             names = [e['name'] for e in EXCHANGES]
             if st.session_state['selected_exchange_name'] in names:
                 default_idx = names.index(st.session_state['selected_exchange_name'])
        except ValueError:
            pass

    col1, col2 = st.columns([1, 1])
    
    with col1:
        # Construct options map
        exchange_options = {e['name']: e['id'] for e in EXCHANGES}
        selected_exchange_name = st.selectbox("Exchange", list(exchange_options.keys()), index=default_idx, key="scanner_exchange_select")
        selected_exchange_id = exchange_options[selected_exchange_name]
        
        # Update session state if changed here too
        if selected_exchange_name != st.session_state.get('selected_exchange_name'):
             st.session_state['selected_exchange_name'] = selected_exchange_name
             st.session_state['selected_exchange_id'] = selected_exchange_id
    
    with col2:
        limit_scan = st.slider("Scan Limit", 10, 100, 20)
        
    if st.button(f"🔍 Scan Top Markets"):
        with st.spinner("Fetching market ticker data..."):
            top_markets = fetch_top_markets(selected_exchange_id, limit=limit_scan)
            if not top_markets.empty:
                top_markets.insert(0, "Select", False)
                st.session_state['scan_results'] = top_markets
            else:
                st.warning("No data returned.")

    # Display Results
    if 'scan_results' in st.session_state and st.session_state['scan_results'] is not None:
        st.divider()
        st.write("### 1. Select Pairs")
        
        edited_df = st.data_editor(
            st.session_state['scan_results'],
            use_container_width=True,
            height=400,
            hide_index=True,
            column_config={
                "Select": st.column_config.CheckboxColumn("Select", default=False),
                "Price": st.column_config.NumberColumn("Price", format="%.4f"),
            }
        )
        
        selected_rows = edited_df[edited_df["Select"] == True]
        count = len(selected_rows)
        st.write(f"**Selected:** {count} pairs")
        
        st.divider()
        st.write("### 2. Configure & Fetch")
        
        bc1, bc2, bc3 = st.columns(3)
        with bc1:
            batch_tf = st.selectbox("Batch Timeframe", ["1m", "5m", "15m", "1h", "4h", "1d"], index=3, key="batch_tf")
        with bc2:
            batch_start = st.date_input("Start Date", value=datetime(2024, 1, 1), key="batch_start")
        with bc3:
            batch_end = st.date_input("End Date", value=datetime.now(), key="batch_end")
            
        col_fetch, col_universe = st.columns(2)
        
        if col_fetch.button("🚀 Fetch Selected Pairs", type="primary", disabled=(count == 0)):
            # Batch Fetch Logic
            start_dt = datetime.combine(batch_start, datetime.min.time())
            end_dt = datetime.combine(batch_end, datetime.max.time())
            
            st.write("### 📟 Terminal Output")
            terminal_placeholder = st.empty()
            logs = []
            
            # Simple progress tracking
            prog_bar = st.progress(0)
            
            def log_callback(pct, msg):
                logs.append(msg)
                terminal_placeholder.code("\n".join(logs[-10:]), language="text")

            success_symbols = []
            for i, row in enumerate(selected_rows.itertuples()):
                sym = row.Symbol
                prog_bar.progress((i) / count)
                try:
                    fetch_data(selected_exchange_id, sym, batch_tf, start_dt, end_dt, progress_callback=log_callback)
                    success_symbols.append(sym)
                except Exception as e:
                    log_callback(0, f"Error {sym}: {e}")
                    
            prog_bar.progress(1.0)
            st.success(f"Fetched {len(success_symbols)}/{count} pairs.")
            
            # Store success list for Universe creation
            st.session_state['last_batch_success'] = {
                "symbols": success_symbols,
                "timeframe": batch_tf,
                "start": batch_start,
                "end": batch_end
            }

        # Universe Creation Button (Appears after fetch)
        if 'last_batch_success' in st.session_state:
            st.divider()
            st.write("### 3. Save as Universe")
            batch_data = st.session_state['last_batch_success']
            
            u_name = st.text_input("Universe Name", value=f"Batch_Scan_{datetime.now().strftime('%Y%m%d')}")
            
            if st.button("💾 Save Universe Configuration"):
                try:
                    path = UniverseManager.save_universe(
                        name=u_name,
                        symbols=batch_data['symbols'],
                        timeframe=batch_data['timeframe'],
                        start_date=batch_data['start'],
                        end_date=batch_data['end'],
                        description=f"Created from Market Scanner batch fetch of {len(batch_data['symbols'])} assets."
                    )
                    st.success(f"Universe saved to {path}!")
                except Exception as e:
                    st.error(f"Failed to save universe: {e}")
