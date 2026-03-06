import streamlit as st
import plotly.express as px
import pandas as pd

def render_returns_histogram(corr_returns: pd.DataFrame):
    """
    Renders the Log Returns Distribution Analysis section with a dropdown for assets and a histogram.
    """
    st.divider()

    st.write("### Análisis de Distribución de Retornos (Log Returns)")
    st.info("Revisa visualmente si los retornos del activo seleccionado se asemejan a una distribución normal (Campana de Gauss), lo cual es ideal para métodos como Pearson.")
    
    with st.expander("🎓 Entendiendo los Momentos de la Distribución (Leer Primero)", expanded=False):
        st.markdown("""
        **1. Media (Mean)**
        *   **¿Qué es?** El promedio aritmético de todos los retornos.
        *   **¿Qué implica?** En finanzas, la media diaria de los retornos suele ser muy cercana a cero. Nos dice hacia dónde tiende el activo en el largo plazo.

        **2. Volatilidad (Desviación Estándar)**
        *   **¿Qué es?** Mide qué tan dispersos están los retornos alrededor de la media.
        *   **¿Qué implica?** Es la medida clásica de riesgo. Una mayor volatilidad significa que la campana es más ancha y "aplastada", indicando movimientos de precio más bruscos.

        **3. Asimetría (Skewness)**
        *   **¿Qué es?** Mide la falta de simetría en la distribución. Una distribución Normal perfecta tiene Skewness = 0.
        *   **¿Qué implica?**
            *   `Skew < 0` (Cola Larga Izquierda): Mayor riesgo de caídas fuertes y repentinas. Los retornos negativos extremos son más probables.
            *   `Skew > 0` (Cola Larga Derecha): Mayor probabilidad de subidas abruptas.

        **4. Curtosis (Kurtosis)**
        *   **¿Qué es?** Mide el "grosor" de las colas de la distribución comparado con una Normal. Aquí mostramos el *Exceso de Curtosis*, por lo que una Normal perfecta tiene Kurtosis = 0.
        *   **¿Qué implica?**
            *   `Kurtosis > 0` (Leptocúrtica): "Colas gordas". El precio hace movimientos salvajes y extremos con más frecuencia de lo normal. Es la regla, no la excepción, en cripto.
            *   `Kurtosis < 0` (Platicúrtica): Menos eventos extremos y datos más concentrados cerca de la media.
        """)
    
    available_assets = list(corr_returns.columns) if corr_returns is not None else []
    
    col_hist_1, col_hist_2 = st.columns([1, 2])
    with col_hist_1:
         selected_hist_asset = st.selectbox("Seleccionar Activo", available_assets)
         bins = st.slider("Número de Bins (Resolución)", min_value=10, max_value=200, value=50)
         
    with col_hist_2:
         if selected_hist_asset and corr_returns is not None:
             hist_data = corr_returns[selected_hist_asset].dropna()
             
             import scipy.stats as stats
             import numpy as np
             import plotly.graph_objects as go
             
             # Create base histogram with marginal box plot
             fig_hist = px.histogram(
                  hist_data, 
                  x=selected_hist_asset,
                  nbins=bins,
                  marginal="box", # Restored the box plot
                  histnorm="probability density", # Normalized for KDE
                  color_discrete_sequence=['#00bfff'] # Vibrant deep sky blue
             )
             
             # Add borders to the bars for visual pop
             fig_hist.update_traces(marker_line_width=1, marker_line_color="rgba(0,0,0,0.2)", opacity=0.8, selector=dict(type='histogram'))
             
             # Calculate and add custom colored KDE curve
             try:
                 kde = stats.gaussian_kde(hist_data)
                 x_kde = np.linspace(hist_data.min(), hist_data.max(), 500)
                 y_kde = kde(x_kde)
                 
                 # Add KDE as a separate line trace (orange/red to stand out)
                 fig_hist.add_trace(go.Scatter(
                     x=x_kde, 
                     y=y_kde, 
                     mode='lines', 
                     line=dict(color='#ff4500', width=2.5), # OrangeRed color
                     name='Curva KDE',
                     hoverinfo='skip'
                 ))
             except Exception as e:
                 pass # If KDE fails for any reason (e.g. not enough variance), just show histogram
             
             
             # Calculate numerical statistics for normality
             mean_ret = hist_data.mean()
             std_ret = hist_data.std()
             skew_ret = hist_data.skew()
             kurt_ret = hist_data.kurt()
             
             fig_hist.update_layout(
                  title=f"<b>Distribución {selected_hist_asset}</b><br><sup>Media: {mean_ret:.6f} | Volatilidad: {std_ret:.6f} | Asimetría (Skew): {skew_ret:.2f} | Curtosis: {kurt_ret:.2f}</sup>",
                  xaxis_title="Retorno Logarítmico",
                  yaxis_title="Frecuencia",
                  showlegend=False
             )
             
             # Add a vertical dotted line at zero for reference
             fig_hist.add_vline(x=0, line_width=2, line_dash="dot", line_color="rgba(0,0,0,0.5)")
             
             st.plotly_chart(fig_hist, use_container_width=True)
