"""Panel 5 — Dollar & Credit Stress.

Sub-panels per PRD:
  5a — Dollar Signals (trade-weighted USD, USD/CAD, dollar/yield divergence flag)
  5b — Credit Spreads (IG OAS, HY OAS)
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from data.fred import fetch_with_fallback
from data.calculated import (
    dollar_yield_divergence,
    calculate_sofr_fed_funds_spread,
    calculate_fed_balance_sheet_wow,
)
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
        "yield_10yr",       # needed for divergence flag
        # Sub-panel 5c — repo market
        "sofr",
        "fed_funds",
        "fed_balance_sheet",
    ]
    data, statuses = {}, {}
    for name in series_names:
        ttl = 7 * 24 if name == "fed_balance_sheet" else 4
        series, status = fetch_with_fallback(
            FRED_SERIES[name], source="fred", cache_max_age_hours=ttl
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
    clean = s.dropna()
    if clean.empty:
        return None
    return float(clean.iloc[-1])


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
# Sub-panel 5c — Repo Market
# ---------------------------------------------------------------------------

def _render_repo_chart(spread_series: pd.Series, trading_days: int) -> None:
    s = _tail(spread_series, trading_days)
    if s is None or s.empty:
        st.warning("SOFR/Fed Funds spread data unavailable.")
        return

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=s.index, y=s.values,
        name="SOFR − Fed Funds Spread",
        mode="lines",
        line=dict(color="#FF8800", width=2),
        fill="tozeroy",
        fillcolor="rgba(255,136,0,0.10)",
    ))
    layout = dict(PLOTLY_LAYOUT)
    layout.update({
        "title":  "SOFR vs Fed Funds Spread",
        "height": 220,
        "yaxis":  dict(title="Spread (%)"),
        "showlegend": False,
    })
    fig.add_hline(
        y=0.25, line_color="#FF4444", line_dash="dash", line_width=1.2,
        annotation_text="Alert threshold (25bps)",
        annotation_position="top right",
        annotation=dict(font_color="#FF4444", font_size=10),
    )
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True)


def _render_fed_balance_chart(
    balance_series: pd.Series,
    wow_series: pd.Series,
    trading_days: int,
) -> None:
    bal = _tail(balance_series, trading_days)
    wow = _tail(wow_series, trading_days)
    if bal is None or bal.empty:
        st.warning("Fed balance sheet data unavailable.")
        return

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=bal.index, y=bal.values,
        name="Fed Total Assets ($B)",
        mode="lines",
        line=dict(color="#4488FF", width=2),
        fill="tozeroy",
        fillcolor="rgba(68,136,255,0.08)",
        yaxis="y",
    ))
    if wow is not None and not wow.empty:
        fig.add_trace(go.Bar(
            x=wow.index, y=wow.values,
            name="WoW Change ($B)",
            marker_color=[
                "rgba(255,68,68,0.65)" if v > 0 else "rgba(0,204,68,0.65)"
                for v in wow.values
            ],
            yaxis="y2",
        ))
    layout = dict(PLOTLY_LAYOUT)
    layout.update({
        "title":  "Fed Balance Sheet (WALCL)",
        "height": 230,
        "yaxis":  dict(title="Total Assets ($B)"),
        "yaxis2": dict(
            title="WoW Change ($B)",
            overlaying="y", side="right",
            zeroline=True, zerolinecolor="#444444",
            titlefont=dict(color="#AAAAAA"),
        ),
        "legend": dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    })
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True)


def render_subpanel_5c(data: dict, trading_days: int) -> None:
    st.markdown("**Sub-panel 5c — Repo Market**")

    sofr_s     = data.get("sofr")
    ff_s       = data.get("fed_funds")
    balance_s  = data.get("fed_balance_sheet")

    spread_s  = None
    wow_s     = None
    if sofr_s is not None and ff_s is not None:
        spread_s = calculate_sofr_fed_funds_spread(sofr_s, ff_s)
    if balance_s is not None:
        wow_s = calculate_fed_balance_sheet_wow(balance_s)

    sofr_val    = _current(sofr_s)
    ff_val      = _current(ff_s)
    spread_val  = _current(spread_s)
    balance_val = _current(balance_s)
    wow_val     = _current(wow_s)

    col_badges, col_charts = st.columns([1, 2])

    with col_badges:
        if sofr_val is not None:
            render_status_badge(
                "SOFR Rate",
                f"{sofr_val:.3f}%",
                "green",
                "Secured Overnight Financing Rate (NY Fed via FRED)",
            )
        if ff_val is not None:
            render_status_badge(
                "Effective Fed Funds Rate",
                f"{ff_val:.2f}%",
                "green",
                "FRED: DFF — daily effective rate",
            )
        if spread_val is not None:
            spread_bps = spread_val * 100
            spread_status = (
                "red"    if spread_bps > 25
                else "yellow" if spread_bps > 10
                else "green"
            )
            render_status_badge(
                "SOFR − Fed Funds Spread",
                f"{spread_bps:+.1f} bps",
                spread_status,
                "🟢 <10bps | 🟡 10–25bps | 🔴 >25bps — Alert threshold: 25bps",
            )
        if balance_val is not None:
            render_status_badge(
                "Fed Total Assets (WALCL)",
                f"${balance_val:,.0f}B",
                "green",
                "Weekly — Fed balance sheet size",
            )
        if wow_val is not None:
            wow_status = (
                "red"    if wow_val > 50
                else "yellow" if wow_val > 20
                else "green"
            )
            render_status_badge(
                "Fed Balance Sheet WoW Change",
                f"${wow_val:+,.0f}B",
                wow_status,
                "🟢 <$20B | 🟡 $20–50B | 🔴 >$50B — Alert threshold: $50B expansion",
            )

    with col_charts:
        if spread_s is not None and not spread_s.empty:
            _render_repo_chart(spread_s, trading_days)
        if balance_s is not None and not balance_s.empty:
            _render_fed_balance_chart(balance_s, wow_s, trading_days)

    st.caption(
        "Sources: FRED — SOFR (NY Fed), DFF (Effective Fed Funds), WALCL (Fed total assets weekly). "
        "SOFR/FF spread and WoW balance sheet change are calculated series."
    )


# ---------------------------------------------------------------------------
# Score export (used by app.py for crisis stage banner)
# ---------------------------------------------------------------------------

def compute_credit_score(data: dict) -> tuple[float, str, dict]:
    """Return (panel_score, divergence_flag, repo_values).

    repo_values contains sofr_fed_funds_spread and fed_balance_sheet_wow_change
    for alert evaluation in app.py.
    """
    ig_raw  = data.get("ig_spread")
    hy_raw  = data.get("hy_spread")
    yield_s = data.get("yield_10yr")
    dxy_s   = data.get("dxy_proxy")
    sofr_s  = data.get("sofr")
    ff_s    = data.get("fed_funds")
    bal_s   = data.get("fed_balance_sheet")

    ig_bps = float(ig_raw.dropna().iloc[-1]) * 100 if ig_raw is not None and not ig_raw.empty else None
    hy_bps = float(hy_raw.dropna().iloc[-1]) * 100 if hy_raw is not None and not hy_raw.empty else None

    div_flag = "neutral"
    if yield_s is not None and dxy_s is not None:
        div_flag = dollar_yield_divergence(yield_s, dxy_s)["flag"]

    flag_numeric = {"neutral": 1, "normal_stress": 5, "crisis_signal": 10}.get(div_flag, 1)

    from data.calculated import calculate_panel_score
    score = calculate_panel_score("credit", {
        "ig_spread_bps":           ig_bps,
        "hy_spread_bps":           hy_bps,
        "dollar_yield_flag_score": flag_numeric,
    })

    # Repo market values for alert engine
    spread_val = None
    if sofr_s is not None and ff_s is not None:
        spread_s = calculate_sofr_fed_funds_spread(sofr_s, ff_s)
        if not spread_s.empty:
            spread_val = float(spread_s.dropna().iloc[-1])

    wow_val = None
    if bal_s is not None and not bal_s.empty:
        wow_s = calculate_fed_balance_sheet_wow(bal_s)
        if not wow_s.empty:
            wow_val = float(wow_s.dropna().iloc[-1])

    repo_values = {
        "sofr_fed_funds_spread":       spread_val,
        "fed_balance_sheet_wow_change": wow_val,
    }

    return score, div_flag, repo_values


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

    st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)

    render_subpanel_5c(data, trading_days)
