"""Panel 5 — Dollar & Credit Stress.

Sub-panels per PRD:
  5a — Dollar Signals (trade-weighted USD, USD/CAD, dollar/yield divergence flag)
  5b — Credit Spreads (IG OAS, HY OAS)
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from data.fred import fetch_with_fallback
from data.calculated import dollar_yield_divergence
from config import FRED_SERIES, PLOTLY_LAYOUT
from panels.bonds import render_status_badge


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def load_credit_data() -> tuple[dict, dict]:
    """Fetch all Panel 5 series. Returns (data_dict, status_dict)."""
    series_names = [
        "ig_spread", "hy_spread",
        "dxy_proxy", "usd_cad",
        "yield_10yr",   # needed for divergence flag calculation
    ]
    data, statuses = {}, {}
    for name in series_names:
        series, status = fetch_with_fallback(
            FRED_SERIES[name], source="fred", cache_max_age_hours=4
        )
        data[name]     = series
        statuses[name] = status
    return data, statuses


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _current(s: pd.Series | None) -> float | None:
    if s is None or s.empty:
        return None
    return float(s.dropna().iloc[-1])


def _tail(s: pd.Series | None, n: int) -> pd.Series | None:
    if s is None or s.empty:
        return s
    return s.dropna().tail(n)


# ---------------------------------------------------------------------------
# Sub-panel 5a — Dollar Signals
# ---------------------------------------------------------------------------

def render_divergence_flag(data: dict) -> None:
    """Dollar/yield divergence — THE primary crisis signal per PRD."""
    yield_s = data.get("yield_10yr")
    dxy_s   = data.get("dxy_proxy")

    if yield_s is None or dxy_s is None:
        st.info("Dollar/yield divergence flag requires yield and DXY data.")
        return

    result = dollar_yield_divergence(yield_s, dxy_s)
    flag   = result["flag"]

    color_map = {
        "crisis_signal": ("#FF0000", "🔴", "CRISIS SIGNAL",
                          "Capital flight from US assets — Liz Truss territory"),
        "normal_stress": ("#FFCC00", "🟡", "NORMAL STRESS",
                          "Risk-off rotation within US assets — manageable"),
        "neutral":       ("#00CC44", "🟢", "NEUTRAL",
                          "No significant dollar/yield divergence"),
    }
    color, icon, label, prd_desc = color_map.get(
        flag, ("#888888", "⚪", "UNKNOWN", "")
    )

    st.markdown(
        f"""
        <div style="border:1px solid {color}; border-left:4px solid {color};
                    padding:12px 16px; margin:8px 0; border-radius:0 4px 4px 0;
                    background:rgba(255,255,255,0.03);">
            <div style="font-size:10px;color:#888;text-transform:uppercase;
                        letter-spacing:0.6px;">Dollar / Yield Divergence Flag</div>
            <div style="font-size:17px;font-weight:bold;color:{color};
                        margin:6px 0;">{icon}&nbsp;{label}</div>
            <div style="font-size:12px;color:#ccc;">{result['description']}</div>
            <div style="font-size:11px;color:#888;margin-top:4px;font-style:italic;">
                {prd_desc}
            </div>
            <div style="font-size:10px;color:#666;margin-top:6px;">
                Yield trend: <b>{result['yield_trend']}</b> &nbsp;|&nbsp;
                Dollar trend: <b>{result['dollar_trend']}</b>
                &nbsp;(20-day rolling window)
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_subpanel_5a(data: dict) -> None:
    st.markdown("**Sub-panel 5a — Dollar Signals**")

    col1, col2 = st.columns([1, 1])

    with col1:
        dxy_val = _current(data.get("dxy_proxy"))
        if dxy_val is not None:
            render_status_badge(
                "Trade Weighted USD Index (Broad)",
                f"{dxy_val:.2f}",
                "green",
                "DTWEXBGS — broad index, not DXY",
            )
        usd_cad_val = _current(data.get("usd_cad"))
        if usd_cad_val is not None:
            render_status_badge(
                "USD/CAD",
                f"{usd_cad_val:.4f}",
                "green",
                "Relevant to Canadian positioning",
            )

    with col2:
        render_divergence_flag(data)


# ---------------------------------------------------------------------------
# Sub-panel 5b — Credit Spreads
# ---------------------------------------------------------------------------

def render_credit_spread_chart(data: dict, trading_days: int) -> None:
    ig_raw = data.get("ig_spread")
    hy_raw = data.get("hy_spread")

    # FRED BAMLC0A0CM and BAMLH0A0HYM2 are in percent; convert to bps
    ig_bps = _tail(ig_raw, trading_days)
    hy_bps = _tail(hy_raw, trading_days)
    if ig_bps is not None:
        ig_bps = ig_bps * 100
    if hy_bps is not None:
        hy_bps = hy_bps * 100

    if ig_bps is None and hy_bps is None:
        st.error("Credit spread data unavailable.")
        return

    fig = go.Figure()

    if ig_bps is not None and not ig_bps.empty:
        fig.add_trace(go.Scatter(
            x=ig_bps.index, y=ig_bps.values,
            name="IG OAS", mode="lines",
            line=dict(color="#4488FF", width=2),
            yaxis="y",
        ))

    if hy_bps is not None and not hy_bps.empty:
        fig.add_trace(go.Scatter(
            x=hy_bps.index, y=hy_bps.values,
            name="HY OAS", mode="lines",
            line=dict(color="#FF8800", width=2),
            yaxis="y2",
        ))

    layout = dict(PLOTLY_LAYOUT)
    layout.update({
        "title":  "Credit Spreads — ICE BofA OAS",
        "height": 280,
        "yaxis":  dict(
            title="IG OAS (bps)",
            titlefont=dict(color="#4488FF"),
            tickfont=dict(color="#4488FF"),
        ),
        "yaxis2": dict(
            title="HY OAS (bps)",
            titlefont=dict(color="#FF8800"),
            tickfont=dict(color="#FF8800"),
            overlaying="y", side="right",
        ),
        "legend": dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
        ),
    })
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True)


def render_subpanel_5b(data: dict, trading_days: int) -> None:
    st.markdown("**Sub-panel 5b — Credit Spreads**")

    col_charts, col_badges = st.columns([2, 1])

    with col_charts:
        render_credit_spread_chart(data, trading_days)

    with col_badges:
        ig_raw = data.get("ig_spread")
        hy_raw = data.get("hy_spread")

        if ig_raw is not None and not ig_raw.empty:
            v = float(ig_raw.dropna().iloc[-1]) * 100  # bps
            # PRD: green <100, yellow 100-200, red >200
            status = "red" if v > 200 else "yellow" if v > 100 else "green"
            render_status_badge(
                "IG Spread (OAS)", f"{v:.0f} bps", status,
                "🟢 <100 | 🟡 100–200 | 🔴 >200 bps",
            )

        if hy_raw is not None and not hy_raw.empty:
            v = float(hy_raw.dropna().iloc[-1]) * 100  # bps
            # PRD: green <400, yellow 400-600, red >600
            status = "red" if v > 600 else "yellow" if v > 400 else "green"
            render_status_badge(
                "HY Spread (OAS)", f"{v:.0f} bps", status,
                "🟢 <400 | 🟡 400–600 | 🔴 >600 bps",
            )

    st.caption(
        "Source: ICE BofA via FRED (BAMLC0A0CM, BAMLH0A0HYM2). "
        "Displayed in basis points (FRED series is in percent). ~1 business day lag."
    )


# ---------------------------------------------------------------------------
# Main panel renderer
# ---------------------------------------------------------------------------

def render_panel_credit(trading_days: int = 252) -> None:
    st.subheader("Panel 5 — Dollar & Credit Stress")

    with st.spinner("Loading Panel 5 data…"):
        data, statuses = load_credit_data()

    for name, status in statuses.items():
        if status == "stale":
            st.warning(f"⚠️ {name}: live fetch failed — showing cached value.")
        elif status == "error":
            st.error(f"❌ {name}: unavailable.")

    render_subpanel_5a(data)

    st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)

    render_subpanel_5b(data, trading_days)
