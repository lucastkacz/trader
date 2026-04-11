import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
import pyarrow.parquet as pq
from src.data.fetcher import update_dataset

def render_manager_tab():
    st.subheader("🗄️ Local Data Manager")
    
    data_dir = Path("data")
    if not data_dir.exists():
        st.info("No data directory found.")
        return

    # Refresh Button
    if st.button("🔄 Refresh File List"):
        st.rerun()

    # 1. Scan for Files
    # Structure: data/exchange/timeframe/symbol_slash_escaped.parquet
    files = list(data_dir.rglob("*.parquet"))
    
    if not files:
        st.info("No parquet files found in `data/`.")
        return
        
    file_records = []
    for f in files:
        try:
            # Parse path parts relative to data_dir
            rel_path = f.relative_to(data_dir)
            parts = rel_path.parts
            
            # Expecting: exchange / timeframe / symbol.parquet
            if len(parts) >= 3:
                exchange = parts[0]
                tf = parts[1]
                # Reconstruct symbol from filename
                sym = parts[2].replace(".parquet", "").replace("_", "/")
                
                # Get Stats
                stats = f.stat()
                size_mb = stats.st_size / (1024 * 1024)
                mod_time = datetime.fromtimestamp(stats.st_mtime)
                
                # Read Metadata (Start/End)
                # Attempt fast read
                try:
                    meta = pq.read_metadata(f)
                    md = meta.metadata or {}
                    
                    # Try custom keys first
                    start_s = md.get(b'start_date', b'').decode('utf-8')
                    end_s = md.get(b'end_date', b'').decode('utf-8')
                    rows = md.get(b'rows', b'0').decode('utf-8')
                    
                    if not start_s:
                        # Fallback to slower row group stats if custom metadata missing
                        # (Omitted for speed unless requested, defaulting to "Unknown")
                        start_s = "Unknown"
                        end_s = "Unknown"
                except:
                    start_s, end_s, rows = "Error", "Error", "0"

                file_records.append({
                    "Exchange": exchange,
                    "Timeframe": tf,
                    "Symbol": sym,
                    "Start": start_s,
                    "End": end_s,
                    "Rows": int(rows) if rows.isdigit() else 0,
                    "Size (MB)": round(size_mb, 2),
                    "Modified": mod_time.strftime("%Y-%m-%d %H:%M"),
                    "path": str(f),
                    "Select": False 
                })
        except Exception as e:
            pass
            
    if not file_records:
        st.info("Found files but could not parse structure. Ensure data is in `data/exchange/timeframe/symbol.parquet`.")
        return

    df = pd.DataFrame(file_records)
    
    # 2. Interactive Table
    # Use data_editor to allow selection
    edited_df = st.data_editor(
        df,
        column_config={
            "Select": st.column_config.CheckboxColumn("Select", default=False),
            "Size (MB)": st.column_config.NumberColumn("Size (MB)", format="%.2f"),
            "path": None # Hide path
        },
        use_container_width=True,
        hide_index=True,
        disabled=["Exchange", "Timeframe", "Symbol", "Start", "End", "Rows", "Size (MB)", "Modified"]
    )
    
    # 3. Actions
    selected_rows = edited_df[edited_df["Select"] == True]
    count = len(selected_rows)
    
    st.write(f"**Selected:** {count} files")
    
    c1, c2, c3 = st.columns(3)
    
    with c1:
        if st.button("🔄 Complete Data (Fetch to Now)", disabled=count==0):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            success_count = 0
            for i, row in enumerate(selected_rows.itertuples()):
                # Row index is irrelevant, we use row attributes
                exch = row.Exchange
                sym = row.Symbol
                tf = row.Timeframe
                
                status_text.text(f"Updating {sym}...")
                progress_bar.progress(i / count)
                
                try:
                    # update_dataset automatically fetches from last known end_date to now
                    update_dataset(exch, sym, tf)
                    success_count += 1
                except Exception as e:
                    st.error(f"Failed to update {sym}: {e}")
            
            progress_bar.progress(1.0)
            status_text.text("Update Complete.")
            if success_count > 0:
                st.success(f"Updated {success_count} files!")
                st.rerun()

    with c2:
        if st.button("🗑️ Delete Selected", type="primary", disabled=count==0):
            deleted = 0
            for row in selected_rows.itertuples():
                try:
                    p = Path(row.path)
                    if p.exists():
                        p.unlink()
                        deleted += 1
                except Exception as e:
                    st.error(f"Could not delete {row.path}: {e}")
            
            if deleted > 0:
                st.success(f"Deleted {deleted} files.")
                st.rerun()
