"""Panel 2 — Consumer Stress Indicator.

Confirms whether demand destruction risk from inflation is materialising.
All data via FRED.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from data.fred import fetch_with_fallback
from data.calculated import (
    calculate_real_wage_growth,
    yoy_pct_change,
    calculate_panel_score,
)
from config import FRED_SERIES, PLOTLY_LAYOUT
from panels.bonds import render_status_badge


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def load_consumer_data() -> tuple[dict, dict]:
    """Fetch Panel 2 series. Monthly/quarterly series use 24h TTL."""
    series_map = {
        "avg_hourly_earnings": ("fred", 24),
        "cpi":                 ("fred", 24),
        "savings_rate":        ("fred", 24),
        "revolving_credit":    ("fred", 24),
        "cc_delinquency":      ("fred", 24),
        "umich_sentiment":     ("fred", 24),
    }
    data, statuses = {}, {}
    for name, (source, ttl) in series_map.items():
        series, status = fetch_with_fallback(
            FRED_SERIES[name], source=source, cache_max_age_hours=ttl
        )
        data[name]     = series
        statuses[name] = status
    return data, statuses


# ---------------------------------------------------------------------------
# Score export
# ---------------------------------------------------------------------------

def compute_consumer_score(data: dict) -> float:
    """Pure score calculation for the crisis stage banner."""
    earnings = data.get("avg_hourly_earnings")
    cpi      = data.get("cpi")
    savings  = data.get("savings_rate")
    cc_delq  = data.get("cc_delinquency")
    umich    = data.get("umich_sentiment")

    real_wage = None
    if earnings is not None and not earnings.empty and cpi is not None and not cpi.empty:
        rw = calculate_real_wage_growth(earnings, cpi)
        real_wage = _current(rw)

    return calculate_panel_score("consumer", {
        "real_wage_growth":           real_wage,
        "savings_rate":               _current(savings),
        "cc_delinquency":             _current(cc_delq),
        "umich_sentiment_normalized": _current(umich),
    })


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _current(s: pd.Series | None) -> float | None:
    if s is None or s.empty:
        return None
    clean = s.dropna()
    if clean.empty:
        return None
    return float(clean.iloc[-1])


def _tail(s: pd.Series | None, n: int) -> pd.Series | None:
    if s is None or s.empty:
        return s
    return s.dropna().tail(n)


def _base_layout(title: str, height: int, **extra) -> dict:
    layout = dict(PLOTLY_LAYOUT)
    layout.update({"title": title, "height": height})
    layout.update(extra)
    return layout


# ---------------------------------------------------------------------------
# Status helpers (PRD thresholds)
# ---------------------------------------------------------------------------

def _real_wage_status(v: float | None) -> str:
    if v is None:
        return "green"
    if v < -0.2:
        return "red"
    if v < 0:
        return "yellow"
    return "green"


def _savings_status(v: float | None) -> str:
    if v is None:
        return "green"
    if v < 3:
        return "red"
    if v < 5:
        return "yellow"
    return "green"


def _delinquency_status(v: float | None) -> str:
    if v is None:
        return "green"
    if v > 4.0:
        return "red"
    if v > 3.0:
        return "yellow"
    return "green"


def _umich_status(v: float | None) -> str:
    if v is None:
        return "green"
    if v < 60:
        return "red"
    if v < 75:
        return "yellow"
    return "green"


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def render_real_wage_chart(data: dict, trading_days: int) -> None:
    """Real wage growth bar chart — green positive, red negative."""
    earnings = _tail(data.get("avg_hourly_earnings"), trading_days)
    cpi      = _tail(data.get("cpi"), trading_days)

    if earnings is None or cpi is None:
        st.warning("Real wage data unavailable.")
        return

    rw = calculate_real_wage_growth(earnings, cpi).dropna()
    if rw.empty:
        st.warning("Insufficient data for real wage calculation.")
        return

    colors = ["#00CC44" if v >= 0 else "#FF4444" for v in rw.values]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=rw.index, y=rw.values,
        name="Real Wage Growth", marker_color=colors,
    ))
    fig.add_hline(y=0, line_color="#666666", line_width=1)
    fig.update_layout(**_base_layout(
        "Real Wage Growth (Nominal MoM − CPI MoM)", 220,
        yaxis_title="% MoM difference", showlegend=False,
    ))
    st.plotly_chart(fig, use_container_width=True)


def render_savings_chart(data: dict, trading_days: int) -> None:
    s = _tail(data.get("savings_rate"), trading_days)
    if s is None or s.empty:
        st.warning("Savings rate data unavailable.")
        return

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=s.index, y=s.values,
        name="Personal Savings Rate", mode="lines",
        line=dict(color="#4488FF", width=2),
        fill="tozeroy", fillcolor="rgba(68,136,255,0.08)",
    ))
    fig.add_hrect(y0=0, y1=3,  fillcolor="rgba(255,68,68,0.08)",  line_width=0)
    fig.add_hrect(y0=3, y1=5,  fillcolor="rgba(255,204,0,0.05)", line_width=0)
    fig.add_hline(y=5, line_color="#FFCC00", line_dash="dash", line_width=1,
                  annotation_text="5%", annotation_position="right",
                  annotation=dict(font_color="#FFCC00", font_size=10))
    fig.add_hline(y=3, line_color="#FF4444", line_dash="dash", line_width=1,
                  annotation_text="3%", annotation_position="right",
                  annotation=dict(font_color="#FF4444", font_size=10))
    fig.update_layout(**_base_layout(
        "Personal Savings Rate", 210,
        yaxis_title="%", showlegend=False,
    ))
    st.plotly_chart(fig, use_container_width=True)


def render_consumer_stress_chart(data: dict, trading_days: int) -> None:
    """UMich sentiment, CC delinquency, and revolving credit on one panel."""
    umich  = _tail(data.get("umich_sentiment"), trading_days)
    cc     = _tail(data.get("cc_delinquency"), trading_days)
    rev    = data.get("revolving_credit")
    rev_yoy = yoy_pct_change(rev).dropna().tail(trading_days) if rev is not None and not rev.empty else None

    fig = go.Figure()

    if umich is not None and not umich.empty:
        fig.add_trace(go.Scatter(
            x=umich.index, y=umich.values,
            name="UMich Sentiment", mode="lines",
            line=dict(color="#FFFFFF", width=2),
            yaxis="y",
        ))

    if cc is not None and not cc.empty:
        fig.add_trace(go.Scatter(
            x=cc.index, y=cc.values,
            name="CC Delinquency %", mode="lines",
            line=dict(color="#FF4444", width=2),
            yaxis="y2",
        ))

    layout = dict(PLOTLY_LAYOUT)
    layout.update({
        "title":  "UMich Consumer Sentiment vs CC Delinquency Rate",
        "height": 220,
        "yaxis":  dict(title="UMich Index",      titlefont=dict(color="#FFFFFF")),
        "yaxis2": dict(title="CC Delinquency %", titlefont=dict(color="#FF4444"),
                       overlaying="y", side="right"),
        "legend": dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    })
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Main panel renderer
# ---------------------------------------------------------------------------

def render_panel_consumer(trading_days: int = 252) -> None:
    st.subheader("Panel 2 — Consumer Stress Indicator")

    with st.spinner("Loading consumer data…"):
        data, statuses = load_consumer_data()

    for name, status in statuses.items():
        if status == "stale":
            st.warning(f"⚠️ {name}: live fetch failed — showing cached value.")
        elif status == "error":
            st.error(f"❌ {name}: unavailable.")

    # Compute display values
    earnings = data.get("avg_hourly_earnings")
    cpi      = data.get("cpi")
    rw_val   = None
    if earnings is not None and not earnings.empty and cpi is not None and not cpi.empty:
        rw_val = _current(calculate_real_wage_growth(earnings, cpi))

    savings_val = _current(data.get("savings_rate"))
    cc_val      = _current(data.get("cc_delinquency"))
    umich_val   = _current(data.get("umich_sentiment"))

    rev = data.get("revolving_credit")
    rev_yoy_val = _current(yoy_pct_change(rev)) if rev is not None and not rev.empty else None

    panel_score = compute_consumer_score(data)
    score_color = "#FF4444" if panel_score >= 7 else "#FFCC00" if panel_score >= 5 else "#00CC44"

    col_b, col_c = st.columns([1, 2])

    with col_b:
        st.markdown(
            f"<div style='font-size:13px;color:#888;'>Consumer Stress Score</div>"
            f"<div style='font-size:26px;font-weight:bold;color:{score_color};"
            f"margin-bottom:12px;'>{panel_score} / 10</div>",
            unsafe_allow_html=True,
        )

        if rw_val is not None:
            render_status_badge(
                "Real Wage Growth (MoM)", f"{rw_val:+.2f}%",
                _real_wage_status(rw_val),
                "🟢 positive | 🟡 slightly negative | 🔴 deeply negative",
            )
        if savings_val is not None:
            render_status_badge(
                "Personal Savings Rate", f"{savings_val:.1f}%",
                _savings_status(savings_val),
                "🟢 >5% | 🟡 3–5% | 🔴 <3% | buffer depletion indicator",
            )
        if cc_val is not None:
            render_status_badge(
                "CC Delinquency Rate", f"{cc_val:.2f}%",
                _delinquency_status(cc_val),
                "🟢 <3% | 🟡 3–4% | 🔴 >4% | consumer debt stress",
            )
        if umich_val is not None:
            render_status_badge(
                "UMich Consumer Sentiment", f"{umich_val:.1f}",
                _umich_status(umich_val),
                "🟢 >75 | 🟡 60–75 | 🔴 <60 | forward-looking confidence",
            )
        if rev_yoy_val is not None:
            rev_s = "red" if rev_yoy_val > 10 else "yellow" if rev_yoy_val > 5 else "green"
            render_status_badge(
                "Revolving Credit YoY %", f"{rev_yoy_val:+.1f}%",
                rev_s,
                "Credit card debt acceleration",
            )

    with col_c:
        render_real_wage_chart(data, trading_days)
        render_savings_chart(data, trading_days)
        render_consumer_stress_chart(data, trading_days)

    st.caption(
        "Sources: FRED — CES0500000003, CPIAUCSL, PSAVERT, REVOLSL, "
        "DRCCLACBS, UMCSENT. Monthly/quarterly data, ~1 day lag."
    )
