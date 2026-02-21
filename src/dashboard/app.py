import streamlit as st

st.set_page_config(page_title="Quant Panel", layout="wide")

st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Data Management", "Research"])

if page == "Data Management":
    from src.dashboard.pages.data.layout import render_data_page
    render_data_page()
elif page == "Research":
    from src.dashboard.pages.research.layout import render_research_page
    render_research_page()
