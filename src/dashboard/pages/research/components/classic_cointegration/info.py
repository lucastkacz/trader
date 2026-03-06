import streamlit as st

def render_methodology_info(window: int = None, timeframe: str = None):
    window_text = f" (calculated over our **{window}-period Evaluation/Lookback Window** of {timeframe} data)" if window and timeframe else ""
    with st.expander("📚 Methodology Details: Classic Cointegration (OLS) - A Complete Mathematical Guide"):
        st.markdown(r"""
### 📊 The Ultimate Guide to Classic Cointegration (Pairs Trading)

Welcome to the **Statistical Arbitrage** engine base. This specific strategy profits when two historically correlated assets temporarily "break" their mathematical relationship, betting that they will eventually snap back together like a rubber band.

We use two distinct charts, and **you need both to trade safely**:
1. **Scatter Plot (OLS)** tells you **HOW MUCH** to buy/sell (Position Sizing & Hedge Ratio).
2. **Z-Score Spread Dynamics** tells you **WHEN** to buy/sell (The Trading Signal).

---

#### 1. The Math of the Hedge Ratio (OLS Regression)
To trade two assets neutrally, we must figure out their exact historical proportionality. We do this by running an **Ordinary Least Squares (OLS) Linear Regression** of Asset A's log-prices against Asset B's log-prices.

*   **The Equation:** 
    $$ \ln(P_{A,t}) = \beta \ln(P_{B,t}) + \alpha + \epsilon_t $$
    *   $P_{A,t}$ & $P_{B,t}$: Prices of Asset A and Asset B at time $t$. Usar logaritmos naturales ($\ln$) nos permite comparar retornos porcentuales en lugar de dólares absolutos.
    *   $\alpha$ (Alpha): El intercepto (desfase constante).
    *   **$\beta$ (Beta): El Hedge Ratio (Ratio de Cobertura).** Esta es la pendiente de la línea de regresión en tu gráfico Scatter.
    *   $\epsilon_t$: El residuo o error (el "Spread" real que vamos a operar).

*   **¿Cómo usar $\beta$?** Si nuestra regresión arroja un $ \beta = 0.5 $, significa que los retornos de Asset B son aproximadamente la mitad de volátiles que los de Asset A. Para mantenernos neutrales al mercado (protegidos ante un crash global), una posición larga de \$1,000 en Asset A **debe** cubrirse con una posición corta de \$500 (\$1000 $\times$ 0.5) en Asset B.

#### 2. The Math of Mean-Reversion (Dickey-Fuller Test)
El hecho de que dos líneas parezcan correlacionadas no garantiza que volverán a unirse tras separarse. Debemos evaluar los **residuos ($\epsilon_t$)** de nuestra regresión para comprobar si son estacionarios (tienden siempre a la media) o si son un *Random Walk* (pueden alejarse infinitamente).

*   **La Ecuación del Augmented Dickey-Fuller (ADF):**
    $$ \Delta \epsilon_t = \gamma \epsilon_{t-1} + \sum_{i=1}^{p} \delta_i \Delta \epsilon_{t-i} + u_t $$
    *   Si $\gamma = 0$, el spread es un *Random Walk* (no estacionario). Los activos a la larga se separarán y destruirán tu cuenta bancaria.
    *   Si $\gamma < 0$, el spread está **Cointegrado** (estacionario). Actúa como una banda elástica tirando hacia cero.
*   **La Decisión del P-Value:** El test ADF nos devuelve un P-Value, que es la probabilidad de que $\gamma = 0$.
    *   **P-Value $\le$ 0.05**: ¡Excelente! Como una banda elástica, cuando los activos se desincronicen, fuerzas matemáticas los volverán a unir.
    *   **P-Value > 0.05**: ¡Peligro! La banda elástica se cortó. No operes este par.

#### 3. The Math of the Z-Score (CIS-COR / El Trading Signal)
El Spread crudo o residual ($\epsilon_t = \ln(P_{A,t}) - \beta \ln(P_{B,t}) - \alpha$) nos indica la distancia actual entre los activos. Pero el valor absoluto del Spread varía drásticamente dependiendo de los precios nominales de los tokens. Para crear un sistema de señales de trading universal, normalizamos el Spread convirtiéndolo en un **Z-Score Rodante**.

Aquí es donde entra la **Ventana de Media Móvil (Moving Average Window)** que mencionaste. Si calculáramos el promedio global utilizando los 672 periodos completos de cointegración, el Z-Score sería lentísimo y ciego a los cambios de micro-estructura recientes. Al usar una ventana corta (como 30 o 60 periodos), el Z-Score evalúa la desviación estándar *inmediata*, volviéndose un oscilador reactivo perfecto para el corto plazo.

1.  **Media Móvil Rodante ($\mu_t$):** El Spread promedio sobre los últimos $n$ periodos (tu Z-Score Window).
    $$ \mu_t = \frac{1}{n} \sum_{i=0}^{n-1} \text{Spread}_{t-i} $$
2.  **Desviación Estándar Rodante ($\sigma_t$):** La volatilidad reciente del spread en esos $n$ periodos.
    $$ \sigma_t = \sqrt{ \frac{1}{n} \sum_{i=0}^{n-1} (\text{Spread}_{t-i} - \mu_t)^2 } $$
3.  **La Ecuación del Z-Score:**
    $$ Z_t = \frac{\text{Spread}_t - \mu_t}{\sigma_t} $$

**Cómo leer el Z-Score para invertir:**
*   **$Z_t = 0$ (Media):** El spread está exactamente en su promedio reciente. Cerrar posiciones (Take Profit).
*   **$Z_t \ge +2.0$ (Sobrecomprado):** El spread está 2 desviaciones estándar POR ENCIMA de su media móvil. Asset A está históricamente sobrevalorado frente a Asset B.
    *   *Acción:* **Short the Spread** (Vender Asset A, Comprar Asset B $\times \beta$).
*   **$Z_t \le -2.0$ (Sobrevendido):** El spread está 2 desviaciones estándar POR DEBAJO de su media móvil. Asset A está históricamente infravalorado frente a Asset B.
    *   *Acción:* **Buy the Spread** (Comprar Asset A, Vender Asset B $\times \beta$).

#### 👁️ Pro-Tips para leer las gráficas como un Institucional
*   **El Patrón "Money Printer":** La línea azul se parece a unos latidos cardíacos frenéticos. Sube rápido a tocar la línea roja (+2), y en pocas barras cae violentamente cruzando el cero para tocar la verde (-2). *Esto significa que tus operaciones abren y cierran velozmente, generando un alto rotamiento de capital con ganancias constantes.*
*   **El Patrón "Account Drainer":** La línea azul sube lentamente a un +1.5 o +2.0 y simplemente se queda ahí, flotando lateralmente por días sin cruzar la línea de cero jamás. *Esto atrapa tu capital en posiciones abiertas que pagan enormes e inútiles tasas de 'Funding Ratios' a los exchanges sin revertir a la media.*
        """)
