"""Panel 3 — Bond Market stress monitor."""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from data.fred import fetch_with_fallback
from data.calculated import (
    classify_yield_curve_move,
    dollar_yield_divergence,
    calculate_panel_score,
)
from config import FRED_SERIES, PLOTLY_LAYOUT


# ---------------------------------------------------------------------------
# Data loading (cached per Streamlit session for 1 hour)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def load_bond_data() -> tuple[dict, dict]:
    """Fetch all Panel 3 + DXY series. Returns (data_dict, status_dict)."""
    series_names = [
        "yield_3m", "yield_2yr", "yield_10yr", "yield_30yr",
        "breakeven_10yr", "term_premium_10yr", "spread_2s10s",
        "dxy_proxy",
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

def _current(series: pd.Series | None) -> float | None:
    if series is None or series.empty:
        return None
    return float(series.dropna().iloc[-1])


def _offset(series: pd.Series | None, trading_days_back: int) -> float | None:
    """Value approximately N trading days ago."""
    if series is None or series.empty:
        return None
    s = series.dropna()
    idx = max(0, len(s) - 1 - trading_days_back)
    return float(s.iloc[idx])


def _tail(series: pd.Series | None, trading_days: int) -> pd.Series | None:
    if series is None or series.empty:
        return series
    return series.dropna().tail(trading_days)


def _yield_status(v: float | None) -> str:
    if v is None:
        return "green"
    if v >= 5.5:
        return "red"
    if v >= 4.5:
        return "yellow"
    return "green"


def _term_premium_status(v: float | None) -> str:
    if v is None:
        return "green"
    if v >= 2.0:
        return "red"
    if v >= 1.0:
        return "yellow"
    return "green"


def _spread_status(bps: float | None) -> str:
    """Higher stress when the curve is more deeply inverted."""
    if bps is None:
        return "green"
    if bps <= -50:
        return "red"
    if bps <= 0:
        return "yellow"
    return "green"


def _breakeven_status(v: float | None) -> str:
    if v is None:
        return "green"
    if v > 2.75:
        return "red"
    if v > 2.5:
        return "yellow"
    return "green"


# ---------------------------------------------------------------------------
# Status badge component
# ---------------------------------------------------------------------------

def render_status_badge(
    label: str, value: str, status: str, interpretation: str
) -> None:
    colors = {"green": "#00CC44", "yellow": "#FFCC00", "red": "#FF4444"}
    c = colors.get(status, "#888888")
    st.markdown(
        f"""
        <div style="border-left:4px solid {c}; padding:8px 12px; margin:4px 0;
                    background:rgba(255,255,255,0.05); border-radius:0 4px 4px 0;">
            <div style="font-size:10px;color:#888;text-transform:uppercase;
                        letter-spacing:0.6px;">{label}</div>
            <div style="font-size:22px;font-weight:bold;color:#fff;">{value}</div>
            <div style="font-size:11px;color:#aaa;">{interpretation}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Chart renderers
# ---------------------------------------------------------------------------

def _base_layout(title: str, height: int, **overrides) -> dict:
    layout = dict(PLOTLY_LAYOUT)
    layout.update({"title": title, "height": height})
    layout.update(overrides)
    return layout


def render_yield_curve_chart(data: dict, trading_days: int) -> None:
    """Snapshot yield curve: current vs 1M ago vs 6M ago."""
    maturities = ["3M", "2Y", "10Y", "30Y"]
    keys       = ["yield_3m", "yield_2yr", "yield_10yr", "yield_30yr"]

    current  = [_current(data.get(k)) for k in keys]
    one_mo   = [_offset(data.get(k), 21)  for k in keys]
    six_mo   = [_offset(data.get(k), 126) for k in keys]

    fig = go.Figure()

    if any(v is not None for v in six_mo):
        fig.add_trace(go.Scatter(
            x=maturities, y=six_mo, name="6M ago",
            mode="lines+markers",
            line=dict(color="#444444", width=2, dash="dot"),
            marker=dict(size=5),
        ))
    if any(v is not None for v in one_mo):
        fig.add_trace(go.Scatter(
            x=maturities, y=one_mo, name="1M ago",
            mode="lines+markers",
            line=dict(color="#888888", width=2),
            marker=dict(size=5),
        ))
    if any(v is not None for v in current):
        fig.add_trace(go.Scatter(
            x=maturities, y=current, name="Current",
            mode="lines+markers",
            line=dict(color="#FFFFFF", width=3),
            marker=dict(size=7),
        ))

    fig.update_layout(**_base_layout(
        "Yield Curve Shape", 260,
        xaxis_title="Maturity",
        yaxis_title="Yield (%)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    ))
    st.plotly_chart(fig, use_container_width=True)


def render_10yr_yield_chart(data: dict, trading_days: int) -> None:
    s = _tail(data.get("yield_10yr"), trading_days)
    if s is None or s.empty:
        st.warning("10-Year yield data unavailable.")
        return

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=s.index, y=s.values, name="10Y Yield", mode="lines",
        line=dict(color="#FFFFFF", width=1.8),
        fill="tozeroy", fillcolor="rgba(255,255,255,0.05)",
    ))
    fig.add_hline(
        y=5.0, line_color="#FF4444", line_dash="dash", line_width=1.5,
        annotation_text="5.0%", annotation_position="top right",
        annotation=dict(font_color="#FF4444", font_size=11),
    )
    fig.update_layout(**_base_layout(
        "10-Year Treasury Yield", 210,
        yaxis_title="Yield (%)", showlegend=False,
    ))
    st.plotly_chart(fig, use_container_width=True)


def render_2s10s_chart(data: dict, trading_days: int) -> None:
    """2s10s spread in basis points (T10Y2Y × 100)."""
    raw = _tail(data.get("spread_2s10s"), trading_days)
    if raw is None or raw.empty:
        st.warning("2s10s spread data unavailable.")
        return

    bps = raw * 100  # FRED T10Y2Y is in %, convert to bps

    fig = go.Figure()
    # Green fill above zero, red fill below zero
    fig.add_trace(go.Scatter(
        x=bps.index, y=bps.clip(lower=0).values,
        name="Positive", mode="lines",
        line=dict(color="rgba(0,204,68,0)", width=0),
        fill="tozeroy", fillcolor="rgba(0,204,68,0.18)",
        showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=bps.index, y=bps.clip(upper=0).values,
        name="Negative", mode="lines",
        line=dict(color="rgba(255,68,68,0)", width=0),
        fill="tozeroy", fillcolor="rgba(255,68,68,0.22)",
        showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=bps.index, y=bps.values, name="2s10s",
        mode="lines", line=dict(color="#AAAAAA", width=1.5),
    ))
    fig.add_hline(y=0, line_color="#555555", line_width=1)
    fig.update_layout(**_base_layout(
        "2s10s Spread (10Y − 2Y)", 210,
        yaxis_title="Basis Points", showlegend=False,
    ))
    st.plotly_chart(fig, use_container_width=True)


def render_term_premium_chart(data: dict, trading_days: int) -> None:
    s = _tail(data.get("term_premium_10yr"), trading_days)
    if s is None or s.empty:
        st.warning("Term premium data unavailable.")
        return

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=s.index, y=s.values, name="ACM Term Premium",
        mode="lines", line=dict(color="#4488FF", width=2),
        fill="tozeroy", fillcolor="rgba(68,136,255,0.10)",
    ))
    fig.add_hline(y=0, line_color="#555555", line_width=1)
    fig.update_layout(**_base_layout(
        "10-Year ACM Term Premium (NY Fed)", 210,
        yaxis_title="Term Premium (%)", showlegend=False,
    ))
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Dollar/yield divergence flag
# ---------------------------------------------------------------------------

def render_divergence_flag(data: dict) -> None:
    yield_s = data.get("yield_10yr")
    dxy_s   = data.get("dxy_proxy")

    if yield_s is None or dxy_s is None:
        return

    result = dollar_yield_divergence(yield_s, dxy_s)
    flag   = result["flag"]

    color_map = {
        "crisis_signal": ("#FF0000", "🔴", "CRISIS SIGNAL"),
        "normal_stress": ("#FFCC00", "🟡", "NORMAL STRESS"),
        "neutral":       ("#00CC44", "🟢", "NEUTRAL"),
    }
    color, icon, label = color_map.get(flag, ("#888888", "⚪", "UNKNOWN"))

    st.markdown(
        f"""
        <div style="border:1px solid {color}; border-left:4px solid {color};
                    padding:10px 14px; margin:8px 0; border-radius:0 4px 4px 0;
                    background:rgba(255,255,255,0.03);">
            <div style="font-size:10px;color:#888;text-transform:uppercase;
                        letter-spacing:0.6px;">Dollar / Yield Divergence</div>
            <div style="font-size:15px;font-weight:bold;color:{color};
                        margin:4px 0;">{icon}&nbsp;{label}</div>
            <div style="font-size:12px;color:#ccc;">{result['description']}</div>
            <div style="font-size:10px;color:#666;margin-top:4px;">
                Yield trend: <b>{result['yield_trend']}</b> &nbsp;|&nbsp;
                Dollar trend: <b>{result['dollar_trend']}</b>
                &nbsp;(20-day window)
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Alert banners (in-app only for Phase 1)
# ---------------------------------------------------------------------------

def _check_active_alerts(
    y10yr: float | None,
    breakeven: float | None,
    divergence_flag: str,
) -> list[tuple[str, str]]:
    """Return list of (severity, message) for active threshold breaches."""
    alerts = []
    if y10yr is not None and y10yr >= 5.0:
        alerts.append(("critical", f"10-Year yield {y10yr:.2f}% — above 5.0% threshold"))
    if breakeven is not None and breakeven > 2.75:
        alerts.append(("warning", f"10Y breakeven {breakeven:.2f}% — above 2.75% threshold"))
    if divergence_flag == "crisis_signal":
        alerts.append(("critical", "Dollar/yield crisis signal active"))
    return alerts


# ---------------------------------------------------------------------------
# Main panel renderer
# ---------------------------------------------------------------------------

def render_panel_bonds(trading_days: int = 252) -> None:
    st.subheader("Panel 3 — Bond Market")

    with st.spinner("Loading bond market data…"):
        data, statuses = load_bond_data()

    # Stale / error warnings
    for name, status in statuses.items():
        if status == "stale":
            st.warning(f"⚠️ {name}: live fetch failed — showing last cached value.")
        elif status == "error":
            st.error(f"❌ {name}: data unavailable. Check FRED_API_KEY or network.")

    # ---- Derive current values ----
    y3m     = _current(data.get("yield_3m"))
    y2yr    = _current(data.get("yield_2yr"))
    y10yr   = _current(data.get("yield_10yr"))
    y30yr   = _current(data.get("yield_30yr"))
    be      = _current(data.get("breakeven_10yr"))
    tp      = _current(data.get("term_premium_10yr"))

    raw_spread     = _current(data.get("spread_2s10s"))
    spread_bps     = raw_spread * 100 if raw_spread is not None else None

    raw_spread_20  = _offset(data.get("spread_2s10s"), 20)
    spread_bps_20  = raw_spread_20 * 100 if raw_spread_20 is not None else None
    y2yr_20        = _offset(data.get("yield_2yr"), 20)

    # Yield curve regime classification
    curve_label = "—"
    if all(v is not None for v in [spread_bps, spread_bps_20, y2yr, y2yr_20]):
        curve_label = classify_yield_curve_move(
            spread_bps, spread_bps_20, y2yr, y2yr_20
        )

    # Divergence flag (needed for alerts + badge)
    dxy_s = data.get("dxy_proxy")
    y10_s = data.get("yield_10yr")
    div_result = (
        dollar_yield_divergence(y10_s, dxy_s)
        if y10_s is not None and dxy_s is not None
        else {"flag": "neutral"}
    )

    # Panel composite score
    panel_score = calculate_panel_score("bonds", {
        "yield_10yr":              y10yr,
        "term_premium":            tp,
        "spread_2s10s_normalized": spread_bps,
        "breakeven_10yr":          be,
    })

    # Active alerts
    active_alerts = _check_active_alerts(y10yr, be, div_result["flag"])
    for severity, msg in active_alerts:
        if severity == "critical":
            st.error(f"🚨 {msg}")
        else:
            st.warning(f"⚠️ {msg}")

    # ---- Layout: badges | charts ----
    col_b, col_c = st.columns([1, 2])

    with col_b:
        score_color = "#FF4444" if panel_score >= 7 else "#FFCC00" if panel_score >= 5 else "#00CC44"
        st.markdown(
            f"<div style='font-size:13px;color:#888;margin-bottom:4px;'>"
            f"Bond Stress Score</div>"
            f"<div style='font-size:28px;font-weight:bold;color:{score_color};"
            f"margin-bottom:12px;'>{panel_score} / 10</div>",
            unsafe_allow_html=True,
        )

        if y10yr is not None:
            render_status_badge(
                "10-Year Yield", f"{y10yr:.2f}%",
                _yield_status(y10yr),
                "⚠️ Above 5.0% threshold" if y10yr >= 5.0 else "Key rate | threshold: 5.0%",
            )
        if y2yr is not None:
            render_status_badge(
                "2-Year Yield", f"{y2yr:.2f}%",
                _yield_status(y2yr),
                "Short end — Fed policy sensitive",
            )
        if spread_bps is not None:
            render_status_badge(
                "2s10s Spread", f"{spread_bps:+.0f} bps",
                _spread_status(spread_bps),
                f"Regime: {curve_label}",
            )
        if tp is not None:
            render_status_badge(
                "10Y Term Premium", f"{tp:.2f}%",
                _term_premium_status(tp),
                "ACM estimate (NY Fed) | elevated = demand concerns",
            )
        if be is not None:
            render_status_badge(
                "10Y Breakeven Inflation", f"{be:.2f}%",
                _breakeven_status(be),
                "Market-implied 10yr avg inflation",
            )
        if y30yr is not None:
            render_status_badge(
                "30-Year Yield", f"{y30yr:.2f}%",
                _yield_status(y30yr),
                "Long end — supply/demand sensitive",
            )
        if y3m is not None:
            render_status_badge(
                "3-Month Yield", f"{y3m:.2f}%",
                "green",
                "Near-term risk-free rate",
            )

        st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)
        render_divergence_flag(data)

    with col_c:
        render_yield_curve_chart(data, trading_days)
        render_10yr_yield_chart(data, trading_days)
        render_2s10s_chart(data, trading_days)
        render_term_premium_chart(data, trading_days)
