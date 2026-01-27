import streamlit as st
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

# Lazy import to avoid circular dependency issues if any
from src.data.fetcher import fetch_data, fetch_top_markets

# List of exchanges provided by user
EXCHANGES = [
    {"id": "binance", "name": "Binance"},
    {"id": "binanceusdm", "name": "Binance USDⓈ-M"},
    {"id": "binancecoinm", "name": "Binance COIN-M"},
    {"id": "bybit", "name": "Bybit"},
    {"id": "okx", "name": "OKX"},
    {"id": "gate", "name": "Gate"},
    {"id": "kucoin", "name": "KuCoin"},
    {"id": "kucoinfutures", "name": "KuCoin Futures"},
    {"id": "bitget", "name": "Bitget"},
    {"id": "hyperliquid", "name": "Hyperliquid"},
    {"id": "bitmex", "name": "BitMEX"},
    {"id": "bingx", "name": "BingX"},
    {"id": "htx", "name": "HTX"},
    {"id": "mexc", "name": "MEXC Global"},
    {"id": "bitmart", "name": "BitMart"},
    {"id": "cryptocom", "name": "Crypto.com"},
    {"id": "coinex", "name": "CoinEx"},
    {"id": "hashkey", "name": "HashKey Global"},
    {"id": "woo", "name": "WOO X"},
    {"id": "woofipro", "name": "WOOFI PRO"},
]

def render_data_page():
    # Compact CSS Injection
    st.markdown("""
        <style>
        .block-container { padding-top: 2rem; padding-bottom: 2rem; }
        h1 { font-size: 1.8rem !important; margin-bottom: 0rem !important; }
        h2 { font-size: 1.4rem !important; margin-top: 1rem !important; margin-bottom: 0.5rem !important; }
        h3 { font-size: 1.1rem !important; margin-top: 0.5rem !important; margin-bottom: 0.5rem !important; }
        .stButton button { padding: 0.2rem 1rem; }
        div[data-testid="stDataFrame"] { font-size: 0.8rem; }
        </style>
    """, unsafe_allow_html=True)

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

        # 5. Existing Data View
        st.markdown("---")
        st.subheader("Local Files")
        data_dir = Path("data")
        if data_dir.exists():
            files = list(data_dir.glob("*.parquet"))
            if files:
                file_data = []
                for f in files:
                    stats = f.stat()
                    file_data.append({
                        "Filename": f.name,
                        "Size (KB)": round(stats.st_size / 1024, 2),
                        "Date": datetime.fromtimestamp(stats.st_ctime).strftime('%Y-%m-%d %H:%M')
                    })
                st.dataframe(pd.DataFrame(file_data), use_container_width=True, height=200)
            else:
                st.info("No files.")

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
