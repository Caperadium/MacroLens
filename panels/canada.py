"""Canada Panel — GoC yields, CAD/USD, spread vs UST, Canadian CPI.

GoC yields: Bank of Canada Valet API (7-day cache TTL).
Canadian CPI, USD/CAD: FRED.
Key visual: GoC 10yr vs UST 10yr spread — widening = Canadian bonds outperforming.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from data.boc import fetch_boc_with_fallback
from data.fred import fetch_with_fallback
from data.calculated import yoy_pct_change
from config import BOC_SERIES, FRED_SERIES, PLOTLY_LAYOUT
from panels.bonds import render_status_badge


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def load_canada_data() -> tuple[dict, dict]:
    """Fetch Canada panel series from BoC Valet and FRED."""
    data, statuses = {}, {}

    # BoC Valet (7-day TTL)
    for name, series_id in BOC_SERIES.items():
        series, status = fetch_boc_with_fallback(series_id, cache_max_age_hours=168)
        data[name]     = series
        statuses[name] = status

    # FRED supplements
    for name, ttl in [("canada_cpi", 24), ("yield_10yr", 4)]:
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


def _base_layout(title: str, height: int, **extra) -> dict:
    layout = dict(PLOTLY_LAYOUT)
    layout.update({"title": title, "height": height})
    layout.update(extra)
    return layout


def _goc_ust_spread(data: dict) -> pd.Series | None:
    """GoC 10yr minus UST 10yr in basis points."""
    goc = data.get("goc_10yr")
    ust = data.get("yield_10yr")
    if goc is None or ust is None:
        return None
    combined = pd.DataFrame({"goc": goc, "ust": ust}).dropna()
    if combined.empty:
        return None
    return (combined["goc"] - combined["ust"]) * 100  # bps


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def render_goc_yield_curve(data: dict) -> None:
    """GoC yield curve snapshot — current vs 1M ago vs 6M ago."""
    maturities = ["2Y", "5Y", "10Y", "30Y"]
    keys       = ["goc_2yr", "goc_5yr", "goc_10yr", "goc_30yr"]

    def _val(key, offset=0):
        s = data.get(key)
        if s is None or s.empty:
            return None
        clean = s.dropna()
        if offset == 0:
            return float(clean.iloc[-1])
        idx = max(0, len(clean) - 1 - offset)
        return float(clean.iloc[idx])

    current = [_val(k, 0)   for k in keys]
    one_mo  = [_val(k, 21)  for k in keys]
    six_mo  = [_val(k, 126) for k in keys]

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
            line=dict(color="#FF4444", width=3), marker=dict(size=7),
        ))

    fig.update_layout(**_base_layout(
        "GoC Yield Curve — Current vs 1M ago vs 6M ago", 250,
        xaxis_title="Maturity", yaxis_title="Yield (%)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    ))
    st.plotly_chart(fig, use_container_width=True)


def render_goc_ust_spread_chart(data: dict, trading_days: int) -> None:
    """GoC 10yr minus UST 10yr spread over time.

    Widening spread = GoC outperforming UST (GoC yield rising less than UST).
    A more negative spread means Canada outperforming on an absolute basis.
    """
    spread = _goc_ust_spread(data)
    if spread is None or spread.empty:
        st.warning("GoC/UST spread data unavailable.")
        return

    spread = spread.tail(trading_days)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=spread.index, y=spread.values,
        name="GoC 10yr − UST 10yr", mode="lines",
        line=dict(color="#FF4444", width=2),
        fill="tozeroy", fillcolor="rgba(255,68,68,0.10)",
    ))
    fig.add_hline(y=0, line_color="#555555", line_width=1)
    fig.update_layout(**_base_layout(
        "GoC 10yr vs UST 10yr Spread (bps) — Negative = Canada Outperforming", 220,
        yaxis_title="Basis Points", showlegend=False,
    ))
    st.plotly_chart(fig, use_container_width=True)


def render_goc_10yr_chart(data: dict, trading_days: int) -> None:
    """GoC 10yr and UST 10yr overlaid."""
    goc = _tail(data.get("goc_10yr"), trading_days)
    ust = _tail(data.get("yield_10yr"), trading_days)

    fig = go.Figure()
    if ust is not None and not ust.empty:
        fig.add_trace(go.Scatter(
            x=ust.index, y=ust.values,
            name="UST 10yr", mode="lines",
            line=dict(color="#FFFFFF", width=1.5, dash="dot"),
        ))
    if goc is not None and not goc.empty:
        fig.add_trace(go.Scatter(
            x=goc.index, y=goc.values,
            name="GoC 10yr", mode="lines",
            line=dict(color="#FF4444", width=2),
        ))

    fig.update_layout(**_base_layout(
        "GoC 10yr vs UST 10yr", 210,
        yaxis_title="Yield (%)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    ))
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Main panel renderer
# ---------------------------------------------------------------------------

def render_panel_canada(trading_days: int = 252) -> None:
    st.subheader("Canada Panel")

    with st.spinner("Loading Canada data…"):
        data, statuses = load_canada_data()

    for name, status in statuses.items():
        if status == "stale":
            st.warning(f"⚠️ {name}: live fetch failed — showing cached value.")
        elif status == "error":
            st.error(f"❌ {name}: unavailable.")

    # Current values
    goc_2yr_val  = _current(data.get("goc_2yr"))
    goc_10yr_val = _current(data.get("goc_10yr"))
    goc_30yr_val = _current(data.get("goc_30yr"))
    ust_10yr_val = _current(data.get("yield_10yr"))
    cad_usd_val  = _current(data.get("cad_usd"))

    spread_series = _goc_ust_spread(data)
    spread_val    = _current(spread_series)

    can_cpi_s   = data.get("canada_cpi")
    can_cpi_val = _current(can_cpi_s)

    col_b, col_c = st.columns([1, 2])

    with col_b:
        st.markdown(
            "<div style='font-size:12px;color:#888;margin-bottom:8px;'>"
            "Canadian-specific indicators — GoC yield data via BoC Valet API</div>",
            unsafe_allow_html=True,
        )

        if goc_10yr_val is not None:
            spread_note = (
                f"vs UST 10yr: {spread_val:+.0f} bps" if spread_val is not None else "GoC 10yr benchmark"
            )
            spread_status = "green"
            if spread_val is not None:
                # more positive = Canada underperforming relative to history
                spread_status = "yellow" if spread_val > 20 else "green"
            render_status_badge("GoC 10-Year Yield", f"{goc_10yr_val:.2f}%",
                                spread_status, spread_note)

        if goc_2yr_val is not None:
            render_status_badge("GoC 2-Year Yield", f"{goc_2yr_val:.2f}%",
                                "green", "BoC rate expectations")

        if goc_30yr_val is not None:
            render_status_badge("GoC 30-Year Yield", f"{goc_30yr_val:.2f}%",
                                "green", "Long-end Canadian benchmark")

        if ust_10yr_val is not None:
            render_status_badge("UST 10-Year Yield", f"{ust_10yr_val:.2f}%",
                                "green", "Reference — US benchmark")

        if cad_usd_val is not None:
            usd_cad = 1 / cad_usd_val
            render_status_badge("USD/CAD", f"{usd_cad:.4f}",
                                "green", f"CAD/USD: {cad_usd_val:.4f}")

        if can_cpi_val is not None:
            cpi_s = "red" if can_cpi_val > 5 else "yellow" if can_cpi_val > 3 else "green"
            render_status_badge("Canadian CPI YoY %", f"{can_cpi_val:.1f}%",
                                cpi_s, "StatsCan via FRED (CPALCY01CAM661N)")

    with col_c:
        render_goc_yield_curve(data)
        render_goc_10yr_chart(data, trading_days)
        render_goc_ust_spread_chart(data, trading_days)

    st.caption(
        "GoC yields: Bank of Canada Valet API (BD.CDN.* series, 7-day cache TTL). "
        "Canadian CPI: FRED CPALCY01CAM661N. "
        "GoC/UST spread: negative value = Canada outperforming US Treasuries."
    )
