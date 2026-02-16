from src.data.fetcher import fetch_data, get_available_symbols
from src.data.universe import UniverseManager
from src.dashboard.pages.data import EXCHANGES

@st.cache_data(ttl=3600)
def load_symbols(exchange_id: str):
    """Cached wrapper to fetch exchange symbols."""
    return get_available_symbols(exchange_id)

def render_downloader_tab():
    st.markdown("Fetch historical data.")
    
    # 1. Exchange Selection
    col_ex, col_sym, col_tf = st.columns([1, 1, 1])
    with col_ex:
        exchange_options = {e['name']: e['id'] for e in EXCHANGES}
        
        # Determine default index from session state
        default_idx = 0
        if 'selected_exchange_name' in st.session_state:
            try:
                default_idx = list(exchange_options.keys()).index(st.session_state['selected_exchange_name'])
            except ValueError:
                pass
                
        selected_exchange_name = st.selectbox("Exchange", list(exchange_options.keys()), index=default_idx)
        selected_exchange_id = exchange_options[selected_exchange_name]
        
        # Persist selection
        st.session_state['selected_exchange_name'] = selected_exchange_name
        st.session_state['selected_exchange_id'] = selected_exchange_id
    
    with col_sym:
        # Dynamic Symbol Loading
        available_symbols = []
        with st.spinner("Loading markets..."):
            try:
                available_symbols = load_symbols(selected_exchange_id)
            except Exception:
                pass
        
        if available_symbols:
            # Smart Default
            default_index = 0
            if "BTC/USDT" in available_symbols:
                default_index = available_symbols.index("BTC/USDT")
            elif "BTC/USD" in available_symbols:
                default_index = available_symbols.index("BTC/USD")
            
            symbol = st.selectbox("Symbol", available_symbols, index=default_index)
        else:
            # Fallback
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
            st.rerun()
        except Exception as e:
            st.error(f"Failed: {str(e)}")
