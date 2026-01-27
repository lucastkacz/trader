import streamlit as st
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

# Lazy import to avoid circular dependency issues if any
from src.data.fetcher import fetch_data, fetch_top_markets, update_dataset
import shutil

# List of exchanges provided by user
EXCHANGES = [
    {"id": "binance", "name": "Binance"},
    {"id": "binanceusdm", "name": "Binance USDⓈ-M"},
    {"id": "binancecoinm", "name": "Binance COIN-M"},
    {"id": "bybit", "name": "Bybit"},
    {"id": "kucoin", "name": "KuCoin"},
    {"id": "kucoinfutures", "name": "KuCoin Futures"},
    {"id": "bitmex", "name": "BitMEX"},
]

from src.dashboard.styles import apply_compact_styles
from src.data.fetcher import fetch_data, fetch_top_markets, update_dataset, get_available_symbols

@st.cache_data(ttl=3600)
def load_symbols(exchange_id):
    return get_available_symbols(exchange_id)

def render_data_page():
    # Apply shared styles
    apply_compact_styles()

    st.title("Data Management")

    tab_download, tab_scan = st.tabs(["⬇️ Downloader", "🔍 Market Scanner"])

    # --- TAB 1: DOWNLOADER (Existing Logic) ---
    with tab_download:
        st.markdown("Fetch historical data.")
        
        # 1. Exchange Selection
        col_ex, col_sym, col_tf = st.columns([1, 1, 1])
        with col_ex:
            exchange_options = {e['name']: e['id'] for e in EXCHANGES}
            selected_exchange_name = st.selectbox("Exchange", list(exchange_options.keys()))
            selected_exchange_id = exchange_options[selected_exchange_name]
        
        with col_sym:
            # Dynamic Symbol Loading
            with st.spinner("Loading markets..."):
                available_symbols = load_symbols(selected_exchange_id)
            
            if available_symbols:
                # Try to set reasonable default
                default_idx = 0
                if "BTC/USDT" in available_symbols:
                    default_idx = available_symbols.index("BTC/USDT")
                elif "BTC/USD" in available_symbols:
                    default_idx = available_symbols.index("BTC/USD")
                    
                symbol = st.selectbox("Symbol", available_symbols, index=default_idx)
            else:
                # Fallback if API fails
                symbol = st.text_input("Symbol", value="BTC/USDT")
                
        with col_tf:
            timeframe = st.selectbox("Timeframe", ["1m", "5m", "15m", "1h", "4h", "1d"], index=3)

        # 3. Time Range
        col_start, col_end, col_btn = st.columns([1, 1, 1])
        with col_start:
            start_date = st.date_input("Start Date", value=datetime(2024, 1, 1))
        with col_end:
            end_date = st.date_input("End Date", value=datetime.now())
        with col_btn:
            st.write("") # Spacer
            st.write("") # Spacer
            fetch_btn = st.button("Fetch Data", type="primary", use_container_width=True)

        if fetch_btn:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(pct, msg):
                safe_pct = max(0.0, min(1.0, float(pct)))
                progress_bar.progress(safe_pct)
                status_text.text(msg)

            try:
                start_dt = datetime.combine(start_date, datetime.min.time())
                end_dt = datetime.combine(end_date, datetime.max.time())
                with st.spinner(f"Connecting to {selected_exchange_name}..."):
                    fetch_data(selected_exchange_id, symbol, timeframe, start_dt, end_dt, update_progress)
                st.success("Download Complete!")
            except Exception as e:
                st.error(f"Failed: {str(e)}")

    # 5. Local Data Management
    st.markdown("---")
    st.subheader("🗄️ Local Data Management")
    
    data_dir = Path("data")
    if data_dir.exists():
        # Recursive find
        files = list(data_dir.rglob("*.parquet"))
        
        if files:
            file_records = []
            for f in files:
                # Structure: data/exchange/timeframe/symbol.parquet
                try:
                    # relative_to data/: exchange/timeframe/symbol.parquet
                    parts = f.relative_to(data_dir).parts
                    if len(parts) >= 3:
                        exchange = parts[0]
                        tf = parts[1]
                        sym = parts[2].replace(".parquet", "").replace("_", "/")
                        
                        # Quick stat for range (optional, might be slow if many files)
                        # Let's just trust metadata or read head/tail if needed. 
                        # For speed, just file stats.
                        stats = f.stat()
                        
                        file_records.append({
                            "Exchange": exchange,
                            "Timeframe": tf,
                            "Symbol": sym,
                            "Size (KB)": round(stats.st_size / 1024, 2),
                            "Modified": datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M'),
                            "path": str(f) # Hidden usage
                        })
                except Exception:
                    pass
            
            if file_records:
                df_files = pd.DataFrame(file_records)
                
                # Selection for actions
                # We use a dataframe to show info, and a selectbox for action
                st.dataframe(
                    df_files.drop(columns=["path"]), 
                    use_container_width=True, 
                    hide_index=True
                )
                
                col_act1, col_act2 = st.columns(2)
                
                with col_act1:
                    st.write("##### Actions")
                    selected_idx = st.selectbox(
                        "Select Dataset to Manage", 
                        range(len(file_records)), 
                        format_func=lambda i: f"{file_records[i]['Exchange']} - {file_records[i]['Symbol']} ({file_records[i]['Timeframe']})"
                    )
                    
                    target_file = file_records[selected_idx]
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("🔄 Complete / Update Data"):
                            status = st.empty()
                            prog = st.progress(0)
                            
                            def update_prog(p, m): 
                                prog.progress(max(min(p, 1.0), 0.0))
                                status.text(m)
                                
                            try:
                                update_dataset(
                                    target_file['Exchange'],
                                    target_file['Symbol'],
                                    target_file['Timeframe'],
                                    progress_callback=update_prog
                                )
                                st.success(f"Updated {target_file['Symbol']}!")
                            except Exception as e:
                                st.error(f"Error: {e}")

                    with c2:
                        if st.button("🗑️ Delete File", type="primary"):
                            try:
                                Path(target_file['path']).unlink()
                                st.success("Deleted file.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Could not delete: {e}")
            else:
                st.info("Found parquet files but structure didn't match 'data/exchange/timeframe/symbol.parquet'")
        else:
            st.info("No data files found.")
    else:
        st.info("Data directory does not exist.")

    # --- TAB 2: MARKET SCANNER (New Feature) ---
    with tab_scan:
        # Ensure selected_exchange_name is available from the other tab's state
        # If the user switches directly to this tab without interacting with the downloader,
        # selected_exchange_name might not be initialized.
        # A simple way to handle this is to re-initialize it or ensure the selectbox is rendered first.
        # For now, we assume it's available or default to the first exchange.
        if 'selected_exchange_name' not in locals():
            selected_exchange_name = EXCHANGES[0]['name']
            selected_exchange_id = EXCHANGES[0]['id']
        
        st.subheader(f"Top Liquid Pairs on {selected_exchange_name}")
        
        limit_scan = st.slider("Number of pairs", 10, 100, 20)
        
        if st.button(f"Scan {selected_exchange_name}"):
            with st.spinner("Fetching market ticker data..."):
                top_markets = fetch_top_markets(selected_exchange_id, limit=limit_scan)
                
            if not top_markets.empty:
                st.dataframe(
                    top_markets.style.format({
                        "Price": "{:.4f}", 
                        "24h Vol (M)": "{:.2f} M",
                        "24h Change %": "{:.2f}%"
                    }), 
                    use_container_width=True, 
                    height=500
                )
            else:
                st.warning("No data returned. Exchange might require API keys or rate limit reached.")
