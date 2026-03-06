import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from src.dashboard.styles import apply_compact_styles
from src.data.universe import UniverseManager
from src.engine.data.loader import DataLoader
from src.stats.correlation import calculate_correlation_matrix, get_top_correlated_pairs
from src.data.basket import BasketManager
from src.dashboard.pages.correlation.components.heatmap import render_correlation_heatmap
from src.dashboard.pages.correlation.components.histogram import render_returns_histogram

def render_correlation_page():
    # Apply shared styles
    apply_compact_styles()

    st.title("Correlation Analysis")
    st.markdown("Filter your universe down to statically correlated pairs that move together historically.")

    # 1. Universe Selection
    st.write("### Data Selection")
    
    universes = UniverseManager.list_universes()
    if not universes:
        st.warning("No universes found. Please create one in Data Management.")
        return

    universe_names = [u.get("name", "Unknown") for u in universes]
    
    col_u1, col_u2 = st.columns([1, 2])
    with col_u1:
        selected_u_name = st.selectbox("Select Universe", universe_names)
    
    selected_universe = next((u for u in universes if u.get("name") == selected_u_name), None)
    
    timeframe = "1h" # Default
    if selected_universe:
        timeframe = selected_universe.get('timeframe', '1h')
        with col_u2:
            st.write("") # Add spacing to align with selectbox
            st.write("")
            st.markdown(f"**Symbols:** {len(selected_universe.get('symbols', []))} &nbsp;&nbsp;|&nbsp;&nbsp; **Timeframe:** {timeframe}")
        
    st.divider()
    
    # Timeframe Conversion Helper
    def get_time_estimate(periods: int, tf_str: str) -> str:
        try:
            if tf_str.endswith('m'):
                mins = int(tf_str[:-1]) * periods
                if mins < 60: return f"{mins} minutes"
                hours = mins / 60
                if hours < 24: return f"{hours:.1f} hours"
                return f"{(hours / 24):.2f} days"
            elif tf_str.endswith('h'):
                hours = int(tf_str[:-1]) * periods
                if hours < 24: return f"{hours} hours"
                return f"{(hours / 24):.2f} days"
            elif tf_str.endswith('d'):
                days = int(tf_str[:-1]) * periods
                if days < 30: return f"{days} days"
                return f"{(days / 30):.1f} months"
            return f"{periods} periods"
        except:
            return f"{periods} periods"
    
    # 2. Correlation Parameters
    st.write("### Filter Parameters")
    
    with st.expander("🎓 Entendiendo los Métodos de Correlación (Leer Primero)", expanded=False):
        st.markdown("""
        **1. Retornos Logarítmicos**
        Primero, calculamos el retorno compuesto continuo (Retorno Logarítmico) para cada activo:
        $$R_{t} = \\ln(\\frac{P_t}{P_{t-1}})$$
        Esto asegura que los retornos sean simétricos, aditivos, y previene la correlación espuria que ocurre al comparar precios absolutos.

        **2. Métodos de Correlación**
        *   **Pearson (Lineal):** Mide la relación lineal entre dos activos. Asume que los retornos se distribuyen normalmente. Es el estándar de la industria para el pairs trading general, pero es altamente sensible a valores atípicos extremos (flash crashes).
        *   **Spearman (Basado en Rangos):** Método no paramétrico que mide relaciones monotónicas. Clasifica (rankea) los retornos en lugar de usar valores absolutos. 
            *   *Pros:* Robusto frente a valores atípicos y captura relaciones no lineales.
            *   *Cons:* Puede ser más lento y ligeramente menos preciso para modelos lineales perfectos.
        *   **Kendall (Tau):** También basado en rangos, pero mide la probabilidad de concordancia (¿si uno sube, el otro también sube?).
            *   *Pros:* El más robusto contra el ruido y valores atípicos en muestras pequeñas.
            *   *Cons:* Computacionalmente el más costoso. Recomendado para datos con mucho ruido.
        """)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        corr_lookback = st.number_input("Correlation Lookback (Periods)", min_value=30, value=672, help="The historical window over which to measure correlation.")
        st.caption(f"⏱️ Analyzing deep history over the last **{get_time_estimate(corr_lookback, timeframe)}**")
        
    with col2:
        top_n = st.number_input("Test Top N Pairs", min_value=1, value=15, help="How many highly correlated pairs to extract for your Basket.")

    with col3:
        corr_method = st.selectbox("Correlation Method", ["pearson", "spearman", "kendall"], index=0)

    st.divider()
    
    st.write("### Normality Pre-Filter (For Pearson)")
    st.markdown("Exclude assets that severely violate normality assumptions (e.g. extreme *flash crashes*) before calculating Pearson correlation, as they can cause spurious high correlations.")
    
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        use_prefilter = st.checkbox("Enable Normality Pre-Filter", value=True, help="Recommended if using Pearson. Disabling this includes all assets regardless of their distribution.")
    with col_f2:
        max_skew = st.number_input("Max Absolute Skewness", min_value=0.5, value=2.0, step=0.1, help="Tolerance for asymmetry. A perfect normal distribution is 0.")
    with col_f3:
        max_kurtosis = st.number_input("Max Excess Kurtosis", min_value=1.0, value=7.0, step=0.5, help="Tolerance for 'fat tails' (extreme events). A perfect normal distribution is 0. Crypto naturally has higher values.")

    st.divider()

    # Session State Management
    if 'corr_matrix' not in st.session_state:
        st.session_state.corr_matrix = None
    if 'corr_candidates' not in st.session_state:
        st.session_state.corr_candidates = None
    if 'corr_start_date' not in st.session_state:
        st.session_state.corr_start_date = None
    if 'corr_end_date' not in st.session_state:
        st.session_state.corr_end_date = None
    if 'corr_method_used' not in st.session_state:
        st.session_state.corr_method_used = None
    if 'corr_filtered_assets' not in st.session_state:
        st.session_state.corr_filtered_assets = []

    # 3. Execution: Correlation
    if st.button("📊 Run Correlation Filter", type="primary", use_container_width=True):
        if not selected_universe or 'symbols' not in selected_universe:
            st.error("Invalid Universe.")
            return
            
        symbols = selected_universe['symbols']
        
        with st.spinner(f"Loading {get_time_estimate(corr_lookback, timeframe)} of data and building heatmaps..."):
            try:
                # Load Data
                loader = DataLoader(symbols, timeframe)
                close_df, _, _ = loader.load()
                
                if close_df.empty:
                    st.error("No data found.")
                    return
                    
                recent_df = close_df.tail(corr_lookback)
                st.session_state.corr_start_date = str(close_df.index[0].date())
                st.session_state.corr_end_date = str(close_df.index[-1].date())
                st.session_state.corr_method_used = corr_method
                
                # Pre-calculate log returns for both the filter and the histogram
                log_returns_unfiltered = np.log(recent_df / recent_df.shift(1)).dropna(how='all')
                log_returns = log_returns_unfiltered.copy()
                
                filtered_assets_log = []
                
                # Apply Normality Pre-Filter
                if use_prefilter:
                    assets_to_keep = []
                    for col in log_returns.columns:
                        col_data = log_returns[col].dropna()
                        if col_data.empty: continue
                        
                        asset_skew = col_data.skew()
                        asset_kurtosis = col_data.kurt()
                        
                        is_valid = True
                        reasons = []
                        if abs(asset_skew) > max_skew:
                            is_valid = False
                            reasons.append(f"Skewness ({asset_skew:.2f})")
                        if asset_kurtosis > max_kurtosis:
                            is_valid = False
                            reasons.append(f"Kurtosis ({asset_kurtosis:.2f})")
                            
                        if is_valid:
                            assets_to_keep.append(col)
                        else:
                            filtered_assets_log.append(f"**{col}**: Eliminado por alta {' y '.join(reasons)}.")
                    
                    # Update dataframes with only surviving assets for the correlation matrix
                    recent_df = recent_df[assets_to_keep]
                    log_returns = log_returns[assets_to_keep]
                
                st.session_state.corr_filtered_assets = filtered_assets_log
                # Keep ALL returns for the histogram so user can inspect excluded assets
                st.session_state.corr_returns = log_returns_unfiltered 
                
                st.session_state.corr_matrix = calculate_correlation_matrix(recent_df, method=corr_method)
                st.session_state.corr_candidates = get_top_correlated_pairs(st.session_state.corr_matrix, top_n=top_n)
                
            except Exception as e:
                st.error(f"Correlation check failed: {str(e)}")

    if st.session_state.corr_matrix is not None and st.session_state.corr_candidates is not None:
        
        # 4. Returns Distribution Analysis (Shows ALL assets, including excluded)
        if hasattr(st.session_state, 'corr_returns') and st.session_state.corr_returns is not None:
             render_returns_histogram(st.session_state.corr_returns)

        # Display Filter Log AFTER the histogram
        if st.session_state.corr_filtered_assets:
            with st.expander(f"⚠️ {len(st.session_state.corr_filtered_assets)} activos fueron excluidos del análisis por el Pre-Filtro estadístico.", expanded=False):
                st.info("Pista: Puedes buscar estos activos en el histograma de arriba para visualizar su comportamiento anómalo.")
                for log_msg in st.session_state.corr_filtered_assets:
                    st.markdown(f"- {log_msg}")

        st.divider()

        render_correlation_heatmap(st.session_state.corr_matrix, st.session_state.corr_candidates)

        st.divider()
        
        # Save Basket Form
        st.write("### Save Correlated Basket")
        st.info("Save this first pass of highly correlated pairs to a Basket. You can load this basket in Alpha Discovery to test specific strategies.")
        
        col_name, col_btn = st.columns([3, 1])
        with col_name:
            basket_name = st.text_input("Basket Name", value=f"Correlated_{selected_u_name}_{top_n}")
        with col_btn:
            st.write("") # Spacing
            st.write("")
            if st.button("💾 Save Correlated Basket", use_container_width=True):
                 if basket_name:
                      # Convert candidates to the dict structure expected by BasketManager
                      # Currently dataframe columns are Asset_1, Asset_2, Correlation
                      pairs_list = []
                      for _, row in st.session_state.corr_candidates.iterrows():
                          pairs_list.append({
                              'asset_a': row['Asset_1'],
                              'asset_b': row['Asset_2'],
                              'correlation': row['Correlation'],
                          })
                          
                      saved_path = BasketManager.save_basket(
                          name=basket_name,
                          pairs=pairs_list,
                          universe_name=selected_u_name,
                          timeframe=timeframe,
                          basket_type="correlated",
                          metadata={
                              "correlation_method": st.session_state.corr_method_used,
                              "correlation_lookback_periods": corr_lookback,
                              "data_start_date": st.session_state.corr_start_date,
                              "data_end_date": st.session_state.corr_end_date
                          }
                      )
                      st.success(f"Basket saved successfully! Head over to Alpha Discovery.")
                 else:
                      st.warning("Please provide a name for the basket.")

