import streamlit as st
import plotly.express as px
import pandas as pd

def render_correlation_heatmap(corr_matrix: pd.DataFrame, corr_candidates: pd.DataFrame):
    """
    Renders the correlation heatmap and the top candidates table.
    """
    st.write("### Step 1 Results: Correlation Matrix")
    st.info("Visual validation of asset relationships over the selected lookback.")
    
    fig = px.imshow(
        corr_matrix, 
        color_continuous_scale="RdBu_r", 
        zmin=-1, zmax=1,
        aspect="auto"
    )
    st.plotly_chart(fig, use_container_width=True)
    
    st.write(f"**Top {len(corr_candidates)} Candidates Selected:**")
    st.dataframe(
        corr_candidates.style.format({'Correlation': "{:.2f}"}),
        use_container_width=True
    )
