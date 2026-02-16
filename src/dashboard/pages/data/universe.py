import streamlit as st
from datetime import datetime
from src.data.universe import UniverseManager
from src.data.fetcher import fetch_data

def render_universe_tab():
    st.subheader("🌌 Universe Management")
    
    # Tabs for Manage vs Create
    tab_manage, tab_create = st.tabs(["Manage Existing", "Create New"])
    
    with tab_manage:
        # 1. List Existing Universes
        universes = UniverseManager.list_universes()
        
        if not universes:
            st.info("No Universes found.")
        else:
            # Select Universe to Manage
            universe_names = [u['name'] for u in universes]
            selected_name = st.selectbox("Select Universe", universe_names, key="univ_manage_sel")
            
            # Find full config
            selected_config = next((u for u in universes if u['name'] == selected_name), None)
            
            if selected_config:
                # --- Preview ---
                with st.expander("Values", expanded=False):
                    st.json(selected_config)

                # --- Edit Form ---
                st.write(f"### Editing: {selected_name}")
                
                with st.form(key="edit_universe_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        new_desc = st.text_input("Description", value=selected_config.get("description", ""))
                        new_tf = st.text_input("Timeframe", value=selected_config.get("timeframe", "1h"))
                    
                    with col2:
                        # Parse existing dates
                        try:
                            s_date = datetime.strptime(selected_config['range']['start'], "%Y-%m-%d %H:%M:%S")
                            e_date = datetime.strptime(selected_config['range']['end'], "%Y-%m-%d %H:%M:%S")
                        except:
                            s_date = datetime.now()
                            e_date = datetime.now()
                            
                        new_start = st.date_input("Start Date", value=s_date)
                        new_end = st.date_input("End Date", value=e_date)
                    
                    # Symbol Editing
                    st.write("#### Symbols")
                    current_syms = selected_config.get("symbols", [])
                    sym_text = st.text_area("Symbols (comma separated)", value=", ".join(current_syms), height=150)
                    
                    # Save Button
                    if st.form_submit_button("💾 Save Changes"):
                         # Process updates
                         updated_syms = [s.strip() for s in sym_text.split(",") if s.strip()]
                         
                         updates = {
                             "description": new_desc,
                             "timeframe": new_tf,
                             "range": {
                                 "start": datetime.combine(new_start, datetime.min.time()).strftime("%Y-%m-%d %H:%M:%S"),
                                 "end": datetime.combine(new_end, datetime.min.time()).strftime("%Y-%m-%d %H:%M:%S")
                             },
                             "symbols": updated_syms
                         }
                         
                         if UniverseManager.update_universe(selected_config['filename'], updates):
                             st.success("Universe updated successfully!")
                             st.rerun()
                         else:
                             st.error("Failed to update universe.")
                
                st.divider()
                
                # Delete & Fetch Actions
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("🗑️ Delete Universe", key="del_univ_btn"):
                        UniverseManager.delete_universe(selected_config['filename'])
                        st.success("Deleted!")
                        st.rerun()

                with c2:
                    if st.button("🚀 Fetch Data", key="fetch_univ_btn"):
                        st.info("Starting batch fetch...")
                        # ... (existing fetch logic could go here or be imported)
                        # Reusing logic for brevity
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
                                fetch_data(exchange, sym, tf, start_dt, end_dt)
                            except Exception as e:
                                st.error(f"Failed {sym}: {e}")
                                
                        prog_bar.progress(1.0)
                        st.success("Done!")

    with tab_create:
        st.subheader("Create New Universe")
        
        with st.form("create_universe_form"):
            new_name = st.text_input("Universe Name")
            new_desc = st.text_input("Description")
            
            c_tf, c_src = st.columns(2)
            with c_tf:
                new_tf = st.text_input("Timeframe", value="1h")
            with c_src:
                new_src = st.selectbox("Data Source", ["binance", "kraken"], index=0)
            
            c_d1, c_d2 = st.columns(2)
            with c_d1:
                new_start = st.date_input("Start Date", value=datetime(2023, 1, 1))
            with c_d2:
                new_end = st.date_input("End Date", value=datetime.now())
                
            new_syms_text = st.text_area("Symbols (comma separated)", placeholder="BTC/USDT, ETH/USDT")
            
            if st.form_submit_button("✨ Create Universe"):
                if not new_name:
                    st.error("Name is required.")
                else:
                    syms = [s.strip() for s in new_syms_text.split(",") if s.strip()]
                    if not syms:
                        st.error("At least one symbol is required.")
                    else:
                        UniverseManager.save_universe(
                            name=new_name,
                            symbols=syms,
                            timeframe=new_tf,
                            start_date=datetime.combine(new_start, datetime.min.time()),
                            end_date=datetime.combine(new_end, datetime.min.time()),
                            description=new_desc,
                            exchange_id=new_src
                        )
                        st.success(f"Universe '{new_name}' created!")
                        st.rerun()
