import streamlit as st
import pandas as pd
from datetime import datetime
from src.data.fetcher import fetch_data
from src.data.universe import UniverseManager

def render_downloader_tab():
    st.markdown("Fetch historical data.")
    
    # Needs EXCHANGES list from main layout or re-import
    # For now, let's redefine minimal or pass as args. 
    # Better to import shared constant if possible, but let's keep it simple.
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
    
    # 1. Exchange Selection
    col_ex, col_sym, col_tf = st.columns([1, 1, 1])
    with col_ex:
        exchange_options = {e['name']: e['id'] for e in EXCHANGES}
        selected_exchange_name = st.selectbox("Exchange", list(exchange_options.keys()))
        selected_exchange_id = exchange_options[selected_exchange_name]
    
    with col_sym:
        # Dynamic Symbol Loading logic would go here
        # Simplified for refactor
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
        # Fetch Logic (Copied from original data_page.py)
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())
        
        st.write("### 📟 Terminal Output")
        terminal_placeholder = st.empty()
        logs = []
        
        def log_callback(pct, msg):
            timestamp = datetime.now().strftime("%H:%M:%S")
            logs.append(f"[{timestamp}] {msg}")
            terminal_content = "\n".join(logs)
            terminal_placeholder.code(terminal_content, language="text")

        try:
            with st.spinner(f"Connecting to {selected_exchange_name}..."):
                fetch_data(selected_exchange_id, symbol, timeframe, start_dt, end_dt, log_callback)
            st.success("Download Complete!")
        except Exception as e:
            st.error(f"Failed: {str(e)}")
