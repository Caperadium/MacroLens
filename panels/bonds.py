"""Panel 3 — Bond Market Stress Monitor.

Sub-panels per PRD:
  3a — Yield Levels
  3b — Yield Curve Shape (2s10s, 30s2s, Bear/Bull regime flag)
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from data.fred import fetch_with_fallback
from data.calculated import (
    classify_yield_curve_move,
    calculate_panel_score,
)
from config import FRED_SERIES, PLOTLY_LAYOUT


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def load_bond_data() -> tuple[dict, dict]:
    """Fetch all Panel 3 series. Returns (data_dict, status_dict)."""
    series_names = [
        "yield_3m", "yield_2yr", "yield_10yr", "yield_30yr",
        "breakeven_10yr", "term_premium_10yr", "spread_2s10s",
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


def _offset(s: pd.Series | None, trading_days_back: int) -> float | None:
    if s is None or s.empty:
        return None
    clean = s.dropna()
    idx = max(0, len(clean) - 1 - trading_days_back)
    return float(clean.iloc[idx])


def _tail(s: pd.Series | None, n: int) -> pd.Series | None:
    if s is None or s.empty:
        return s
    return s.dropna().tail(n)


def _calculate_30s2s(data: dict) -> pd.Series | None:
    """30yr minus 2yr yield spread in basis points."""
    y30 = data.get("yield_30yr")
    y2  = data.get("yield_2yr")
    if y30 is None or y2 is None:
        return None
    combined = pd.DataFrame({"y30": y30, "y2": y2}).dropna()
    if combined.empty:
        return None
    return (combined["y30"] - combined["y2"]) * 100  # bps


# ---------------------------------------------------------------------------
# Status colours
# ---------------------------------------------------------------------------

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


def _2s10s_status(bps: float | None) -> str:
    """Deeply inverted = red (recession signal)."""
    if bps is None:
        return "green"
    if bps <= -50:
        return "red"
    if bps <= 0:
        return "yellow"
    return "green"


def _30s2s_status(bps: float | None) -> str:
    """Long-end fiscal confidence — compressing long end = stress."""
    if bps is None:
        return "green"
    if bps < 50:
        return "red"
    if bps < 150:
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
# Status badge
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
# Chart helpers
# ---------------------------------------------------------------------------

def _base_layout(title: str, height: int, **overrides) -> dict:
    layout = dict(PLOTLY_LAYOUT)
    layout.update({"title": title, "height": height})
    layout.update(overrides)
    return layout


# ---------------------------------------------------------------------------
# Sub-panel 3a — Yield Levels charts
# ---------------------------------------------------------------------------

def render_yield_curve_snapshot(data: dict) -> None:
    """Current / 1M ago / 6M ago yield curve shape."""
    maturities = ["3M", "2Y", "10Y", "30Y"]
    keys       = ["yield_3m", "yield_2yr", "yield_10yr", "yield_30yr"]

    current = [_current(data.get(k))    for k in keys]
    one_mo  = [_offset(data.get(k), 21) for k in keys]
    six_mo  = [_offset(data.get(k), 126) for k in keys]

    fig = go.Figure()
    if any(v is not None for v in six_mo):
        fig.add_trace(go.Scatter(
            x=maturities, y=six_mo, name="6M ago",
            mode="lines+markers",
            line=dict(color="#444444", width=2, dash="dot"), marker=dict(size=5),
        ))
    if any(v is not None for v in one_mo):
        fig.add_trace(go.Scatter(
            x=maturities, y=one_mo, name="1M ago",
            mode="lines+markers",
            line=dict(color="#888888", width=2), marker=dict(size=5),
        ))
    if any(v is not None for v in current):
        fig.add_trace(go.Scatter(
            x=maturities, y=current, name="Current",
            mode="lines+markers",
            line=dict(color="#FFFFFF", width=3), marker=dict(size=7),
        ))

    fig.update_layout(**_base_layout(
        "Yield Curve Shape — Current vs 1M ago vs 6M ago", 260,
        xaxis_title="Maturity", yaxis_title="Yield (%)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    ))
    st.plotly_chart(fig, use_container_width=True)


def render_10yr_chart(data: dict, trading_days: int) -> None:
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
        annotation_text="5.0% threshold", annotation_position="top right",
        annotation=dict(font_color="#FF4444", font_size=11),
    )
    fig.update_layout(**_base_layout(
        "10-Year Treasury Yield", 210,
        yaxis_title="Yield (%)", showlegend=False,
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
# Sub-panel 3b — Yield Curve Shape charts
# ---------------------------------------------------------------------------

def render_spreads_chart(data: dict, trading_days: int) -> None:
    """2s10s and 30s2s spreads on one dual-line chart."""
    raw_2s10s = _tail(data.get("spread_2s10s"), trading_days)
    spread_30s2s = _calculate_30s2s(data)
    spread_30s2s = _tail(spread_30s2s, trading_days) if spread_30s2s is not None else None

    fig = go.Figure()

    if raw_2s10s is not None and not raw_2s10s.empty:
        bps_2s10s = raw_2s10s * 100
        # Green fill above zero, red fill below
        fig.add_trace(go.Scatter(
            x=bps_2s10s.index, y=bps_2s10s.clip(lower=0).values,
            mode="lines", line=dict(color="rgba(0,204,68,0)", width=0),
            fill="tozeroy", fillcolor="rgba(0,204,68,0.15)",
            showlegend=False,
        ))
        fig.add_trace(go.Scatter(
            x=bps_2s10s.index, y=bps_2s10s.clip(upper=0).values,
            mode="lines", line=dict(color="rgba(255,68,68,0)", width=0),
            fill="tozeroy", fillcolor="rgba(255,68,68,0.20)",
            showlegend=False,
        ))
        fig.add_trace(go.Scatter(
            x=bps_2s10s.index, y=bps_2s10s.values,
            name="2s10s (10Y−2Y)", mode="lines",
            line=dict(color="#AAAAAA", width=1.8),
        ))

    if spread_30s2s is not None and not spread_30s2s.empty:
        fig.add_trace(go.Scatter(
            x=spread_30s2s.index, y=spread_30s2s.values,
            name="30s2s (30Y−2Y)", mode="lines",
            line=dict(color="#FF8800", width=1.8, dash="dot"),
        ))

    fig.add_hline(y=0, line_color="#555555", line_width=1)
    fig.update_layout(**_base_layout(
        "Yield Curve Spreads", 250,
        yaxis_title="Basis Points",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    ))
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Active alert banners
# ---------------------------------------------------------------------------

def _check_active_alerts(
    y10yr: float | None,
    breakeven: float | None,
) -> list[tuple[str, str]]:
    alerts = []
    if y10yr is not None and y10yr >= 5.0:
        alerts.append(("critical", f"10-Year yield {y10yr:.2f}% — above 5.0% threshold"))
    if breakeven is not None and breakeven > 2.75:
        alerts.append(("warning", f"10Y breakeven {breakeven:.2f}% — above 2.75%"))
    return alerts


# ---------------------------------------------------------------------------
# Main panel renderer
# ---------------------------------------------------------------------------

def render_panel_bonds(trading_days: int = 252) -> None:
    st.subheader("Panel 3 — Bond Market Stress Monitor")

    with st.spinner("Loading bond market data…"):
        data, statuses = load_bond_data()

    for name, status in statuses.items():
        if status == "stale":
            st.warning(f"⚠️ {name}: live fetch failed — showing cached value.")
        elif status == "error":
            st.error(f"❌ {name}: unavailable.")

    # Current values
    y3m   = _current(data.get("yield_3m"))
    y2yr  = _current(data.get("yield_2yr"))
    y10yr = _current(data.get("yield_10yr"))
    y30yr = _current(data.get("yield_30yr"))
    be    = _current(data.get("breakeven_10yr"))
    tp    = _current(data.get("term_premium_10yr"))

    raw_spread    = _current(data.get("spread_2s10s"))
    spread_bps    = raw_spread * 100 if raw_spread is not None else None

    raw_spread_20 = _offset(data.get("spread_2s10s"), 20)
    spread_bps_20 = raw_spread_20 * 100 if raw_spread_20 is not None else None
    y2yr_20       = _offset(data.get("yield_2yr"), 20)

    # 30s2s
    s30s2s_series = _calculate_30s2s(data)
    spread_30s2s  = _current(s30s2s_series) if s30s2s_series is not None else None

    # Regime classification (uses 2s10s and 2yr per spec)
    curve_label = "—"
    if all(v is not None for v in [spread_bps, spread_bps_20, y2yr, y2yr_20]):
        curve_label = classify_yield_curve_move(
            spread_bps, spread_bps_20, y2yr, y2yr_20
        )

    # Composite score
    panel_score = calculate_panel_score("bonds", {
        "yield_10yr":              y10yr,
        "term_premium":            tp,
        "spread_2s10s_normalized": spread_bps,
        "breakeven_10yr":          be,
    })

    # Alert banners
    for severity, msg in _check_active_alerts(y10yr, be):
        if severity == "critical":
            st.error(f"🚨 {msg}")
        else:
            st.warning(f"⚠️ {msg}")

    score_color = "#FF4444" if panel_score >= 7 else "#FFCC00" if panel_score >= 5 else "#00CC44"
    st.markdown(
        f"<div style='font-size:13px;color:#888;'>Bond Stress Score</div>"
        f"<div style='font-size:26px;font-weight:bold;color:{score_color};"
        f"margin-bottom:14px;'>{panel_score} / 10</div>",
        unsafe_allow_html=True,
    )

    # ---- Sub-panel 3a: Yield Levels ----
    st.markdown("**Sub-panel 3a — Yield Levels**")

    col_b, col_c = st.columns([1, 2])

    with col_b:
        if y10yr is not None:
            render_status_badge(
                "10-Year Yield", f"{y10yr:.2f}%", _yield_status(y10yr),
                "⚠️ Above 5.0% threshold" if y10yr >= 5.0 else "Key benchmark | threshold: 5.0%",
            )
        if y2yr is not None:
            render_status_badge(
                "2-Year Yield", f"{y2yr:.2f}%", _yield_status(y2yr),
                "Near-term rate expectations | Fed policy sensitive",
            )
        if y30yr is not None:
            render_status_badge(
                "30-Year Yield", f"{y30yr:.2f}%", _yield_status(y30yr),
                "Most sensitive to fiscal confidence",
            )
        if y3m is not None:
            render_status_badge(
                "3-Month T-Bill", f"{y3m:.2f}%", "green",
                "Fed policy proxy",
            )
        if tp is not None:
            render_status_badge(
                "10Y Term Premium (ACM)", f"{tp:.2f}%", _term_premium_status(tp),
                "Risk premium for holding duration | NY Fed estimate",
            )
        if be is not None:
            render_status_badge(
                "10Y Breakeven Inflation", f"{be:.2f}%", _breakeven_status(be),
                "Bond market inflation expectation",
            )

    with col_c:
        render_yield_curve_snapshot(data)
        render_10yr_chart(data, trading_days)
        render_term_premium_chart(data, trading_days)

    st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)

    # ---- Sub-panel 3b: Yield Curve Shape ----
    st.markdown("**Sub-panel 3b — Yield Curve Shape**")

    col_b2, col_c2 = st.columns([1, 2])

    with col_b2:
        if spread_bps is not None:
            render_status_badge(
                "2s10s Spread (10Y − 2Y)", f"{spread_bps:+.0f} bps",
                _2s10s_status(spread_bps),
                "Recession predictor | inverted = elevated risk",
            )
        if spread_30s2s is not None:
            render_status_badge(
                "30s2s Spread (30Y − 2Y)", f"{spread_30s2s:+.0f} bps",
                _30s2s_status(spread_30s2s),
                "Long-end fiscal confidence",
            )
        if curve_label != "—":
            regime_color = (
                "red"    if curve_label in ("Bear Steepener", "Bear Flattener")
                else "yellow" if curve_label in ("Bull Flattener",)
                else "green"
            )
            render_status_badge(
                "Curve Regime (20-day)", curve_label, regime_color,
                "Based on 2yr yield direction + 2s10s spread change",
            )

    with col_c2:
        render_spreads_chart(data, trading_days)

    st.caption(
        "Sources: FRED — DGS3MO, DGS2, DGS10, DGS30, T10YIE, THREEFYTP10, T10Y2Y. "
        "~1 business day lag for daily series. "
        "30s2s calculated from DGS30 − DGS2."
    )
