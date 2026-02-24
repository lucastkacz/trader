import streamlit as st
import pandas as pd
from src.data.basket import BasketManager

def render_baskets_tab():
    st.subheader("🗃️ Alpha Baskets")
    st.markdown("Manage your statistically proven trading baskets generated from Alpha Discovery.")
    
    baskets = BasketManager.list_baskets()
    
    if not baskets:
        st.info("No saved baskets found. Go to Alpha Discovery to create one.")
        return
        
    # Build summary table
    table_data = []
    for b in baskets:
        meta = b.get("metadata", {})
        table_data.append({
            "Name": b.get("name"),
            "Universe": b.get("universe_name"),
            "Pairs": len(b.get("pairs", [])),
            "Timeframe": b.get("timeframe"),
            "Created": b.get("created_at", "").split("T")[0] if "T" in b.get("created_at", "") else "Legacy",
            "Hold Target": f"{meta.get('cointegration_window_periods', 'N/A')} Bars",
            "Data Window": f"{meta.get('data_start_date', 'N/A')} to {meta.get('data_end_date', 'N/A')}"
        })
        
    df = pd.DataFrame(table_data)
    
    # Selection and Management
    col_sel, col_del = st.columns([3, 1])
    
    with col_sel:
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.write("### Inspect Basket")
        selected_name = st.selectbox("Select a Basket to View/Delete", [b["name"] for b in baskets])
        
    selected_basket = next((b for b in baskets if b["name"] == selected_name), None)
    
    with col_del:
        if selected_basket:
            st.write("") # Spacing
            st.write("")
            st.write("")
            st.write("")
            st.error(f"**Delete {selected_name}?**")
            if st.button("🗑️ Delete Permanently", use_container_width=True):
                if BasketManager.delete_basket(selected_name):
                    st.success("Basket deleted.")
                    st.rerun()
                else:
                    st.error("Failed to delete basket.")
                    
    # Detail View
    if selected_basket:
        with st.expander("🔍 View Raw JSON Metadata", expanded=False):
            st.json(selected_basket)
            
        st.write(f"#### Contained Pairs ({len(selected_basket.get('pairs', []))})")
        pairs_df = pd.DataFrame(selected_basket.get("pairs", []))
        if not pairs_df.empty:
            # Handle legacy vs new column names gracefully
            display_cols = ['asset_a', 'asset_b', 'correlation']
            if 'p_value' in pairs_df.columns:
                display_cols.append('p_value')
            elif 'latest_p_value' in pairs_df.columns:
                display_cols.append('latest_p_value')
                
            if 'hedge_ratio' in pairs_df.columns:
                display_cols.append('hedge_ratio')
            elif 'latest_hedge_ratio' in pairs_df.columns:
                display_cols.append('latest_hedge_ratio')
                
            # Formatting
            format_dict = {'correlation': "{:.2f}"}
            for col in ['p_value', 'latest_p_value', 'hedge_ratio', 'latest_hedge_ratio']:
                if col in pairs_df.columns:
                    format_dict[col] = "{:.4f}"
                    
            st.dataframe(pairs_df[display_cols].style.format(format_dict), use_container_width=True)
