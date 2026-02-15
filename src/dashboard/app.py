import streamlit as st
from src.dashboard.pages.data.layout import render_data_page

st.set_page_config(page_title="Quant Panel", layout="wide")

# Direct render - no navigation needed for single page
render_data_page()
