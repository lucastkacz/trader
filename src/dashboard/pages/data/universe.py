import streamlit as st
from datetime import datetime
from src.data.universe import UniverseManager
from src.data.fetcher import fetch_data

def render_universe_tab():
    st.subheader("🌌 Universe Management")
    
    # 1. List Existing Universes
    universes = UniverseManager.list_universes()
    
    if not universes:
        st.info("No Universes found. Create one from the Scanner tab or manually below.")
    else:
        st.write(f"Found {len(universes)} universes.")
        
        # Select Universe to Manage
        universe_names = [u['name'] for u in universes]
        selected_name = st.selectbox("Select Universe", universe_names)
        
        # Find full config
        selected_config = next((u for u in universes if u['name'] == selected_name), None)
        
        if selected_config:
            with st.expander("Values", expanded=True):
                st.json(selected_config)
                
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🗑️ Delete Universe"):
                    UniverseManager.delete_universe(f"{selected_config['filename']}") # Use stored filename
                    st.success("Deleted!")
                    st.rerun()

            with c2:
                # "Import/Fetch" Feature as requested by user
                if st.button("🚀 Fetch All Data for Universe"):
                    st.info("Starting batch fetch for this universe...")
                    
                    # Reconstruction of fetch logic
                    start_dt = datetime.strptime(selected_config['range']['start'], "%Y-%m-%d %H:%M:%S")
                    end_dt = datetime.strptime(selected_config['range']['end'], "%Y-%m-%d %H:%M:%S")
                    symbols = selected_config['symbols']
                    tf = selected_config['timeframe']
                    exchange = selected_config.get('data_source', 'binance')
                    
                    progress_text = st.empty()
                    prog_bar = st.progress(0)
                    
                    for i, sym in enumerate(symbols):
                        progress_text.text(f"Fetching {sym} ({i+1}/{len(symbols)})...")
                        prog_bar.progress(i / len(symbols))
                        try:
                            # We don't really need a detailed log callback here, just blocking
                            fetch_data(exchange, sym, tf, start_dt, end_dt)
                        except Exception as e:
                            st.error(f"Failed {sym}: {e}")
                            
                    prog_bar.progress(1.0)
                    st.success("All data fetched successfully!")

    st.divider()
    st.subheader("Create Manual Universe")
    st.warning("Manual creation UI pending... use Market Scanner for now.")
