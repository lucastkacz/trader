import streamlit as st

st.set_page_config(page_title="Quant Panel", layout="wide")

# Sidebar Navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Data Manager", "Visualizer"])

if page == "Data Manager":
    from src.dashboard.pages.data_page import render_data_page
    render_data_page()
    
elif page == "Visualizer":
    from src.dashboard.pages.viz_page import render_viz_page
    render_viz_page()
