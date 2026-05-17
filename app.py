"""MacroLens — Streamlit entry point.

Launch with:  streamlit run app.py
"""

import os
from dotenv import load_dotenv

# Load .env before any module that reads os.getenv
load_dotenv()

import streamlit as st

from data.cache import init_db
from panels.bonds import render_panel_bonds
from panels.credit import render_panel_credit
from config import TIME_RANGES

# --- Page config must be the first Streamlit call ---
st.set_page_config(
    page_title="MacroLens — Bond Crisis Monitor",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- Global CSS tweaks ---
st.markdown(
    """
    <style>
    .stApp { background-color: #0d0d0d; }
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    h1 { color: #ffffff; }
    h2, h3 { color: #eeeeee; }
    hr { border-color: #333333; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Initialise SQLite cache (idempotent) ---
init_db()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
col_title, col_range = st.columns([4, 1])

with col_title:
    st.markdown(
        "<h1 style='margin-bottom:0;'>📊 MacroLens</h1>"
        "<p style='color:#888;margin-top:0;'>Bond Crisis Monitor — Phase 1 MVP &nbsp;|&nbsp; "
        "Live data via FRED API</p>",
        unsafe_allow_html=True,
    )

with col_range:
    selected_range = st.selectbox(
        "Time range",
        options=list(TIME_RANGES.keys()),
        index=2,          # default: 1Y
        key="global_time_range",
        label_visibility="visible",
    )

trading_days = TIME_RANGES[selected_range]

st.divider()

# ---------------------------------------------------------------------------
# Panel 3 — Bond Market (Phase 1 core deliverable)
# ---------------------------------------------------------------------------
render_panel_bonds(trading_days=trading_days)

st.divider()

# ---------------------------------------------------------------------------
# Credit Spreads — IG & HY OAS (Phase 1 step 6)
# ---------------------------------------------------------------------------
render_panel_credit(trading_days=trading_days)

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("---")
st.caption(
    "**MacroLens Phase 1 MVP** &nbsp;|&nbsp; "
    "Data: Federal Reserve Bank of St. Louis (FRED) &nbsp;|&nbsp; "
    "Daily series lag ~1 business day &nbsp;|&nbsp; "
    "Panels 1, 2, Canada, Foreign, Alerts → Phase 2"
)
