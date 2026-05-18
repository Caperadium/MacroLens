# All constants, thresholds, and series IDs for MacroLens

# ---------------------------------------------------------------------------
# FRED Series IDs
# ---------------------------------------------------------------------------
FRED_SERIES = {
    # Panel 1 — Inflation
    # ISM Mfg (NAPMPRIC) and ISM Svc (NMFPRC) removed — invalid FRED series IDs.
    # ISM data is entered manually via the sidebar (see MANUAL_RELEASE_SCHEDULE).
    # Regional proxies (free, on FRED):
    "cpi":                       "CPIAUCSL",
    "ppi":                       "PPIACO",
    "philly_fed_prices_paid":    "PPCDFSA066MSFRBPHI",  # diffusion index
    "dallas_fed_prices_paid":    "PRMUAMFRBDAL",         # diffusion index
    "oil_wti":                   "DCOILWTICO",
    # Panel 2 — Consumer
    "avg_hourly_earnings": "CES0500000003",
    "savings_rate":        "PSAVERT",
    "revolving_credit":    "REVOLSL",
    "cc_delinquency":      "DRCCLACBS",
    "umich_sentiment":     "UMCSENT",
    # Panel 3 — Bond Market
    "yield_3m":            "DGS3MO",
    "yield_2yr":           "DGS2",
    "yield_10yr":          "DGS10",
    "yield_30yr":          "DGS30",
    "breakeven_10yr":      "T10YIE",
    "term_premium_10yr":   "THREEFYTP10",
    "spread_2s10s":        "T10Y2Y",
    # Panel 5 — Dollar & Credit
    "dxy_proxy":           "DTWEXBGS",    # Trade-weighted USD (broad), not DXY
    "usd_cad":             "DEXCAUS",
    "usd_jpy":             "DEXJPUS",
    "ig_spread":           "BAMLC0A0CM",
    "hy_spread":           "BAMLH0A0HYM2",
    # Sub-panel 5c — Repo market
    "sofr":                "SOFR",
    "fed_funds":           "DFF",
    "fed_balance_sheet":   "WALCL",
    # Panel 4 — Foreign demand
    "us_current_account":  "NETFI",
    # Canada — via FRED
    "canada_cpi":          "CPALCY01CAM661N",
}

FRED_START_DATE = "2020-01-01"

# ---------------------------------------------------------------------------
# Bank of Canada Valet API series
# ---------------------------------------------------------------------------
BOC_SERIES = {
    "goc_2yr":  "BD.CDN.2YR.DQ.YLD",
    "goc_5yr":  "BD.CDN.5YR.DQ.YLD",
    "goc_10yr": "BD.CDN.10YR.DQ.YLD",
    "goc_30yr": "BD.CDN.LONG.DQ.YLD",
    "cad_usd":  "FXCADUSD",
}

BOC_START_DATE = "2020-01-01"

# ---------------------------------------------------------------------------
# Composite score thresholds
# Bands are (upper_bound, score); first match (value <= upper_bound) wins.
# ---------------------------------------------------------------------------
SCORE_THRESHOLDS = {
    # Panel 3
    "yield_10yr": {
        "bands": [(4.0, 2), (4.5, 4), (5.0, 7), (5.5, 9), (float("inf"), 10)],
    },
    "term_premium": {
        "bands": [(0.5, 2), (1.0, 4), (1.5, 6), (2.0, 8), (float("inf"), 10)],
    },
    "spread_2s10s_normalized": {
        # more negative (deeply inverted) = higher stress
        "bands": [(-50, 9), (-20, 7), (0, 5), (50, 3), (float("inf"), 2)],
    },
    "breakeven_10yr": {
        "bands": [(2.2, 2), (2.35, 4), (2.5, 6), (2.75, 8), (float("inf"), 10)],
    },
    # Panel 5
    "ig_spread_bps": {
        "bands": [(100, 2), (150, 4), (200, 7), (250, 9), (float("inf"), 10)],
    },
    "hy_spread_bps": {
        "bands": [(400, 2), (500, 4), (600, 7), (700, 9), (float("inf"), 10)],
    },
    "dollar_yield_flag_score": {
        # 1=neutral, 5=normal_stress, 10=crisis_signal → stress score
        "bands": [(1, 2), (5, 5), (float("inf"), 10)],
    },
    # Panel 1 — Inflation
    "ppi_yoy": {
        "bands": [(2.0, 2), (3.0, 4), (4.0, 6), (5.0, 8), (float("inf"), 10)],
    },
    # Regional Fed diffusion indexes (% rising minus % falling; NOT 0-100 scale)
    # above 0 = prices rising; above 20 = yellow pressure; above 40 = red pressure
    "philly_fed_prices_paid": {
        "bands": [(-float("inf"), 1), (0, 3), (20, 5), (40, 8), (float("inf"), 10)],
    },
    "dallas_fed_prices_paid": {
        "bands": [(-float("inf"), 1), (0, 3), (20, 5), (40, 8), (float("inf"), 10)],
    },
    # ISM 0-100 scale (50 = neutral) — used only when manually entered this month
    "ism_avg_prices": {
        "bands": [(50, 2), (55, 4), (60, 6), (65, 8), (float("inf"), 10)],
    },
    "oil_yoy": {
        "bands": [(0, 2), (10, 4), (20, 6), (35, 8), (float("inf"), 10)],
    },
    # Panel 2 — Consumer
    "real_wage_growth": {
        # negative real wages = higher stress; first match on ascending bounds
        "bands": [(-float("inf"), 10), (-0.2, 8), (0, 6), (0.1, 4), (float("inf"), 2)],
        "inverted": True,
    },
    "savings_rate": {
        # lower savings = higher stress
        "bands": [(-float("inf"), 10), (3.0, 8), (5.0, 6), (7.0, 4), (float("inf"), 2)],
        "inverted": True,
    },
    "cc_delinquency": {
        "bands": [(2.5, 2), (3.0, 4), (3.5, 6), (4.0, 8), (float("inf"), 10)],
    },
    "umich_sentiment_normalized": {
        # lower consumer sentiment = higher stress
        "bands": [(50, 10), (60, 8), (70, 6), (80, 4), (float("inf"), 2)],
    },
}

# ---------------------------------------------------------------------------
# Panel composite score weights
# ---------------------------------------------------------------------------
PANEL_WEIGHTS = {
    # Regional proxies (default — when ISM not entered for current month).
    # Philly Fed + Dallas Fed together carry the weight that ISM would otherwise have.
    "inflation_regional": {
        "ppi_yoy":                0.30,
        "philly_fed_prices_paid": 0.15,
        "dallas_fed_prices_paid": 0.15,
        "oil_yoy":                0.25,
        "breakeven_10yr":         0.15,
    },
    # ISM mode — substitutes when ISM data is manually entered for the current month.
    # ism_avg_prices replaces both regional feds entirely; reweighted per spec.
    "inflation_ism": {
        "ppi_yoy":        0.30,
        "ism_avg_prices": 0.25,
        "oil_yoy":        0.25,
        "breakeven_10yr": 0.20,
    },
    "consumer": {
        "real_wage_growth":           0.35,
        "savings_rate":               0.25,
        "cc_delinquency":             0.20,
        "umich_sentiment_normalized": 0.20,
    },
    "bonds": {
        "yield_10yr":              0.30,
        "term_premium":            0.30,
        "spread_2s10s_normalized": 0.20,
        "breakeven_10yr":          0.20,
    },
    "credit": {
        "ig_spread_bps":          0.40,
        "hy_spread_bps":          0.40,
        "dollar_yield_flag_score": 0.20,
    },
}

# ---------------------------------------------------------------------------
# Alert thresholds
# ---------------------------------------------------------------------------
ALERT_THRESHOLDS = {
    "yield_10yr_5pct": {
        "series":         "yield_10yr",
        "condition":      "above",
        "threshold":      5.0,
        "description":    "10-Year Treasury yield has crossed 5%",
        "severity":       "critical",
        "cooldown_hours": 72,
    },
    "hy_spread_600": {
        "series":         "hy_spread_bps",
        "condition":      "above",
        "threshold":      600,
        "description":    "High yield spreads above 600bps — significant credit stress",
        "severity":       "critical",
        "cooldown_hours": 48,
    },
    "ig_spread_200": {
        "series":         "ig_spread_bps",
        "condition":      "above",
        "threshold":      200,
        "description":    "Investment grade spreads above 200bps",
        "severity":       "warning",
        "cooldown_hours": 48,
    },
    "dollar_yield_divergence": {
        "series":         "dollar_yield_flag",
        "condition":      "equals",
        "threshold":      "crisis_signal",
        "description":    "Dollar weakening while yields rise — potential capital flight",
        "severity":       "critical",
        "cooldown_hours": 72,
    },
    "breakeven_inflation_275": {
        "series":         "breakeven_10yr",
        "condition":      "above",
        "threshold":      2.75,
        "description":    "10-year breakeven inflation above 2.75% — Fed credibility at risk",
        "severity":       "warning",
        "cooldown_hours": 48,
    },
    "crisis_stage_5": {
        "series":         "crisis_stage",
        "condition":      "above",
        "threshold":      4,
        "description":    "Dashboard has reached Stage 5 — all crisis indicators active",
        "severity":       "critical",
        "cooldown_hours": 168,
    },
    "sofr_spike": {
        "series":         "sofr_fed_funds_spread",
        "condition":      "above",
        "threshold":      0.25,
        "description":    "Repo market stress — SOFR more than 25bps above Fed Funds",
        "severity":       "warning",
        "cooldown_hours": 24,
    },
    "fed_balance_sheet_expansion": {
        "series":         "fed_balance_sheet_wow_change",
        "condition":      "above",
        "threshold":      50,
        "description":    "Fed balance sheet expanding >$50B in a week — potential emergency QE",
        "severity":       "warning",
        "cooldown_hours": 168,
    },
    "tic_foreign_decline": {
        "series":         "tic_mom_change",
        "condition":      "below",
        "threshold":      -50,
        "description":    "TIC data: total foreign Treasury holdings declined >$50B month-over-month",
        "severity":       "critical",
        "cooldown_hours": 168,
    },
}

# ---------------------------------------------------------------------------
# Plotly dark theme
# ---------------------------------------------------------------------------
PLOTLY_LAYOUT = {
    "template":      "plotly_dark",
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor":  "rgba(0,0,0,0)",
    "font":          {"color": "#FFFFFF", "family": "Inter, sans-serif"},
    "margin":        {"l": 40, "r": 20, "t": 30, "b": 40},
}

# ---------------------------------------------------------------------------
# Time range selector (approximate trading days)
# ---------------------------------------------------------------------------
TIME_RANGES = {
    "3M":  63,
    "6M":  126,
    "1Y":  252,
    "2Y":  504,
    "5Y":  1260,
}

# ---------------------------------------------------------------------------
# Manual input release schedule (displayed in sidebar)
# ---------------------------------------------------------------------------
MANUAL_RELEASE_SCHEDULE = {
    "ism_mfg_prices":    "First business day of the following month — ismworld.org",
    "ism_svc_prices":    "Third business day of the following month — ismworld.org",
    "kc_fed_prices_paid": "Fourth week of the current month — kansascityfed.org",
}
