import streamlit as st
import plotly.express as px

def render_zscore(zscore_series, window):
    """
    Renders the Z-Score chart with bands using Plotly.
    """
    st.subheader(f"Z-Score ({window} periods)")
    
    fig = px.line(zscore_series, title="Z-Score")
    fig.add_hline(y=2.0, line_dash="dash", line_color="red")
    fig.add_hline(y=-2.0, line_dash="dash", line_color="green")
    fig.add_hline(y=0.0, line_dash="dash", line_color="gray")
    
    st.plotly_chart(fig, use_container_width=True)
