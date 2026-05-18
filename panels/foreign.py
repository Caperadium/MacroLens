"""Panel 4 — Foreign Demand Monitor.

Primary data source: TIC Major Foreign Holders flat file (monthly, ~6-week lag).
Secondary: USD/JPY and US Current Account from FRED.

⚠️ Custodial bias note: Belgium + Luxembourg combined as 'Euroclear Proxy'
reflects Euroclear custody location, NOT ultimate beneficial ownership.
UI must display this caveat clearly — never label it 'Eurozone holdings'.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from data.treasury import get_tic_data
from data.fred import fetch_with_fallback
from config import FRED_SERIES, PLOTLY_LAYOUT
from panels.bonds import render_status_badge


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data(ttl=7 * 3600)
def load_foreign_data() -> tuple[dict, dict]:
    """Fetch TIC data plus FRED supplementary series.

    Returns (data_dict, status_dict).
    data_dict keys:
      "tic_df"            — long-format TIC DataFrame
      "usd_jpy"           — USD/JPY series
      "us_current_account" — US Current Account ($B, quarterly)
    """
    data, statuses = {}, {}

    tic_df, tic_status = get_tic_data()
    data["tic_df"]    = tic_df
    statuses["tic"]   = tic_status

    for name in ("usd_jpy", "us_current_account"):
        series, status = fetch_with_fallback(
            FRED_SERIES[name],
            source="fred",
            cache_max_age_hours=4,
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
    return float(clean.iloc[-1]) if not clean.empty else None


def _tail(s: pd.Series | None, n: int) -> pd.Series | None:
    if s is None or s.empty:
        return s
    return s.dropna().tail(n)


def _get_tic_series(tic_df: pd.DataFrame, series_id: str) -> pd.Series | None:
    """Extract a named series from the long-format TIC DataFrame."""
    if tic_df is None or tic_df.empty:
        return None
    sub = tic_df[tic_df["series_id"] == series_id].copy()
    if sub.empty:
        return None
    idx = pd.to_datetime([str(p) for p in sub["date"]])
    s = pd.Series(sub["value_usd_billions"].values, index=idx, name=series_id)
    return s.sort_index()


def _tic_mom_change(total_series: pd.Series | None) -> float | None:
    """Most recent month-over-month change in total foreign holdings ($B)."""
    if total_series is None or len(total_series) < 2:
        return None
    clean = total_series.dropna()
    if len(clean) < 2:
        return None
    return float(clean.iloc[-1] - clean.iloc[-2])


def _tic_status(mom_change: float | None) -> str:
    if mom_change is None:
        return "green"
    if mom_change < -50:
        return "red"
    if mom_change < -20:
        return "yellow"
    return "green"


def _holdings_level_status(current: float | None, prior: float | None) -> str:
    if current is None or prior is None:
        return "green"
    change = current - prior
    return _tic_status(change)


# ---------------------------------------------------------------------------
# TIC holdings chart
# ---------------------------------------------------------------------------

def render_tic_chart(tic_df: pd.DataFrame) -> None:
    """Bar chart: total foreign holdings (24 months) + MoM change line overlay.

    Also shows UK/Cayman and Euroclear proxy as stacked reference bars.
    """
    total      = _get_tic_series(tic_df, "total_foreign")
    uk_cayman  = _get_tic_series(tic_df, "uk_cayman")
    euroclear  = _get_tic_series(tic_df, "euroclear_proxy")

    if total is None or total.empty:
        st.warning("TIC holdings data unavailable.")
        return

    total     = total.tail(24)
    mom_change = total.diff()

    fig = go.Figure()

    # Reference stacked bars: Euroclear proxy + UK/Cayman
    if euroclear is not None and not euroclear.empty:
        euroclear_trimmed = euroclear.reindex(total.index, method="nearest")
        fig.add_trace(go.Bar(
            x=total.index, y=euroclear_trimmed.values,
            name="Euroclear Proxy (Bel+Lux) ⚠️",
            marker_color="rgba(100,149,237,0.55)",
            yaxis="y",
        ))
    if uk_cayman is not None and not uk_cayman.empty:
        uk_cayman_trimmed = uk_cayman.reindex(total.index, method="nearest")
        fig.add_trace(go.Bar(
            x=total.index, y=uk_cayman_trimmed.values,
            name="UK + Cayman (Hedge Fund Proxy)",
            marker_color="rgba(255,165,0,0.55)",
            yaxis="y",
        ))

    # Total foreign holdings — main bars
    fig.add_trace(go.Bar(
        x=total.index, y=total.values,
        name="Total Foreign Holdings ($B)",
        marker_color="rgba(180,180,180,0.30)",
        yaxis="y",
    ))

    # MoM change — line on secondary axis
    fig.add_trace(go.Scatter(
        x=mom_change.index, y=mom_change.values,
        name="MoM Change ($B)",
        mode="lines+markers",
        line=dict(color="#FF4444", width=2),
        marker=dict(size=5),
        yaxis="y2",
    ))

    fig.add_hline(y=0, line_color="#444444", line_width=1, yref="y2")

    layout = dict(PLOTLY_LAYOUT)
    layout.update({
        "title":   "Total Foreign Holdings of US Treasuries (24-month)",
        "height":  320,
        "barmode": "overlay",
        "yaxis":   dict(title="Holdings ($B)"),
        "yaxis2":  dict(
            title="MoM Change ($B)",
            titlefont=dict(color="#FF4444"),
            tickfont=dict(color="#FF4444"),
            overlaying="y", side="right",
            zeroline=True, zerolinecolor="#444444",
        ),
        "legend": dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        "annotations": [{
            "text": "⚠️ Euroclear Proxy = custodial location, not ultimate ownership",
            "xref": "paper", "yref": "paper",
            "x": 0, "y": -0.18,
            "showarrow": False,
            "font": {"size": 10, "color": "#888888"},
        }],
    })
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Main panel renderer
# ---------------------------------------------------------------------------

def render_panel_foreign(trading_days: int = 252) -> None:
    st.subheader("Panel 4 — Foreign Demand Monitor")

    with st.spinner("Loading foreign demand data…"):
        data, statuses = load_foreign_data()

    tic_status = statuses.get("tic", "error")
    if tic_status == "stale":
        st.warning(
            "⚠️ TIC data: live fetch failed — showing cached value. "
            "TIC data is released monthly with a ~6-week lag; stale data is normal."
        )
    elif tic_status == "error":
        st.error("❌ TIC data unavailable (no cache).")

    for name in ("usd_jpy", "us_current_account"):
        if statuses.get(name) == "stale":
            st.warning(f"⚠️ {name}: showing cached value.")
        elif statuses.get(name) == "error":
            st.error(f"❌ {name}: unavailable.")

    tic_df = data.get("tic_df", pd.DataFrame())
    total_series = _get_tic_series(tic_df, "total_foreign")

    # Current metrics
    current_total = _current(total_series)
    mom           = _tic_mom_change(total_series)

    # Reference month label
    ref_month = "—"
    if total_series is not None and not total_series.empty:
        ref_month = total_series.dropna().index[-1].strftime("%b %Y")

    # ---- Badges ----
    col_badges, col_chart = st.columns([1, 2])

    with col_badges:
        render_status_badge(
            f"Total Foreign Holdings (as of {ref_month})",
            f"${current_total:,.0f}B" if current_total is not None else "—",
            _tic_status(mom),
            "TIC data — ~6-week lag from reference month",
        )
        if mom is not None:
            render_status_badge(
                "MoM Change",
                f"${mom:+,.0f}B",
                _tic_status(mom),
                "🟢 ≥0 | 🟡 -$20–$0B | 🔴 <-$50B | Alert threshold: -$50B",
            )

        usd_jpy_val = _current(data.get("usd_jpy"))
        if usd_jpy_val is not None:
            render_status_badge(
                "USD/JPY",
                f"{usd_jpy_val:.2f}",
                "yellow" if usd_jpy_val > 155 else "green",
                "Japanese capital flow indicator | High = yen weakness / potential repatriation",
            )

        ca_val = _current(data.get("us_current_account"))
        if ca_val is not None:
            render_status_badge(
                "US Current Account ($B)",
                f"${ca_val:,.0f}B",
                "red" if ca_val < -250 else "yellow" if ca_val < -150 else "green",
                "Quarterly — deeper deficit = greater foreign credit dependence",
            )

        # Euroclear caveat
        st.markdown(
            """
            <div style="border-left:3px solid #555; padding:6px 10px; margin-top:8px;
                        font-size:11px; color:#888; background:rgba(255,255,255,0.03);">
                <b>⚠️ Euroclear Proxy note:</b> Belgium + Luxembourg figures reflect
                Euroclear <i>custodial location</i>, not ultimate beneficial ownership.
                Do not interpret as "Eurozone" holdings.
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_chart:
        render_tic_chart(tic_df)

    st.caption(
        "Sources: TIC Major Foreign Holders — ticdata.treasury.gov/Publish/mfhhis01.txt "
        "(monthly, ~6-week lag). "
        "USD/JPY: FRED DEXJPUS. US Current Account: FRED NETFI. "
        "Euroclear proxy = Belgium + Luxembourg custodial holdings."
    )
