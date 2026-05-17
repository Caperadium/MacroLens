# MacroLens — Bond Crisis Monitor

A Streamlit dashboard for monitoring US bond market stress in real time using live FRED data.

---

## Phase 1 MVP — What's included

**Panel 3 — Bond Market**
- Yield curve shape snapshot (current / 1M ago / 6M ago)
- 10-Year Treasury yield chart with 5% alert threshold
- 2s10s spread area chart (red when inverted)
- ACM 10-Year Term Premium (NY Fed estimate)
- Status badges for all key rates with colour-coded stress levels
- Yield curve regime classification (Bear/Bull Flattener/Steepener)
- Dollar/yield divergence flag — detects potential capital flight

**Credit Spreads**
- IG and High Yield OAS on a dual-axis chart
- Status badges with thresholds (IG: 200 bps, HY: 600 bps)

**Bond Stress Score** — composite 1–10 score weighted across yield level, term premium, curve shape, and breakeven inflation.

---

## Setup

### 1. Get a FRED API key
Free at [fred.stlouisfed.org/docs/api/api_key.html](https://fred.stlouisfed.org/docs/api/api_key.html)

### 2. Create your .env file
```
cp .env.example .env
```
Then open `.env` and paste your key:
```
FRED_API_KEY=your_key_here
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
├── app.py                  # Streamlit entry point
├── config.py               # Series IDs, thresholds, constants
├── data/
│   ├── cache.py            # SQLite cache manager
│   ├── fred.py             # FRED API fetcher with fallback
│   └── calculated.py       # Derived metrics and scoring
├── panels/
│   ├── bonds.py            # Panel 3 — Bond Market UI
│   └── credit.py           # Credit spread charts
├── alerts/                 # Phase 2 — alert engine + SMTP
├── requirements.txt
├── .env.example
└── .gitignore
```

`cache.db` is created automatically on first run and stores last-known-good values so the dashboard stays up if FRED is temporarily unreachable.

---

## Data sources

| Series | FRED ID | Notes |
|---|---|---|
| 3M / 2Y / 10Y / 30Y yields | DGS3MO, DGS2, DGS10, DGS30 | ~1 business day lag |
| 2s10s spread | T10Y2Y | Pre-calculated by FRED |
| 10Y breakeven inflation | T10YIE | TIPS-derived |
| ACM term premium | THREEFYTP10 | NY Fed estimate |
| Trade-weighted USD index | DTWEXBGS | Broad index, not DXY |
| IG credit spread (OAS) | BAMLC0A0CM | ICE BofA via FRED |
| HY credit spread (OAS) | BAMLH0A0HYM2 | ICE BofA via FRED |

---

## Roadmap

| Phase | Contents |
|---|---|
| **Phase 1 (current)** | Panel 3 (bonds) + credit spreads, FRED data, SQLite cache |
| Phase 2 | Panels 1 & 2 (inflation, consumer), Canada panel, composite crisis stage banner, email alerts |
| Phase 3 | Treasury auction data, TIC foreign holdings, repo market stress, weekly digest |
