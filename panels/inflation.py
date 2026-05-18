"""Panel 1 — Inflation Pressure Gauge.

Leads the crisis sequence by ~4 months.

FRED series (auto-fetched):
  - CPI, PPI, Oil, Breakeven (standard)
  - Philadelphia Fed Mfg Prices Paid (PPCDFSA066MSFRBPHI) — diffusion index
  - Dallas Fed Prices Paid for Raw Materials (PRMUAMFRBDAL) — diffusion index

Manual inputs (sidebar, stored in SQLite):
  - ISM Mfg Prices Paid (0–100 scale)
  - ISM Services Prices Paid (0–100 scale)
  - KC Fed Prices Paid for Raw Materials (diffusion index, supplementary only)

Scale warning: Philly/Dallas use a diffusion index (roughly -80 to +80, neutral=0).
ISM uses a 0–100 scale (neutral=50). These are NEVER displayed on the same axis.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

from data.fred import fetch_with_fallback
from data.cache import (
    get_last_6_months,
    get_manual_input,
    get_manual_input_with_meta,
    save_manual_input,
)
from data.calculated import yoy_pct_change, calculate_panel_score
from config import FRED_SERIES, PLOTLY_LAYOUT
from panels.bonds import render_status_badge


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def load_inflation_data() -> tuple[dict, dict]:
    """Fetch Panel 1 FRED series. Returns (data_dict, statuses_dict)."""
    series_map = {
        "cpi":                    ("fred", 24),
        "ppi":                    ("fred", 24),
        "philly_fed_prices_paid": ("fred", 24),
        "dallas_fed_prices_paid": ("fred", 24),
        "oil_wti":                ("fred", 4),   # daily
        "breakeven_10yr":         ("fred", 4),   # daily
    }
    data, statuses = {}, {}
    for name, (source, ttl) in series_map.items():
        series, status = fetch_with_fallback(
            FRED_SERIES[name], source=source, cache_max_age_hours=ttl
        )
        data[name] = series
        statuses[name] = status
    return data, statuses


# ---------------------------------------------------------------------------
# Composite score
# ---------------------------------------------------------------------------

def compute_inflation_score(
    data: dict,
    manual_data: dict | None = None,
) -> float:
    """Compute inflation stress score (1–10).

    Uses ISM weights when ISM data is available for the current month,
    otherwise falls back to regional proxy weights (Philly + Dallas Fed).
    """
    ppi_yoy = _current(yoy_pct_change(data.get("ppi")))
    oil_yoy = _current(yoy_pct_change(data.get("oil_wti")))
    be = _current(data.get("breakeven_10yr"))

    ism_mfg = manual_data.get("ism_mfg_prices") if manual_data else None
    ism_svc = manual_data.get("ism_svc_prices") if manual_data else None
    ism_entered = ism_mfg is not None or ism_svc is not None

    if ism_entered:
        ism_avg = _ism_average_vals(ism_mfg, ism_svc)
        return calculate_panel_score("inflation_ism", {
            "ppi_yoy":        ppi_yoy,
            "ism_avg_prices": ism_avg,
            "oil_yoy":        oil_yoy,
            "breakeven_10yr": be,
        })

    philly = _current(data.get("philly_fed_prices_paid"))
    dallas = _current(data.get("dallas_fed_prices_paid"))
    return calculate_panel_score("inflation_regional", {
        "ppi_yoy":                ppi_yoy,
        "philly_fed_prices_paid": philly,
        "dallas_fed_prices_paid": dallas,
        "oil_yoy":                oil_yoy,
        "breakeven_10yr":         be,
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


def _ism_average_vals(mfg: float | None, svc: float | None) -> float | None:
    """Average of two optional ISM values."""
    vals = [v for v in (mfg, svc) if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def _base_layout(title: str, height: int, **extra) -> dict:
    layout = dict(PLOTLY_LAYOUT)
    layout.update({"title": title, "height": height})
    layout.update(extra)
    return layout


# ---------------------------------------------------------------------------
# Status helpers
# ---------------------------------------------------------------------------

def _ppi_status(v: float | None) -> str:
    if v is None: return "green"
    if v > 5: return "red"
    if v > 3: return "yellow"
    return "green"


def _diffusion_status(v: float | None) -> str:
    """Status for diffusion index series (Philly/Dallas/KC Fed). Neutral = 0."""
    if v is None: return "green"
    if v > 40: return "red"
    if v > 0: return "yellow"
    return "green"


def _ism_status(v: float | None) -> str:
    """Status for ISM 0–100 scale. Neutral = 50."""
    if v is None: return "green"
    if v > 65: return "red"
    if v > 55: return "yellow"
    return "green"


def _oil_status(v: float | None) -> str:
    if v is None: return "green"
    if v > 20: return "red"
    if v > 0: return "yellow"
    return "green"


def _breakeven_status(v: float | None) -> str:
    if v is None: return "green"
    if v > 2.75: return "red"
    if v > 2.5: return "yellow"
    return "green"


def _bar_color_diffusion(value: float) -> str:
    """Per-bar colour for a diffusion index bar chart."""
    if value > 40:
        return "#FF4444"
    if value > 20:
        return "#FFCC00"
    if value > 0:
        return "#88BBFF"
    return "#00CC44"


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def render_cpi_ppi_chart(data: dict, trading_days: int) -> None:
    """CPI vs PPI YoY % — dual line chart (CPI white, PPI orange)."""
    # Apply YoY to full series first, then tail — shifting on a trimmed series
    # would lose all history needed for the 12-period lookback.
    cpi_s = data.get("cpi")
    ppi_s = data.get("ppi")

    fig = go.Figure()
    if ppi_s is not None and not ppi_s.empty:
        ppi_yoy = _tail(yoy_pct_change(ppi_s).dropna(), trading_days)
        if ppi_yoy is not None and not ppi_yoy.empty:
            fig.add_trace(go.Scatter(
                x=ppi_yoy.index, y=ppi_yoy.values,
                name="PPI YoY %", mode="lines",
                line=dict(color="#FF8800", width=2),
            ))
    if cpi_s is not None and not cpi_s.empty:
        cpi_yoy = _tail(yoy_pct_change(cpi_s).dropna(), trading_days)
        if cpi_yoy is not None and not cpi_yoy.empty:
            fig.add_trace(go.Scatter(
                x=cpi_yoy.index, y=cpi_yoy.values,
                name="CPI YoY %", mode="lines",
                line=dict(color="#FFFFFF", width=2),
            ))
    fig.add_hline(y=2.0, line_color="#444444", line_dash="dot", line_width=1,
                  annotation_text="2% target", annotation_position="right",
                  annotation=dict(font_color="#888888", font_size=10))
    fig.update_layout(**_base_layout(
        "CPI vs PPI — Year-over-Year %", 220,
        yaxis_title="YoY %",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    ))
    st.plotly_chart(fig, use_container_width=True)


def render_regional_fed_chart(data: dict, trading_days: int,
                               kc_val: float | None = None,
                               kc_month: str | None = None) -> None:
    """Dual grouped bar chart — Philly Fed (blue) and Dallas Fed (teal).

    Both series use a diffusion index scale (roughly -80 to +80, neutral=0).
    Bars are coloured by threshold band. KC Fed (manual) shown if entered.
    This chart uses its OWN y-axis — never mixed with the ISM 0-100 scale.
    """
    philly_s = _tail(data.get("philly_fed_prices_paid"), trading_days)
    dallas_s = _tail(data.get("dallas_fed_prices_paid"), trading_days)

    fig = go.Figure()

    if philly_s is not None and not philly_s.empty:
        colors = [_bar_color_diffusion(v) for v in philly_s.values]
        fig.add_trace(go.Bar(
            x=philly_s.index, y=philly_s.values,
            name="Philly Fed (Mfg)",
            marker_color=colors,
            opacity=0.85,
            offsetgroup=0,
        ))

    if dallas_s is not None and not dallas_s.empty:
        # Teal with same threshold colouring, slightly lighter
        colors = [_bar_color_diffusion(v) for v in dallas_s.values]
        teal_colors = [c.replace("#4444", "#4444").replace("#FF4444", "#FF8888")
                       .replace("#FFCC00", "#FFE066").replace("#88BBFF", "#44CCBB")
                       .replace("#00CC44", "#44EE88") for c in colors]
        fig.add_trace(go.Bar(
            x=dallas_s.index, y=dallas_s.values,
            name="Dallas Fed (Raw Materials)",
            marker_color=teal_colors,
            opacity=0.85,
            offsetgroup=1,
        ))

    # Threshold reference lines
    fig.add_hline(y=40, line_color="#FF4444", line_dash="dash", line_width=1,
                  annotation_text="40 (red)", annotation_position="right",
                  annotation=dict(font_color="#FF4444", font_size=10))
    fig.add_hline(y=20, line_color="#FFCC00", line_dash="dash", line_width=1,
                  annotation_text="20 (yellow)", annotation_position="right",
                  annotation=dict(font_color="#FFCC00", font_size=10))
    fig.add_hline(y=0, line_color="#555555", line_width=1)

    # KC Fed as annotation if entered — not a time series bar, just a marker
    if kc_val is not None and kc_month:
        fig.add_annotation(
            xref="paper", yref="y",
            x=1.0, y=kc_val,
            text=f"KC Fed ({kc_month}): {kc_val:+.1f}",
            showarrow=True, arrowhead=2,
            arrowcolor="#FFAA44", font=dict(color="#FFAA44", size=10),
            ax=40, ay=0,
        )

    fig.update_layout(**_base_layout(
        "Regional Fed Prices Paid — Diffusion Index (neutral = 0)", 240,
        yaxis_title="Diffusion Index (% rising minus % falling)",
        barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    ))
    st.plotly_chart(fig, use_container_width=True)


def render_oil_chart(data: dict, trading_days: int) -> None:
    """WTI crude oil YoY % change."""
    oil_s = data.get("oil_wti")
    if oil_s is None or oil_s.empty:
        st.warning("Oil price data unavailable.")
        return

    oil_yoy = yoy_pct_change(oil_s).dropna()
    if oil_yoy.empty:
        st.warning("Insufficient oil history for YoY calculation.")
        return
    oil_yoy = oil_yoy.tail(trading_days)

    fig = go.Figure()
    pos = oil_yoy.clip(lower=0)
    neg = oil_yoy.clip(upper=0)
    fig.add_trace(go.Scatter(
        x=oil_yoy.index, y=pos.values, mode="lines",
        line=dict(color="rgba(255,68,68,0)", width=0),
        fill="tozeroy", fillcolor="rgba(255,68,68,0.20)",
        showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=oil_yoy.index, y=neg.values, mode="lines",
        line=dict(color="rgba(0,204,68,0)", width=0),
        fill="tozeroy", fillcolor="rgba(0,204,68,0.15)",
        showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=oil_yoy.index, y=oil_yoy.values,
        name="WTI Oil YoY %", mode="lines",
        line=dict(color="#AAAAAA", width=1.5),
    ))
    fig.add_hline(y=0, line_color="#555555", line_width=1)
    fig.update_layout(**_base_layout(
        "WTI Crude Oil — Year-over-Year %", 200,
        yaxis_title="YoY %", showlegend=False,
    ))
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Manual input sidebar
# ---------------------------------------------------------------------------

def render_manual_input_sidebar() -> None:
    """Collapsible sidebar panel for ISM and KC Fed manual data entry.

    Stores values in SQLite — enter once per month after each release.
    Current month is pre-selected. Persists across sessions.
    """
    with st.sidebar.expander("📝 Manual Data Entry", expanded=False):
        st.caption("ISM and KC Fed data — enter after each monthly release")

        months = get_last_6_months()
        reference_month = st.selectbox(
            "Reference Month",
            options=months,
            index=0,
            key="manual_input_month",
        )

        # ISM Manufacturing Prices Paid
        st.markdown("**ISM Manufacturing Prices Paid** (0–100 scale, 50 = neutral)")
        st.caption("Released first business day of month — ismworld.org")
        mfg_meta = get_manual_input_with_meta("ism_mfg_prices", reference_month)
        mfg_default = mfg_meta["value"] if mfg_meta else 0.0
        ism_mfg = st.number_input(
            "ISM Mfg Prices Paid",
            min_value=0.0, max_value=100.0, step=0.1,
            value=mfg_default,
            key=f"ism_mfg_{reference_month}",
        )
        if mfg_meta:
            st.caption(f"Last entered: {mfg_meta['entered_at'][:16]} UTC  |  For: {reference_month}")

        # ISM Services Prices Paid
        st.markdown("**ISM Services Prices Paid** (0–100 scale, 50 = neutral)")
        st.caption("Released third business day of month — ismworld.org")
        svc_meta = get_manual_input_with_meta("ism_svc_prices", reference_month)
        svc_default = svc_meta["value"] if svc_meta else 0.0
        ism_svc = st.number_input(
            "ISM Svc Prices Paid",
            min_value=0.0, max_value=100.0, step=0.1,
            value=svc_default,
            key=f"ism_svc_{reference_month}",
        )
        if svc_meta:
            st.caption(f"Last entered: {svc_meta['entered_at'][:16]} UTC  |  For: {reference_month}")

        # KC Fed Prices Paid (diffusion index, supplementary)
        st.markdown("**KC Fed Prices Paid — Raw Materials** (diffusion index)")
        st.caption("Released ~4th week of month — kansascityfed.org/surveys/manufacturing-survey")
        kc_meta = get_manual_input_with_meta("kc_fed_prices_paid", reference_month)
        kc_default = kc_meta["value"] if kc_meta else 0.0
        kc_fed = st.number_input(
            "KC Fed Prices Paid",
            min_value=-100.0, max_value=100.0, step=0.1,
            value=kc_default,
            key=f"kc_fed_{reference_month}",
        )
        if kc_meta:
            st.caption(f"Last entered: {kc_meta['entered_at'][:16]} UTC  |  For: {reference_month}")

        st.markdown("---")
        st.caption(
            "⚠️ **Scale note:** ISM uses 0–100 (neutral=50). "
            "KC Fed uses diffusion index (neutral=0). Never compared directly."
        )

        if st.button("💾 Save Manual Inputs", key="save_manual_inputs"):
            # Only save non-zero values (zero is the widget default, not a data entry)
            if ism_mfg > 0:
                save_manual_input("ism_mfg_prices", reference_month, ism_mfg)
            if ism_svc > 0:
                save_manual_input("ism_svc_prices", reference_month, ism_svc)
            # KC Fed can legitimately be 0 (no change) — save always if changed from default
            if kc_fed != 0.0 or kc_meta is not None:
                save_manual_input("kc_fed_prices_paid", reference_month, kc_fed)
            st.success(f"✓ Saved for {reference_month}")
            st.rerun()


# ---------------------------------------------------------------------------
# Main panel renderer
# ---------------------------------------------------------------------------

def render_panel_inflation(
    trading_days: int = 252,
    manual_data: dict | None = None,
) -> None:
    st.subheader("Panel 1 — Inflation Pressure Gauge")

    with st.spinner("Loading inflation data…"):
        data, statuses = load_inflation_data()

    for name, status in statuses.items():
        if status == "stale":
            st.warning(f"⚠️ {name}: live fetch failed — showing cached value.")
        elif status == "error":
            st.error(f"❌ {name}: unavailable.")

    # Manual data for current month
    if manual_data is None:
        from data.cache import get_current_month_manual
        manual_data = get_current_month_manual()

    ism_mfg_val = manual_data.get("ism_mfg_prices")
    ism_svc_val = manual_data.get("ism_svc_prices")
    kc_val      = manual_data.get("kc_fed_prices_paid")
    ref_month   = manual_data.get("reference_month", "")
    ism_entered = ism_mfg_val is not None or ism_svc_val is not None

    # Computed display values
    cpi_yoy_val   = _current(yoy_pct_change(data["cpi"])) if data.get("cpi") is not None else None
    ppi_yoy_val   = _current(yoy_pct_change(data["ppi"])) if data.get("ppi") is not None else None
    oil_yoy_val   = _current(yoy_pct_change(data["oil_wti"])) if data.get("oil_wti") is not None else None
    philly_val    = _current(data.get("philly_fed_prices_paid"))
    dallas_val    = _current(data.get("dallas_fed_prices_paid"))
    be_val        = _current(data.get("breakeven_10yr"))
    ism_avg_val   = _ism_average_vals(ism_mfg_val, ism_svc_val)

    panel_score = compute_inflation_score(data, manual_data)
    score_color = "#FF4444" if panel_score >= 7 else "#FFCC00" if panel_score >= 5 else "#00CC44"

    # ISM mode indicator banner
    if ism_entered:
        st.markdown(
            f"<div style='background:rgba(0,204,68,0.08);border-left:3px solid #00CC44;"
            f"padding:6px 10px;margin:4px 0 8px 0;font-size:12px;color:#88EE88;'>"
            f"✓ ISM data entered for {ref_month} — using ISM weights in composite score</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='background:rgba(100,100,100,0.1);border-left:3px solid #666;"
            "padding:6px 10px;margin:4px 0 8px 0;font-size:12px;color:#999;'>"
            "⚠️ ISM pending — showing regional proxies (Philly Fed + Dallas Fed). "
            "Enter ISM data via sidebar after each release.</div>",
            unsafe_allow_html=True,
        )

    col_b, col_c = st.columns([1, 2])

    with col_b:
        st.markdown(
            f"<div style='font-size:13px;color:#888;'>Inflation Stress Score</div>"
            f"<div style='font-size:26px;font-weight:bold;color:{score_color};"
            f"margin-bottom:12px;'>{panel_score} / 10</div>",
            unsafe_allow_html=True,
        )
        mode_label = "ISM weights" if ism_entered else "Regional proxy weights"
        st.caption(f"Composite using: {mode_label}")

        if ppi_yoy_val is not None:
            render_status_badge(
                "PPI YoY %", f"{ppi_yoy_val:+.1f}%", _ppi_status(ppi_yoy_val),
                "🟢 <3% | 🟡 3–5% | 🔴 >5% | leads CPI by ~2 months",
            )
        if cpi_yoy_val is not None:
            cpi_s = "red" if cpi_yoy_val > 5 else "yellow" if cpi_yoy_val > 3 else "green"
            render_status_badge(
                "CPI YoY %", f"{cpi_yoy_val:+.1f}%", cpi_s,
                "Headline consumer inflation (BLS via FRED)",
            )

        # Regional Fed proxies (diffusion index — own section)
        st.markdown(
            "<div style='font-size:11px;color:#666;margin:8px 0 2px 0;"
            "text-transform:uppercase;letter-spacing:0.5px;'>"
            "Regional Fed Proxies — Diffusion Index (neutral = 0)</div>",
            unsafe_allow_html=True,
        )
        if philly_val is not None:
            render_status_badge(
                "Philly Fed Prices Paid", f"{philly_val:+.1f}",
                _diffusion_status(philly_val),
                "🟢 <0 | 🟡 0–40 | 🔴 >40 | diffusion index, not 0–100 scale",
            )
        if dallas_val is not None:
            render_status_badge(
                "Dallas Fed Prices Paid", f"{dallas_val:+.1f}",
                _diffusion_status(dallas_val),
                "🟢 <0 | 🟡 0–40 | 🔴 >40 | energy-sector skew",
            )
        if kc_val is not None:
            render_status_badge(
                "KC Fed Prices Paid ✎", f"{kc_val:+.1f}",
                _diffusion_status(kc_val),
                f"Supplementary only — does not affect score | For: {ref_month}",
            )

        # ISM manual inputs (0–100 scale — own section, clearly separated)
        if ism_entered:
            st.markdown(
                "<div style='font-size:11px;color:#666;margin:8px 0 2px 0;"
                "text-transform:uppercase;letter-spacing:0.5px;'>"
                "ISM Manual Data — 0–100 Scale (neutral = 50)</div>",
                unsafe_allow_html=True,
            )
            if ism_mfg_val is not None:
                render_status_badge(
                    f"ISM Mfg Prices Paid ✓ {ref_month}",
                    f"{ism_mfg_val:.1f}",
                    _ism_status(ism_mfg_val),
                    "🟢 <55 | 🟡 55–65 | 🔴 >65 | leads PPI by ~2 months",
                )
            if ism_svc_val is not None:
                render_status_badge(
                    f"ISM Svc Prices Paid ✓ {ref_month}",
                    f"{ism_svc_val:.1f}",
                    _ism_status(ism_svc_val),
                    "🟢 <55 | 🟡 55–65 | 🔴 >65 | services inflation pressure",
                )
            if ism_avg_val is not None:
                render_status_badge(
                    "ISM Average (composite input)",
                    f"{ism_avg_val:.1f}",
                    _ism_status(ism_avg_val),
                    "Average of Mfg + Svc — used in score weighting",
                )

        if oil_yoy_val is not None:
            render_status_badge(
                "WTI Oil YoY %", f"{oil_yoy_val:+.1f}%",
                _oil_status(oil_yoy_val),
                "🟢 negative | 🟡 0–20% | 🔴 >20% | primary PPI driver",
            )
        if be_val is not None:
            render_status_badge(
                "10Y Breakeven Inflation", f"{be_val:.2f}%",
                _breakeven_status(be_val),
                "Bond market inflation expectation",
            )

    with col_c:
        render_cpi_ppi_chart(data, trading_days)
        render_regional_fed_chart(data, trading_days, kc_val=kc_val, kc_month=ref_month)
        render_oil_chart(data, trading_days)

    sources_line = (
        "Sources: FRED — CPIAUCSL, PPIACO, PPCDFSA066MSFRBPHI (Philly Fed), "
        "PRMUAMFRBDAL (Dallas Fed), DCOILWTICO, T10YIE. ~1 day lag. "
        "ISM + KC Fed: manual entry via sidebar."
    )
    st.caption(sources_line)
