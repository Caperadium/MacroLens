"""MacroLens — Streamlit entry point (Phase 3).

Launch with:  streamlit run app.py
"""

import os
from dotenv import load_dotenv

load_dotenv()

import streamlit as st

from data.cache import init_db
from data.calculated import calculate_crisis_stage
from panels.inflation import (
    load_inflation_data,
    compute_inflation_score,
    render_panel_inflation,
    render_manual_input_sidebar,
)
from data.cache import get_current_month_manual
from panels.consumer  import load_consumer_data,  compute_consumer_score,  render_panel_consumer
from panels.bonds     import load_bond_data,       compute_bond_score,      render_panel_bonds
from panels.credit    import load_credit_data,     compute_credit_score,    render_panel_credit
from panels.foreign   import render_panel_foreign
from panels.canada    import render_panel_canada
from alerts.engine    import check_all_alerts, record_alert_fired
from alerts.smtp      import send_alert_email, send_weekly_digest
from data.cache       import write_panel_scores
from data.treasury    import get_total_foreign_holdings
from config           import TIME_RANGES

# ── Page config (must be first Streamlit call) ─────────────────────────────
st.set_page_config(
    page_title="MacroLens — Bond Crisis Monitor",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
.stApp { background-color: #0d0d0d; }
.block-container { padding-top: 0.5rem; padding-bottom: 2rem; }
h1, h2, h3 { color: #ffffff; }
hr { border-color: #2a2a2a; }
</style>
""", unsafe_allow_html=True)

init_db()

# ── Manual input sidebar (ISM + KC Fed — not available via free API) ────────
render_manual_input_sidebar()

# ── Time range selector ─────────────────────────────────────────────────────
col_title, col_range = st.columns([5, 1])
with col_title:
    st.markdown(
        "<h1 style='margin-bottom:0;'>📊 MacroLens</h1>"
        "<p style='color:#666;margin-top:0;font-size:13px;'>"
        "Bond Crisis Monitor &nbsp;|&nbsp; Phase 2 &nbsp;|&nbsp; Live FRED + BoC data</p>",
        unsafe_allow_html=True,
    )
with col_range:
    selected_range = st.selectbox(
        "Time range",
        options=list(TIME_RANGES.keys()),
        index=2,
        key="global_time_range",
    )

trading_days = TIME_RANGES[selected_range]

# ── Pre-compute all panel scores for the crisis stage banner ────────────────
# Each loader is @st.cache_data — panels that render later reuse the cache.
infl_data, _ = load_inflation_data()
cons_data, _ = load_consumer_data()
bond_data, _ = load_bond_data()
cred_data, _ = load_credit_data()

# Manual data is read fresh (not cached) so sidebar saves take effect immediately.
manual_data = get_current_month_manual()

infl_score                    = compute_inflation_score(infl_data, manual_data)
cons_score                    = compute_consumer_score(cons_data)
bond_score                    = compute_bond_score(bond_data)
cred_score, div_flag, repo_vals = compute_credit_score(cred_data)

# TIC foreign demand flag (Phase 3)
tic_series, _ = get_total_foreign_holdings()
tic_mom_change = None
foreign_declining = False
if tic_series is not None and len(tic_series.dropna()) >= 2:
    clean = tic_series.dropna()
    tic_mom_change = float(clean.iloc[-1] - clean.iloc[-2])
    foreign_declining = tic_mom_change < 0

panel_scores = {
    "inflation":               infl_score,
    "consumer":                cons_score,
    "bonds":                   bond_score,
    "credit":                  cred_score,
    "dollar_divergence_active": div_flag == "crisis_signal",
    "foreign_declining":       foreign_declining,
}
crisis = calculate_crisis_stage(panel_scores)
panel_scores["crisis_stage"] = crisis["stage"]

# Persist panel scores for weekly digest comparison
write_panel_scores(panel_scores)


def _score_color(s: float) -> str:
    if s >= 7:
        return "#FF4444"
    if s >= 5:
        return "#FFCC00"
    return "#00CC44"


# ── Crisis Stage Banner ─────────────────────────────────────────────────────
color = crisis["color"]
stage = crisis["stage"]
label = crisis["label"]

stage_icons = {0: "🟢", 1: "🟡", 2: "🟡", 3: "🔴", 4: "🔴", 5: "🔴🚨"}
icon = stage_icons.get(stage, "⚪")

st.markdown(
    f"""
    <div style="background:linear-gradient(90deg, {color}18, transparent);
                border-left:6px solid {color}; padding:14px 20px; margin:8px 0 16px 0;
                border-radius:0 8px 8px 0;">
        <div style="font-size:11px;color:#888;text-transform:uppercase;
                    letter-spacing:0.8px;margin-bottom:4px;">CRISIS STAGE</div>
        <div style="font-size:22px;font-weight:bold;color:{color};">
            {icon}&nbsp; Stage {stage} — {label}
        </div>
        <div style="display:flex;gap:28px;margin-top:10px;flex-wrap:wrap;">
            <span style="font-size:12px;color:#aaa;">
                <b style="color:#ddd;">Inflation</b>&nbsp;
                <span style="color:{_score_color(infl_score)};font-weight:bold;">{infl_score}</span>/10
            </span>
            <span style="font-size:12px;color:#aaa;">
                <b style="color:#ddd;">Consumer</b>&nbsp;
                <span style="color:{_score_color(cons_score)};font-weight:bold;">{cons_score}</span>/10
            </span>
            <span style="font-size:12px;color:#aaa;">
                <b style="color:#ddd;">Bonds</b>&nbsp;
                <span style="color:{_score_color(bond_score)};font-weight:bold;">{bond_score}</span>/10
            </span>
            <span style="font-size:12px;color:#aaa;">
                <b style="color:#ddd;">Credit</b>&nbsp;
                <span style="color:{_score_color(cred_score)};font-weight:bold;">{cred_score}</span>/10
            </span>
            <span style="font-size:12px;color:#aaa;">
                <b style="color:#ddd;">Foreign</b>&nbsp;
                <span style="color:{'#FF4444' if foreign_declining else '#00CC44'};font-weight:bold;">
                    {'Declining ▼' if foreign_declining else 'Stable ✓'}
                </span>
            </span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Alert evaluation ────────────────────────────────────────────────────────
ig_bps = None
hy_bps = None
ig_raw = cred_data.get("ig_spread")
hy_raw = cred_data.get("hy_spread")
if ig_raw is not None and not ig_raw.empty:
    ig_bps = float(ig_raw.dropna().iloc[-1]) * 100
if hy_raw is not None and not hy_raw.empty:
    hy_bps = float(hy_raw.dropna().iloc[-1]) * 100

be_raw = bond_data.get("breakeven_10yr")
be_val = float(be_raw.dropna().iloc[-1]) if be_raw is not None and not be_raw.empty else None
y10_raw = bond_data.get("yield_10yr")
y10_val = float(y10_raw.dropna().iloc[-1]) if y10_raw is not None and not y10_raw.empty else None

alert_inputs = {
    "yield_10yr":                  y10_val,
    "hy_spread_bps":               hy_bps,
    "ig_spread_bps":               ig_bps,
    "dollar_yield_flag":           div_flag,
    "breakeven_10yr":              be_val,
    "crisis_stage":                crisis["stage"],
    # Repo market (Phase 3)
    "sofr_fed_funds_spread":       repo_vals.get("sofr_fed_funds_spread"),
    "fed_balance_sheet_wow_change": repo_vals.get("fed_balance_sheet_wow_change"),
    # TIC foreign demand (Phase 3)
    "tic_mom_change":              tic_mom_change,
}

fired_alerts = check_all_alerts(alert_inputs)
for alert in fired_alerts:
    email_sent = send_alert_email(alert, panel_scores)
    record_alert_fired(alert["alert_type"], alert["current_value"], email_sent)
    if alert["severity"] == "critical":
        st.error(f"🚨 **ALERT** — {alert['description']} "
                 f"(current: {alert['current_value']}, threshold: {alert['threshold']})")
    else:
        st.warning(f"⚠️ **Alert** — {alert['description']} "
                   f"(current: {alert['current_value']}, threshold: {alert['threshold']})")

st.divider()

# ── Main 2-column grid (per spec layout) ───────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    render_panel_inflation(trading_days, manual_data)
    st.divider()
    render_panel_bonds(trading_days)
    st.divider()
    render_panel_canada(trading_days)

with col2:
    render_panel_consumer(trading_days)
    st.divider()
    render_panel_credit(trading_days)

# ── Panel 4 — Foreign Demand ────────────────────────────────────────────────
st.divider()
render_panel_foreign(trading_days)

# ── Weekly digest scheduler (APScheduler — started once per process) ────────
if "digest_scheduler_started" not in st.session_state:
    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        def _send_digest():
            send_weekly_digest(panel_scores, crisis)

        _digest_scheduler = BackgroundScheduler()
        _digest_scheduler.add_job(
            func=_send_digest,
            trigger="cron",
            day_of_week="mon",
            hour=8,
            minute=0,
            timezone="America/New_York",
        )
        _digest_scheduler.start()
        st.session_state["digest_scheduler_started"] = True
    except Exception:
        pass  # APScheduler unavailable or already running

# ── Footer ──────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "**MacroLens Phase 3** &nbsp;|&nbsp; "
    "Data: FRED + Bank of Canada Valet API + Treasury Direct + TIC MFH file &nbsp;|&nbsp; "
    "Daily series ~1 business day lag &nbsp;|&nbsp; "
    "TIC data released monthly with ~6-week lag &nbsp;|&nbsp; "
    "Alerts fire on page load; weekly digest emails Mondays at 8am ET (SMTP required)"
)
