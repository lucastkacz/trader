import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from src.data.universe import UniverseManager
from src.data.fetcher import storage, get_available_symbols
from pathlib import Path

def render_qc_tab():
    st.subheader("🕵️ Data Quality Control")
    
    # 1. Source Selection
    source_mode = st.radio("Select Source", ["Universe", "Single File"], horizontal=True)
    result_mode = source_mode # Capture for later use
    
    selected_files = []
    
    if source_mode == "Universe":
        universes = UniverseManager.list_universes()
        if not universes:
            st.warning("No Universes found.")
            return
            
        u_names = [u['name'] for u in universes]
        sel_u = st.selectbox("Select Universe", u_names, key="qc_universe_select")
        config = next((u for u in universes if u['name'] == sel_u), None)
        
        if config:
            # Reconstruct file paths
            # This assumes data follows strict naming convention managed by fetcher
            base_dir = Path("data") / config.get('data_source', 'binance') / config['timeframe']
            for sym in config['symbols']:
                safe_sym = sym.replace('/', '_')
                f_path = base_dir / f"{safe_sym}.parquet"
                if f_path.exists():
                    selected_files.append((sym, f_path))
            
            st.info(f"Checking {len(selected_files)} / {len(config['symbols'])} available files.")

    else:
        # Single file picker (simplified)
        data_dir = Path("data")
        if data_dir.exists():
            all_files = list(data_dir.rglob("*.parquet"))
            # Sort by mod time desc
            all_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            file_map = {f"{f.parent.parent.name}/{f.parent.name}/{f.name}": f for f in all_files}
            sel_f_key = st.selectbox("Select File", list(file_map.keys()))
            if sel_f_key:
                # Extract symbol name roughly or just use key
                selected_files.append((sel_f_key, file_map[sel_f_key]))

    st.session_state.qc_results = None

    if selected_files:
        check_btn = st.button("Run QC Check")
    else:
        st.warning("No files selected to check.")
        check_btn = False

    if check_btn:
        st.session_state.qc_results = [] # Reset on new run
        
        progress = st.progress(0)
        
        for i, (sym, f_path) in enumerate(selected_files):
            progress.progress(i / len(selected_files))
            try:
                # We need to read the index to check gaps
                # Reading just the index is faster than full file
                df = pd.read_parquet(f_path, columns=[]) # Empty columns might not work with some engines, but usually reads index
                # Actually, reading columns=[] often returns DataFrame with index only if index is preserved
                # Let's read 'close' just to be safe and cheap
                df = pd.read_parquet(f_path, columns=['close'])
                
                if df.empty:
                    st.session_state.qc_results.append({
                        "Symbol": sym, "Rows": 0, "Start": None, "End": None, "Continuity": 0.0
                    })
                    continue
                    
                # Check Gaps
                # Infer expected freq?
                # For now, just simplistic stats
                
                rows = len(df)
                start = df.index.min()
                end = df.index.max()
                
                # Check for Funding Rate presence
                has_funding = False
                try:
                    # Check columns available in parquet without reading all
                     pq_file = storage.pq.ParquetFile(f_path)
                     if 'fundingRate' in pq_file.schema.names:
                         has_funding = True
                except:
                    pass

                st.session_state.qc_results.append({
                    "Symbol": sym,
                    "Rows": rows,
                    "Start": start,
                    "End": end,
                    "Has Funding": "✅" if has_funding else "❌"
                })
                
            except Exception as e:
                pass
                
        progress.progress(1.0)
        
        progress.progress(1.0)
        
        st.write("### QC Report")
        
        qc_results = st.session_state.qc_results
        
        if qc_results:
            df_res = pd.DataFrame(qc_results)
            st.dataframe(df_res, use_container_width=True)
            
            # Gantt chart for universe?
            if result_mode == "Universe" and 'Start' in df_res.columns and 'End' in df_res.columns:
                fig = px.timeline(df_res, x_start="Start", x_end="End", y="Symbol", title="Data Coverage Intervals")
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(fig, use_container_width=True)

        # --- Single File Inspector ---
        if result_mode == "Single File" and selected_files and st.session_state.qc_results:
             st.divider()
             st.write("### 🔬 Detailed Inspector")
             
             # We should have only one file in this mode
             sym, f_path = selected_files[0]
             
             try:
                 # Load data efficiently? 
                 # Maybe just last 1000 candles for performance
                 df_insp = pd.read_parquet(f_path)
                 
                 # Create Subplots: Candlestick + Funding
                 from plotly.subplots import make_subplots
                 
                 has_funding = 'fundingRate' in df_insp.columns
                 
                 fig = make_subplots(
                     rows=2 if has_funding else 1, 
                     cols=1, 
                     shared_xaxes=True, 
                     vertical_spacing=0.05,
                     row_heights=[0.7, 0.3] if has_funding else [1.0],
                     subplot_titles=(f"{sym} Price Action", "Funding Rate") if has_funding else (f"{sym} Price Action",)
                 )
                 
                 # Candlestick
                 fig.add_trace(go.Candlestick(
                     x=df_insp.index,
                     open=df_insp['open'],
                     high=df_insp['high'],
                     low=df_insp['low'],
                     close=df_insp['close'],
                     name='OHLC'
                 ), row=1, col=1)
                 
                 # Funding
                 if has_funding:
                     fig.add_trace(go.Bar(
                         x=df_insp.index, 
                         y=df_insp['fundingRate'], 
                         name='Funding Rate', 
                         marker_color='orange'
                     ), row=2, col=1)
                     
                 fig.update_layout(height=600, xaxis_rangeslider_visible=False)
                 st.plotly_chart(fig, use_container_width=True)
                 
             except Exception as e:
                 st.error(f"Could not load chart: {e}")
            

