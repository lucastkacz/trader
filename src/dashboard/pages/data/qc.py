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
    
    selected_files = []
    
    if source_mode == "Universe":
        universes = UniverseManager.list_universes()
        if not universes:
            st.warning("No Universes found.")
            return
            
        u_names = [u['name'] for u in universes]
        sel_u = st.selectbox("Select Universe", u_names)
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

    if not selected_files:
        return

    check_btn = st.button("Run QC Check")
    
    if check_btn:
        qc_results = []
        
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
                    qc_results.append({
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

                qc_results.append({
                    "Symbol": sym,
                    "Rows": rows,
                    "Start": start,
                    "End": end,
                    "Has Funding": "✅" if has_funding else "❌"
                })
                
            except Exception as e:
                pass
                
        progress.progress(1.0)
        
        st.divider()
        st.write("### QC Report")
        
        if qc_results:
            df_res = pd.DataFrame(qc_results)
            st.dataframe(df_res, use_container_width=True)
            
            # Simple Visuals
            # Gantt chart of start/end?
            if 'Start' in df_res.columns and 'End' in df_res.columns:
                fig = px.timeline(df_res, x_start="Start", x_end="End", y="Symbol", title="Data Coverage Intervals")
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(fig, use_container_width=True)
            
        # Drill Down Inspector
        st.divider()
        st.write("### 🔬 Inspector")
        
        insp_sym = st.selectbox("Inspect Symbol", [s[0] for s in selected_files])
        target_path = next((f for s, f in selected_files if s == insp_sym), None)
        
        if target_path:
            # Load tail
            df_insp = pd.read_parquet(target_path)
            st.write("#### Last 5 Rows")
            st.dataframe(df_insp.tail())
            
            st.write("#### Chart")
            # Dual axis: Close + Funding
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_insp.index, y=df_insp['close'], name='Close', line=dict(color='blue')))
            
            if 'fundingRate' in df_insp.columns:
                # Funding rate is often small, put on secondary axis
                # Or just plot underneath?
                # Secondary axis is better
                fig.add_trace(go.Bar(x=df_insp.index, y=df_insp['fundingRate'], name='Funding Rate', marker_color='red', yaxis='y2'))
                
            fig.update_layout(
                yaxis2=dict(overlaying='y', side='right', title='Funding Rate'),
                height=500,
                title=f"{insp_sym} Price & Funding"
            )
            st.plotly_chart(fig, use_container_width=True)

