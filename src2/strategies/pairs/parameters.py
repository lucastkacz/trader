"""
Strategy-owned parameter definitions for Pairs Trading.

This module reads defaults from config.yml and renders the Streamlit
parameter widgets.  Keeping parameters in their own file makes them
easy to import from an optimiser without pulling in Streamlit or the
full strategy class.
"""

from typing import Any, Dict


def get_defaults(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract a flat parameter dict from the raw YAML config.
    Useful for headless / optimiser access (no Streamlit needed).
    """
    params = config.get("parameters", {})
    exec_p = params.get("execution", {})
    coint  = params.get("cointegration_thresholds", {})
    z_thr  = params.get("zscore_thresholds", {})

    return {
        "capital":        float(exec_p.get("capital", 10000.0)),
        "fee_rate":       float(exec_p.get("fee_rate_pct", 0.05)) / 100.0,
        "slippage":       float(exec_p.get("slippage_pct", 0.02)) / 100.0,
        "stop_loss_pct":  float(exec_p.get("stop_loss_pct", 0.0)),
        "long_leverage":  float(exec_p.get("long_leverage", 1.0)),
        "short_leverage": float(exec_p.get("short_leverage", 1.0)),
        "coint_window":   int(params.get("cointegration_window", 180)),
        "z_window":       int(params.get("zscore_window", 60)),
        "coint_entry":    float(coint.get("entry", 0.10)),
        "coint_cutoff":   float(coint.get("cutoff", 0.70)),
        "z_entry":        float(z_thr.get("entry", 2.0)),
        "z_exit":         float(z_thr.get("exit", 0.0)),
    }


def render_parameters(config: Dict[str, Any], st) -> Dict[str, Any]:
    """
    Render Streamlit widgets for all Pairs Trading parameters.

    Args:
        config: Raw YAML config dict (from config.yml).
        st:     The Streamlit module.

    Returns:
        Flat dict of user-chosen parameter values.
    """
    defaults = get_defaults(config)
    params   = config.get("parameters", {})
    exec_p   = params.get("execution", {})

    with st.expander("⚙️ Step 1: Define Rules & Capital", expanded=True):
        st.markdown(
            "Before calculating any math, we need to define the environment constraints."
        )
        c1, c2, c3 = st.columns(3)

        # ── Execution Costs ──────────────────────────────────────────
        with c1:
            st.markdown("**Execution Costs**")
            capital = st.number_input(
                "Total Capital Allocation ($)",
                min_value=100.0,
                value=defaults["capital"],
                step=1000.0,
                key="phase1_capital",
            )
            fee_rate_pct = st.number_input(
                "Exchange Fee Rate (%)",
                min_value=0.0,
                value=float(exec_p.get("fee_rate_pct", 0.05)),
                step=0.01,
                key="phase1_fee",
            )
            slippage_pct = st.number_input(
                "Slippage (%)",
                min_value=0.0,
                value=float(exec_p.get("slippage_pct", 0.02)),
                step=0.01,
                key="phase1_slippage",
            )
            stop_loss_pct = st.number_input(
                "Per-Trade Stop Loss (%)",
                min_value=0.0,
                value=defaults["stop_loss_pct"],
                step=0.1,
                help="Close a trade if it loses more than this % of entry equity. 0 = disabled.",
                key="phase1_stop_loss",
            )
            long_leverage = st.number_input(
                "Long Leverage (x)",
                min_value=0.1,
                value=defaults["long_leverage"],
                step=0.1,
                help="Multiplier applied when going LONG the spread (Buy A, Sell B).",
                key="phase1_long_leverage",
            )
            short_leverage = st.number_input(
                "Short Leverage (x)",
                min_value=0.1,
                value=defaults["short_leverage"],
                step=0.1,
                help="Multiplier applied when going SHORT the spread (Sell A, Buy B).",
                key="phase1_short_leverage",
            )

        # ── Statistical Windows ──────────────────────────────────────
        with c2:
            st.markdown("**Statistical Windows**")
            coint_window = st.number_input(
                "Cointegration Window (Bars)",
                min_value=10,
                value=defaults["coint_window"],
                help="How many bars to look back to calculate the OLS regression (Hedge Ratio).",
                key="phase1_coint_window",
            )
            z_window = st.number_input(
                "Z-Score MA Window (Bars)",
                min_value=10,
                value=defaults["z_window"],
                help="Smoothing window for the spread oscillator.",
                key="phase1_z_window",
            )

        # ── Regime Filters ───────────────────────────────────────────
        with c3:
            st.markdown("**Regime Filters (P-Value)**")
            coint_entry = st.number_input(
                "Entry Barrier (Start Trading)",
                min_value=0.01,
                max_value=1.0,
                value=defaults["coint_entry"],
                step=0.01,
                key="phase1_coint_entry",
            )
            coint_cutoff = st.number_input(
                "Emergency Cutoff (Kill Switch)",
                min_value=0.05,
                max_value=1.0,
                value=defaults["coint_cutoff"],
                step=0.01,
                key="phase1_coint_cutoff",
            )

        # ── Z-Score Triggers ─────────────────────────────────────────
        st.markdown("**Z-Score Triggers**")
        c4, c5 = st.columns(2)
        with c4:
            z_entry = st.number_input(
                "Z-Score Entry",
                min_value=1.0,
                value=defaults["z_entry"],
                step=0.1,
                key="phase1_z_entry",
            )
        with c5:
            z_exit = st.number_input(
                "Z-Score Exit",
                min_value=-1.0,
                value=defaults["z_exit"],
                step=0.1,
                key="phase1_z_exit",
            )

    return {
        "capital":        capital,
        "fee_rate":       fee_rate_pct / 100.0,
        "slippage":       slippage_pct / 100.0,
        "stop_loss_pct":  stop_loss_pct,
        "long_leverage":  long_leverage,
        "short_leverage": short_leverage,
        "coint_window":   coint_window,
        "z_window":       z_window,
        "coint_entry":    coint_entry,
        "coint_cutoff":   coint_cutoff,
        "z_entry":        z_entry,
        "z_exit":         z_exit,
    }
