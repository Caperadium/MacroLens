# MacroLens — Bond Crisis Monitor

A Streamlit dashboard for monitoring US (and Canadian) bond market stress in real time using live FRED, Bank of Canada, Treasury Direct, and TIC data.

---

## Panels

### Panel 1 — Inflation
- CPI and PPI YoY % change chart
- PCE deflator and core PCE
- Oil (WTI) YoY % change
- Regional Fed prices-paid diffusion indices
- Manual entry sidebar for ISM Manufacturing/Services prices paid and KC Fed prices paid (not available via free API)
- Composite inflation stress score (1–10)

### Panel 2 — Consumer Stress
- Retail sales MoM % change
- University of Michigan consumer sentiment
- Credit card delinquency rate (FRED)
- Composite consumer stress score (1–10)

### Panel 3 — Bond Market
- Yield curve shape snapshot (current / 1M ago / 6M ago)
- 10-Year Treasury yield with 5% alert threshold
- 2s10s spread area chart (red when inverted)
- ACM 10-Year Term Premium (NY Fed estimate)
- Dollar/yield divergence flag — detects potential capital flight
- Yield curve regime classification (Bear/Bull Flattener/Steepener)
- **Sub-panel 3c — Auction Health**: last 5 auctions per type (Bills, Notes, Bonds) with bid-to-cover ratio and dealer takedown % badges from Treasury Direct
- Composite bond stress score (1–10)

### Panel 4 — Foreign Demand
- TIC Major Foreign Holdings: total foreign, UK, Cayman Islands, Belgium, Luxembourg (monthly, ~6-week lag)
- Derived series: UK + Cayman proxy; Belgium + Luxembourg Euroclear custodial proxy
- MoM change badges and 24-month bar chart
- USD/JPY rate and US current account balance
- Euroclear custodial-bias caveat prominently displayed

### Panel 5 — Credit Spreads
- IG and High Yield OAS on a dual-axis chart
- Status badges with stress thresholds (IG: 200 bps, HY: 600 bps)
- **Sub-panel 5c — Repo Market**: SOFR vs Fed Funds spread chart with 25 bps alert line; Fed balance sheet level with WoW change overlay
- Composite credit stress score (1–10)

### Canada Panel
- Bank of Canada overnight rate vs 10-year GoC yield
- Canadian yield curve (via BoC Valet API)

---

## Crisis Stage Banner

A top-of-page banner shows the current composite crisis stage (0–5):

| Stage | Label | Trigger |
|---|---|---|
| 0 | No Significant Stress | Default |
| 1 | Inflation Pressure Building | Inflation ≥ 5 |
| 2 | Consumer Stress Emerging | Inflation ≥ 5, Consumer ≥ 4 |
| 3 | Bond Market Showing Strain | Inflation ≥ 6, Consumer ≥ 5, Bonds ≥ 6 |
| 4 | Foreign Demand Deteriorating | Stage 3 + TIC MoM declining |
| 5 | Dollar/Credit Crisis Signals Active | Stage 4 + Credit ≥ 7 or dollar/yield divergence |

---

## Alerts

Alert types (fire on page load, email via SMTP if configured):

| Alert | Threshold | Severity |
|---|---|---|
| 10Y yield spike | > 5.0% | Warning |
| HY spread blowout | > 600 bps | Critical |
| IG spread blowout | > 200 bps | Warning |
| Dollar/yield divergence | Flag active | Warning |
| Breakeven surge | > 3.0% | Warning |
| Crisis stage escalation | Stage ≥ 3 | Critical |
| SOFR spike | Spread > 25 bps | Warning |
| Fed balance sheet expansion | WoW > $50B | Warning |
| TIC foreign decline | MoM < −$50B | Critical |

A weekly digest email is sent every Monday at 8am ET (requires SMTP config) with panel scores, week-over-week changes, and a list of alerts that fired.

---

## Setup

### 1. Get a FRED API key
Free at [fred.stlouisfed.org/docs/api/api_key.html](https://fred.stlouisfed.org/docs/api/api_key.html)

### 2. Create your .env file
```
cp .env.example .env
```
Open `.env` and fill in the required values:
```
FRED_API_KEY=your_key_here

# Optional — alerts will silently skip if not set
ALERT_EMAIL_FROM=you@gmail.com
ALERT_EMAIL_TO=you@gmail.com
ALERT_EMAIL_PASSWORD=your_app_password
ALERT_SMTP_HOST=smtp.gmail.com   # default
ALERT_SMTP_PORT=587              # default
```

### 3. Install dependencies
```
pip install -r requirements.txt
```

### 4. Run
```
streamlit run app.py
```

---

## Project structure

```
macrolens/
├── app.py                  # Streamlit entry point + crisis banner + alert wiring
├── config.py               # FRED series IDs, alert thresholds, time-range constants
├── data/
│   ├── cache.py            # SQLite cache manager (series_cache, alert_history, panel_scores, manual_inputs)
│   ├── fred.py             # FRED API fetcher with stale-cache fallback
│   ├── boc.py              # Bank of Canada Valet API fetcher
│   ├── treasury.py         # Treasury Direct auction fetcher + TIC MFH parser
│   └── calculated.py       # Derived metrics: crisis stage, SOFR spread, Fed balance sheet WoW, etc.
├── panels/
│   ├── inflation.py        # Panel 1 — Inflation
│   ├── consumer.py         # Panel 2 — Consumer Stress
│   ├── bonds.py            # Panel 3 — Bond Market (incl. auction sub-panel)
│   ├── foreign.py          # Panel 4 — Foreign Demand (TIC)
│   ├── credit.py           # Panel 5 — Credit Spreads + Repo Market
│   └── canada.py           # Canada Panel
├── alerts/
│   ├── engine.py           # Alert evaluation against thresholds
│   └── smtp.py             # Alert emails + weekly digest
├── requirements.txt
├── .env.example
└── .gitignore
```

`cache.db` is created automatically on first run and stores last-known-good values so the dashboard stays up if any upstream data source is temporarily unreachable.

---

## Data sources

| Series | Source | Notes |
|---|---|---|
| Treasury yields (3M / 2Y / 10Y / 30Y) | FRED | ~1 business day lag |
| 2s10s spread | FRED T10Y2Y | Pre-calculated |
| 10Y breakeven inflation | FRED T10YIE | TIPS-derived |
| ACM term premium | FRED THREEFYTP10 | NY Fed estimate |
| Trade-weighted USD | FRED DTWEXBGS | Broad index |
| IG / HY credit spread | FRED BAMLC0A0CM / BAMLH0A0HYM2 | ICE BofA |
| CPI / PPI / PCE | FRED | Monthly |
| Retail sales | FRED | Monthly |
| Consumer sentiment | FRED UMCSENT | U of Michigan |
| SOFR | FRED SOFR | Daily |
| Fed Funds rate | FRED DFF | Daily |
| Fed balance sheet | FRED WALCL | Weekly |
| USD/JPY | FRED DEXJPUS | Daily |
| US current account | FRED NETFI | Quarterly |
| Treasury auction results | Treasury Direct API | Bid-to-cover, dealer takedown |
| TIC foreign holdings | Treasury Dept MFH file | Monthly, ~6-week lag |
| Bank of Canada rates | BoC Valet API | Daily |
| ISM prices paid, KC Fed | Manual sidebar entry | Not available via free API |
