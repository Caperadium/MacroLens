"""Credit spread panel — IG and HY OAS (Phase 1 step 6)."""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from data.fred import fetch_with_fallback
from config import FRED_SERIES, PLOTLY_LAYOUT
from panels.bonds import render_status_badge


@st.cache_data(ttl=3600)
def load_credit_data() -> tuple[dict, dict]:
    data, statuses = {}, {}
    for name in ("ig_spread", "hy_spread"):
        series, status = fetch_with_fallback(
            FRED_SERIES[name], source="fred", cache_max_age_hours=4
        )
        data[name]     = series
        statuses[name] = status
    return data, statuses


def render_panel_credit(trading_days: int = 252) -> None:
    st.subheader("Credit Spreads — IG & High Yield OAS")

    with st.spinner("Loading credit spread data…"):
        data, statuses = load_credit_data()

    for name, status in statuses.items():
        if status == "stale":
            st.warning(f"⚠️ {name}: live fetch failed — showing cached value.")
        elif status == "error":
            st.error(f"❌ {name}: unavailable.")

    ig_raw = data.get("ig_spread")
    hy_raw = data.get("hy_spread")

    if ig_raw is None and hy_raw is None:
        st.error("No credit spread data available.")
        return

    # FRED BAMLC0A0CM and BAMLH0A0HYM2 are in percent; convert to bps
    ig_bps = ig_raw.dropna().tail(trading_days) * 100 if ig_raw is not None else None
    hy_bps = hy_raw.dropna().tail(trading_days) * 100 if hy_raw is not None else None

    # ---- Chart ----
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
        "title":  "Credit Spreads — ICE BofA OAS (FRED, 1-day lag)",
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
            overlaying="y",
            side="right",
        ),
        "legend": dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
        ),
    })
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True)

    # ---- Status badges ----
    col1, col2 = st.columns(2)
    with col1:
        if ig_bps is not None and not ig_bps.empty:
            v = float(ig_bps.iloc[-1])
            status = "red" if v > 200 else "yellow" if v > 150 else "green"
            render_status_badge(
                "IG Spread (OAS)", f"{v:.0f} bps", status,
                "⚠️ Above 200 bps threshold" if v > 200 else "Threshold: 200 bps",
            )
    with col2:
        if hy_bps is not None and not hy_bps.empty:
            v = float(hy_bps.iloc[-1])
            status = "red" if v > 600 else "yellow" if v > 500 else "green"
            render_status_badge(
                "HY Spread (OAS)", f"{v:.0f} bps", status,
                "⚠️ Above 600 bps threshold" if v > 600 else "Threshold: 600 bps",
            )

    st.caption(
        "Source: ICE BofA via FRED (BAMLC0A0CM, BAMLH0A0HYM2). "
        "Data is in percent on FRED; displayed here in basis points. "
        "~1 business day lag."
    )
