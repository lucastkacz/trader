import streamlit as st

def apply_compact_styles():
    """
    Injects custom CSS for a more compact, professional look.
    Reduces padding, header sizes, and font sizes.
    """
    st.markdown("""
        <style>
        .block-container { padding-top: 2rem; padding-bottom: 2rem; }
        h1 { font-size: 1.8rem !important; margin-bottom: 0rem !important; }
        h2 { font-size: 1.4rem !important; margin-top: 1rem !important; margin-bottom: 0.5rem !important; }
        h3 { font-size: 1.1rem !important; margin-top: 0.5rem !important; margin-bottom: 0.5rem !important; }
        .stButton button { padding: 0.2rem 1rem; }
        div[data-testid="stDataFrame"] { font-size: 0.8rem; }
        /* Reduce sidebar padding */
        section[data-testid="stSidebar"] > div { padding-top: 2rem; }
        </style>
    """, unsafe_allow_html=True)
