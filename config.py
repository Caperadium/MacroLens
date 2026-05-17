# All constants, thresholds, and series IDs for MacroLens

# FRED Series IDs — Phase 1 MVP (Panel 3 + Credit Spreads)
FRED_SERIES = {
    # Panel 3 — Bond Market
    "yield_3m":          "DGS3MO",
    "yield_2yr":         "DGS2",
    "yield_10yr":        "DGS10",
    "yield_30yr":        "DGS30",
    "breakeven_10yr":    "T10YIE",
    "term_premium_10yr": "THREEFYTP10",
    "spread_2s10s":      "T10Y2Y",
    # Panel 5 — Dollar & Credit (Phase 1 steps 5 & 6)
    "dxy_proxy":         "DTWEXBGS",   # Trade-weighted USD (broad), not DXY
    "usd_cad":           "DEXCAUS",    # USD/CAD exchange rate
    "ig_spread":         "BAMLC0A0CM",
    "hy_spread":         "BAMLH0A0HYM2",
}

# How far back to fetch on initial load
FRED_START_DATE = "2020-01-01"

# Composite score thresholds — each entry maps a value to a 1-10 stress score.
# Bands are (upper_bound, score); first match (value <= upper_bound) wins.
SCORE_THRESHOLDS = {
    "yield_10yr": {
        "bands": [(4.0, 2), (4.5, 4), (5.0, 7), (5.5, 9), (float("inf"), 10)],
    },
    "term_premium": {
        "bands": [(0.5, 2), (1.0, 4), (1.5, 6), (2.0, 8), (float("inf"), 10)],
    },
    # spread in bps — more negative (deeply inverted) = higher stress
    "spread_2s10s_normalized": {
        "bands": [(-50, 9), (-20, 7), (0, 5), (50, 3), (float("inf"), 2)],
    },
    "breakeven_10yr": {
        "bands": [(2.2, 2), (2.35, 4), (2.5, 6), (2.75, 8), (float("inf"), 10)],
    },
    "ig_spread_bps": {
        "bands": [(100, 2), (150, 4), (200, 7), (250, 9), (float("inf"), 10)],
    },
    "hy_spread_bps": {
        "bands": [(400, 2), (500, 4), (600, 7), (700, 9), (float("inf"), 10)],
    },
    # Panels 1 & 2 thresholds (Phase 2)
    "ppi_yoy": {
        "bands": [(2.0, 2), (3.0, 4), (4.0, 6), (5.0, 8), (float("inf"), 10)],
    },
    "ism_avg_prices": {
        "bands": [(50, 2), (55, 4), (60, 6), (65, 8), (float("inf"), 10)],
    },
    "oil_yoy": {
        "bands": [(0, 2), (10, 4), (20, 6), (35, 8), (float("inf"), 10)],
    },
    "real_wage_growth": {
        "bands": [(-float("inf"), 10), (-0.2, 8), (0, 6), (0.1, 4), (float("inf"), 2)],
        "inverted": True,
    },
    "savings_rate": {
        "bands": [(-float("inf"), 10), (3.0, 8), (5.0, 6), (7.0, 4), (float("inf"), 2)],
        "inverted": True,
    },
    "cc_delinquency": {
        "bands": [(2.5, 2), (3.0, 4), (3.5, 6), (4.0, 8), (float("inf"), 10)],
    },
}

PANEL_WEIGHTS = {
    "bonds": {
        "yield_10yr":             0.30,
        "term_premium":           0.30,
        "spread_2s10s_normalized": 0.20,
        "breakeven_10yr":         0.20,
    },
    "inflation": {
        "ppi_yoy":        0.30,
        "ism_avg_prices": 0.25,
        "oil_yoy":        0.25,
        "breakeven_10yr": 0.20,
    },
    "consumer": {
        "real_wage_growth":         0.35,
        "savings_rate":             0.25,
        "cc_delinquency":           0.20,
        "umich_sentiment_normalized": 0.20,
    },
    "credit": {
        "ig_spread_bps":         0.40,
        "hy_spread_bps":         0.40,
        "dollar_yield_flag_score": 0.20,
    },
}

# Alert thresholds (Phase 1: display only; SMTP dispatch in Phase 2)
ALERT_THRESHOLDS = {
    "yield_10yr_5pct": {
        "series":      "yield_10yr",
        "condition":   "above",
        "threshold":   5.0,
        "description": "10-Year Treasury yield above 5%",
        "severity":    "critical",
        "cooldown_hours": 72,
    },
    "hy_spread_600": {
        "series":      "hy_spread_bps",
        "condition":   "above",
        "threshold":   600,
        "description": "High yield spreads above 600bps — significant credit stress",
        "severity":    "critical",
        "cooldown_hours": 48,
    },
    "ig_spread_200": {
        "series":      "ig_spread_bps",
        "condition":   "above",
        "threshold":   200,
        "description": "Investment grade spreads above 200bps",
        "severity":    "warning",
        "cooldown_hours": 48,
    },
    "dollar_yield_divergence": {
        "series":      "dollar_yield_flag",
        "condition":   "equals",
        "threshold":   "crisis_signal",
        "description": "Dollar weakening while yields rise — potential capital flight",
        "severity":    "critical",
        "cooldown_hours": 72,
    },
    "breakeven_inflation_275": {
        "series":      "breakeven_10yr",
        "condition":   "above",
        "threshold":   2.75,
        "description": "10-year breakeven inflation above 2.75% — Fed credibility at risk",
        "severity":    "warning",
        "cooldown_hours": 48,
    },
}

# Plotly dark theme applied to all charts
PLOTLY_LAYOUT = {
    "template":      "plotly_dark",
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor":  "rgba(0,0,0,0)",
    "font":          {"color": "#FFFFFF", "family": "Inter, sans-serif"},
    "margin":        {"l": 40, "r": 20, "t": 30, "b": 40},
}

# Time range selector options (in approximate trading days)
TIME_RANGES = {
    "3M":  63,
    "6M":  126,
    "1Y":  252,
    "2Y":  504,
    "5Y":  1260,
}
