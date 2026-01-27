import streamlit as st

def render_price_history(df):
    """
    Renders the raw price history chart.
    """
    st.subheader("Price History")
    st.line_chart(df)

def render_normalized_prices(df):
    """
    Renders prices normalized to start at 1.0.
    """
    st.subheader("Normalized Prices (Start = 1.0)")
    normalized_df = df / df.iloc[0]
    st.line_chart(normalized_df)
