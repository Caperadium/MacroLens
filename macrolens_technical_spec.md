# MacroLens — Technical Specification
**Version:** 1.0  
**Status:** Ready for build  
**Stack:** Python 3.11+ / Streamlit / SQLite / FRED API / Bank of Canada Valet API

---

## 1. System Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Streamlit Frontend                │
│         (dashboard.py — single page app)            │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                  Data Layer (data.py)                │
│   Fetch → Validate → Calculate → Cache → Serve      │
└──────┬──────────┬──────────┬──────────┬─────────────┘
       │          │          │          │
┌──────▼──┐ ┌────▼────┐ ┌───▼───┐ ┌────▼──────────┐
│  FRED   │ │  BoC    │ │  US   │ │  ISM / Other  │
│   API   │ │ Valet   │ │Treas. │ │   (scrape)    │
└─────────┘ └─────────┘ └───────┘ └───────────────┘
       │
┌──────▼──────────────────────────────────────────────┐
│              SQLite Cache (cache.db)                 │
│         Stores last known good values                │
└─────────────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────┐
│              Alerts Engine (alerts.py)               │
│         Threshold monitoring + SMTP dispatch         │
└─────────────────────────────────────────────────────┘
```

**Design rationale:**
- SQLite cache prevents data loss on API failure and reduces API calls
- Each data source has its own fetcher class for clean separation
- Streamlit's `st.cache_data` used for in-session caching on top of SQLite

---

## 2. Project Structure

```
macrolens/
├── app.py                  # Streamlit entry point
├── data/
│   ├── __init__.py
│   ├── fred.py             # FRED API fetcher
│   ├── boc.py              # Bank of Canada fetcher
│   ├── treasury.py         # Treasury Direct + TIC fetcher
│   ├── calculated.py       # Derived metrics
│   └── cache.py            # SQLite cache manager
├── panels/
│   ├── __init__.py
│   ├── inflation.py        # Panel 1
│   ├── consumer.py         # Panel 2
│   ├── bonds.py            # Panel 3
│   ├── foreign.py          # Panel 4
│   ├── credit.py           # Panel 5
│   └── canada.py           # Canada panel
├── alerts/
│   ├── __init__.py
│   ├── engine.py           # Threshold evaluation
│   └── smtp.py             # Email dispatch
├── config.py               # All constants, thresholds, series IDs
├── requirements.txt
├── .env                    # API keys (gitignored)
└── cache.db                # SQLite (gitignored)
```

---

## 3. Dependencies

### requirements.txt
```
streamlit==1.35.0
pandas==2.2.2
numpy==1.26.4
fredapi==0.5.1
plotly==5.22.0
requests==2.32.3
python-dotenv==1.0.1
sqlalchemy==2.0.30
apscheduler==3.10.4
```

### Environment Variables (.env)
```
FRED_API_KEY=your_fred_api_key_here
ALERT_EMAIL_FROM=your_email@gmail.com
ALERT_EMAIL_TO=recipient@gmail.com
ALERT_EMAIL_PASSWORD=your_app_password_here
ALERT_SMTP_HOST=smtp.gmail.com
ALERT_SMTP_PORT=587
```

**FRED API key:** Free at https://fred.stlouisfed.org/docs/api/api_key.html  
**Gmail app password:** Required if using Gmail SMTP — generate at myaccount.google.com/apppasswords

---

## 4. Complete Data Source Specifications

---

### 4.1 FRED API — Series IDs

**Base URL:** `https://api.stlouisfed.org/fred/series/observations`  
**Library:** `fredapi.Fred(api_key=FRED_API_KEY)`  
**Standard call:**
```python
from fredapi import Fred
fred = Fred(api_key=os.getenv("FRED_API_KEY"))
series = fred.get_series("DGS10", observation_start="2020-01-01")
```

#### Panel 1 — Inflation

| Variable Name | FRED Series ID | Description | Frequency | Transform |
|---|---|---|---|---|
| `cpi` | `CPIAUCSL` | CPI All Urban Consumers | Monthly | YoY % = (current/prior_year - 1) * 100 |
| `ppi` | `PPIACO` | PPI All Commodities | Monthly | YoY % = (current/prior_year - 1) * 100 |
| `ism_mfg_prices` | `NAPMPRIC` | ISM Manufacturing Prices Paid Index | Monthly | Raw index value |
| `ism_svc_prices` | `NMFPRC` | ISM Non-Manufacturing Prices Paid | Monthly | Raw index value |
| `oil_wti` | `DCOILWTICO` | WTI Crude Oil Price (daily) | Daily | YoY % change |
| `breakeven_10yr` | `T10YIE` | 10-Year Breakeven Inflation Rate | Daily | Raw % |

#### Panel 2 — Consumer Stress

| Variable Name | FRED Series ID | Description | Frequency | Transform |
|---|---|---|---|---|
| `avg_hourly_earnings` | `CES0500000003` | Average Hourly Earnings All Private | Monthly | MoM % change |
| `cpi_mom` | `CPIAUCSL` | CPI (reused) | Monthly | MoM % change |
| `real_wage_growth` | Calculated | avg_hourly_earnings_mom - cpi_mom | Monthly | See Section 5.1 |
| `savings_rate` | `PSAVERT` | Personal Savings Rate | Monthly | Raw % |
| `revolving_credit` | `REVOLSL` | Revolving Consumer Credit | Monthly | YoY % change |
| `cc_delinquency` | `DRCCLACBS` | Credit Card Delinquency Rate | Quarterly | Raw % |
| `umich_sentiment` | `UMCSENT` | UMich Consumer Sentiment | Monthly | Raw index |
| `umich_conditions` | `UMCICR` | UMich Index of Current Economic Conditions | Monthly | Raw index |

#### Panel 3 — Bond Market

| Variable Name | FRED Series ID | Description | Frequency | Transform |
|---|---|---|---|---|
| `yield_3m` | `DGS3MO` | 3-Month Treasury Yield | Daily | Raw % |
| `yield_2yr` | `DGS2` | 2-Year Treasury Yield | Daily | Raw % |
| `yield_10yr` | `DGS10` | 10-Year Treasury Yield | Daily | Raw % |
| `yield_30yr` | `DGS30` | 30-Year Treasury Yield | Daily | Raw % |
| `breakeven_10yr` | `T10YIE` | 10-Year Breakeven Rate | Daily | Raw % |
| `term_premium_10yr` | `THREEFYTP10` | ACM 10-Year Term Premium | Daily | Raw % |
| `spread_2s10s` | `T10Y2Y` | 10Y-2Y Spread (pre-calculated) | Daily | Raw bps |

**Note on term premium:** FRED series `THREEFYTP10` is the Adrian-Crump-Moench term premium estimate from NY Fed, updated daily. This is the correct series — do not calculate manually.

**Note on 2s10s:** Use `T10Y2Y` directly from FRED rather than calculating DGS10 - DGS2 to avoid any timing mismatches.

#### Panel 5 — Dollar & Credit

| Variable Name | FRED Series ID | Description | Frequency | Transform |
|---|---|---|---|---|
| `dxy_proxy` | `DTWEXBGS` | Trade Weighted USD Index Broad | Daily | Raw index |
| `usd_cad` | `DEXCAUS` | USD/CAD Exchange Rate | Daily | Raw |
| `usd_jpy` | `DEXJPUS` | USD/JPY Exchange Rate | Daily | Raw |
| `ig_spread` | `BAMLC0A0CM` | ICE BofA US Corporate Bond OAS | Daily | Raw bps |
| `hy_spread` | `BAMLH0A0HYM2` | ICE BofA US High Yield OAS | Daily | Raw bps |
| `sofr` | `SOFR` | Secured Overnight Financing Rate | Daily | Raw % |
| `fed_funds` | `DFF` | Effective Federal Funds Rate | Daily | Raw % |
| `fed_balance_sheet` | `WALCL` | Fed Total Assets (Balance Sheet) | Weekly | Raw $B, WoW change |
| `us_current_account` | `NETFI` | US Current Account Balance | Quarterly | Raw $B |

---

### 4.2 Bank of Canada Valet API

**Base URL:** `https://www.bankofcanada.ca/valet`  
**Auth:** None required  
**Standard call:**
```python
import requests

def get_boc_series(series_name: str, start_date: str) -> pd.Series:
    url = f"https://www.bankofcanada.ca/valet/observations/{series_name}/json"
    params = {"start_date": start_date}
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    observations = data["observations"]
    dates = [obs["d"] for obs in observations]
    values = [float(obs[series_name]["v"]) for obs in observations 
              if obs[series_name]["v"] != ""]
    # Note: filter out empty string values for non-business days
    return pd.Series(values, index=pd.to_datetime(dates))
```

#### Canada Panel Series

| Variable Name | BoC Series ID | Description | Frequency |
|---|---|---|---|
| `goc_2yr` | `BD.CDN.2YR.DQ.YLD` | GoC 2-Year Bond Yield | Daily |
| `goc_5yr` | `BD.CDN.5YR.DQ.YLD` | GoC 5-Year Bond Yield | Daily |
| `goc_10yr` | `BD.CDN.10YR.DQ.YLD` | GoC 10-Year Bond Yield | Daily |
| `goc_30yr` | `BD.CDN.LONG.DQ.YLD` | GoC Long Bond Yield (30yr proxy) | Daily |
| `cad_usd` | `FXCADUSD` | CAD/USD Exchange Rate | Daily |

**Canadian CPI:** Use FRED series `CPALCY01CAM661N` (Canada CPI YoY) — easier than BoC API for this metric.

---

### 4.3 US Treasury Direct API

**Base URL:** `https://www.treasurydirect.gov/TA_WS/securities/search`  
**Auth:** None required  
**Purpose:** Auction results — bid-to-cover, tail, dealer takedown

```python
import requests

def get_recent_auctions(security_type: str = "Bill", 
                        days_back: int = 30) -> pd.DataFrame:
    """
    security_type options: "Bill", "Note", "Bond"
    Returns most recent auctions with bid-to-cover and other metrics
    """
    url = "https://www.treasurydirect.gov/TA_WS/securities/search"
    params = {
        "type": security_type,
        "pagesize": 10,
        "format": "json"
    }
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    return pd.DataFrame(response.json())
```

**Key fields to extract from response:**
- `bidToCoverRatio` — bid-to-cover ratio
- `highYield` — high yield at auction
- `interestRate` — coupon rate
- `auctionDate` — date of auction
- `primaryDealerTendered` and `primaryDealerAccepted` — calculate dealer takedown %

**Auction tail calculation:**
```python
# Tail = high yield at auction minus when-issued yield
# When-issued yield requires a separate market data source
# Simplification for MVP: use bid-to-cover ratio only
# Full implementation: integrate with a market data provider for WI yield
tail_bps = (auction_high_yield - when_issued_yield) * 100
```

**Note:** Full tail calculation requires when-issued yield which is not available from free APIs. For MVP, flag when bid-to-cover falls below threshold and note tail data requires upgrade to paid data source.

---

### 4.4 TIC Data — Foreign Treasury Holdings

**Source:** US Treasury TIC monthly report  
**URL pattern:** `https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/mfhhis.txt`  
**Format:** Fixed-width text file, requires custom parser  
**Frequency:** Monthly, released ~6 weeks after reference month

```python
import requests
import pandas as pd
from io import StringIO

def get_tic_data() -> pd.DataFrame:
    """
    Fetches TIC major foreign holders data.
    Returns DataFrame with country, holdings ($B), and date.
    """
    url = "https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/mfhhis.txt"
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    
    # Parse fixed-width format — first column is country name,
    # subsequent columns are monthly holdings in $B
    # Implementation requires careful column alignment parsing
    # See Treasury documentation for exact column widths
    lines = response.text.split('\n')
    # Skip header rows (typically first 5-7 lines)
    # Extract: Japan, China (Mainland), United Kingdom, 
    #          Cayman Islands, Canada, All Other
    countries_to_track = [
        "Japan", "China, Mainland", "United Kingdom", 
        "Cayman Islands", "Canada"
    ]
    # Return most recent 12 months for each country
    ...
```

**Note:** TIC parsing is the most complex data ingestion task. Recommend building this in Phase 2. For Phase 1 MVP, display a static note that TIC data requires manual monthly update or Phase 2 implementation.

---

### 4.5 ISM Data — Fallback Approach

ISM data is not available via free API. Two options:

**Option A (Recommended for MVP):** Use FRED series `NAPMPRIC` and `NMFPRC` — FRED sources these from ISM with a short lag. No additional fetching needed.

**Option B (Phase 2):** Scrape ISM press releases at `ismworld.org` using `requests` + `BeautifulSoup`. Fragile and against most sites' ToS — not recommended.

---

## 5. Calculation Specifications

All calculations live in `data/calculated.py`.

---

### 5.1 Real Wage Growth

```python
def calculate_real_wage_growth(
    avg_hourly_earnings: pd.Series,  # FRED CES0500000003, monthly level
    cpi: pd.Series                   # FRED CPIAUCSL, monthly level
) -> pd.Series:
    """
    Real wage growth = nominal wage MoM % - CPI MoM %
    Positive = workers gaining purchasing power
    Negative = workers losing purchasing power
    """
    wage_mom = avg_hourly_earnings.pct_change() * 100
    cpi_mom = cpi.pct_change() * 100
    return (wage_mom - cpi_mom).dropna()
```

---

### 5.2 YoY % Change (Generic)

```python
def yoy_pct_change(series: pd.Series) -> pd.Series:
    """
    For monthly series: shift by 12 periods
    For daily series: shift by 252 trading days
    """
    if series.index.freq == 'MS' or series.index.freq == 'M':
        return (series / series.shift(12) - 1) * 100
    else:
        return (series / series.shift(252) - 1) * 100
```

---

### 5.3 Bear Flattener / Bear Steepener Flag

```python
def classify_yield_curve_move(
    spread_current: float,   # 2s10s spread today (bps)
    spread_prior: float,     # 2s10s spread 20 trading days ago
    yield_2yr_current: float,
    yield_2yr_prior: float
) -> str:
    """
    Bear = both yields rising (yield_2yr_current > yield_2yr_prior)
    Bull = both yields falling
    Flattener = spread narrowing (spread_current < spread_prior)
    Steepener = spread widening (spread_current > spread_prior)
    
    Returns one of:
    "Bear Flattener" — yields up, spread narrowing (NEGATIVE signal)
    "Bear Steepener" — yields up, spread widening (CRISIS signal)
    "Bull Flattener" — yields down, spread narrowing (NEUTRAL)
    "Bull Steepener" — yields down, spread widening (POSITIVE)
    "Unchanged" — no significant move
    """
    MOVE_THRESHOLD_BPS = 5  # Minimum move to classify
    
    yields_rising = yield_2yr_current > yield_2yr_prior + (MOVE_THRESHOLD_BPS / 100)
    yields_falling = yield_2yr_current < yield_2yr_prior - (MOVE_THRESHOLD_BPS / 100)
    spread_narrowing = spread_current < spread_prior - MOVE_THRESHOLD_BPS
    spread_widening = spread_current > spread_prior + MOVE_THRESHOLD_BPS
    
    if yields_rising and spread_narrowing:
        return "Bear Flattener"
    elif yields_rising and spread_widening:
        return "Bear Steepener"  
    elif yields_falling and spread_narrowing:
        return "Bull Flattener"
    elif yields_falling and spread_widening:
        return "Bull Steepener"
    else:
        return "Unchanged"
```

---

### 5.4 Dollar / Yield Divergence Flag

```python
def dollar_yield_divergence(
    yield_10yr_series: pd.Series,   # Daily, last 20 trading days
    dxy_series: pd.Series           # Daily, last 20 trading days
) -> dict:
    """
    Normal stress: yields rising + dollar rising
    Crisis signal: yields rising + dollar FALLING simultaneously
    
    Uses 20-day rolling window to assess trend direction.
    Requires both series to be moving in same direction for 
    at least 10 of the last 20 days to trigger flag.
    
    Returns:
        {
            "flag": "normal_stress" | "crisis_signal" | "neutral",
            "yield_trend": "rising" | "falling" | "flat",
            "dollar_trend": "rising" | "falling" | "flat",
            "description": str
        }
    """
    WINDOW = 20
    THRESHOLD_DAYS = 10
    
    yield_changes = yield_10yr_series.diff().tail(WINDOW)
    dollar_changes = dxy_series.diff().tail(WINDOW)
    
    yield_rising_days = (yield_changes > 0).sum()
    dollar_rising_days = (dollar_changes > 0).sum()
    
    yield_trend = (
        "rising" if yield_rising_days >= THRESHOLD_DAYS 
        else "falling" if yield_rising_days <= WINDOW - THRESHOLD_DAYS 
        else "flat"
    )
    dollar_trend = (
        "rising" if dollar_rising_days >= THRESHOLD_DAYS 
        else "falling" if dollar_rising_days <= WINDOW - THRESHOLD_DAYS 
        else "flat"
    )
    
    if yield_trend == "rising" and dollar_trend == "falling":
        flag = "crisis_signal"
        description = "Yields rising while dollar weakening — potential capital flight from US assets"
    elif yield_trend == "rising" and dollar_trend == "rising":
        flag = "normal_stress"
        description = "Yields and dollar both rising — normal risk-off rotation, not crisis"
    else:
        flag = "neutral"
        description = "No significant divergence detected"
    
    return {
        "flag": flag,
        "yield_trend": yield_trend,
        "dollar_trend": dollar_trend,
        "description": description
    }
```

---

### 5.5 Composite Panel Scores (1–10)

Each panel produces a composite score. Score is weighted average of sub-indicators, each scored 1-10 based on threshold bands.

```python
SCORE_THRESHOLDS = {
    "ppi_yoy": {
        # (upper_bound, score) — first match wins, ascending order
        "bands": [(2.0, 2), (3.0, 4), (4.0, 6), (5.0, 8), (float('inf'), 10)],
    },
    "ism_avg_prices": {
        "bands": [(50, 2), (55, 4), (60, 6), (65, 8), (float('inf'), 10)],
    },
    "oil_yoy": {
        "bands": [(0, 2), (10, 4), (20, 6), (35, 8), (float('inf'), 10)],
    },
    "breakeven_10yr": {
        "bands": [(2.2, 2), (2.35, 4), (2.5, 6), (2.75, 8), (float('inf'), 10)],
    },
    "real_wage_growth": {
        # Inverted — negative real wages = higher stress score
        "bands": [(-float('inf'), 10), (-0.2, 8), (0, 6), (0.1, 4), (float('inf'), 2)],
        "inverted": True
    },
    "savings_rate": {
        # Lower savings = higher stress
        "bands": [(-float('inf'), 10), (3.0, 8), (5.0, 6), (7.0, 4), (float('inf'), 2)],
        "inverted": True
    },
    "cc_delinquency": {
        "bands": [(2.5, 2), (3.0, 4), (3.5, 6), (4.0, 8), (float('inf'), 10)],
    },
    "yield_10yr": {
        "bands": [(4.0, 2), (4.5, 4), (5.0, 7), (5.5, 9), (float('inf'), 10)],
    },
    "term_premium": {
        "bands": [(0.5, 2), (1.0, 4), (1.5, 6), (2.0, 8), (float('inf'), 10)],
    },
    "ig_spread_bps": {
        "bands": [(100, 2), (150, 4), (200, 7), (250, 9), (float('inf'), 10)],
    },
    "hy_spread_bps": {
        "bands": [(400, 2), (500, 4), (600, 7), (700, 9), (float('inf'), 10)],
    },
}

PANEL_WEIGHTS = {
    "inflation": {
        "ppi_yoy": 0.30,
        "ism_avg_prices": 0.25,
        "oil_yoy": 0.25,
        "breakeven_10yr": 0.20,
    },
    "consumer": {
        "real_wage_growth": 0.35,
        "savings_rate": 0.25,
        "cc_delinquency": 0.20,
        "umich_sentiment_normalized": 0.20,
    },
    "bonds": {
        "yield_10yr": 0.30,
        "term_premium": 0.30,
        "spread_2s10s_normalized": 0.20,
        "breakeven_10yr": 0.20,
    },
    "credit": {
        "ig_spread_bps": 0.40,
        "hy_spread_bps": 0.40,
        "dollar_yield_flag_score": 0.20,
    }
}

def score_indicator(value: float, series_name: str) -> int:
    config = SCORE_THRESHOLDS[series_name]
    for upper_bound, score in config["bands"]:
        if value <= upper_bound:
            return score
    return 10

def calculate_panel_score(panel_name: str, indicator_values: dict) -> float:
    weights = PANEL_WEIGHTS[panel_name]
    total_score = 0
    for indicator, weight in weights.items():
        if indicator in indicator_values:
            raw_score = score_indicator(indicator_values[indicator], indicator)
            total_score += raw_score * weight
    return round(total_score, 1)
```

---

### 5.6 Crisis Stage Logic

```python
def calculate_crisis_stage(panel_scores: dict) -> dict:
    """
    Panel scores dict: {
        "inflation": float,
        "consumer": float,
        "bonds": float,
        "foreign": float,  # Manual/Phase 2
        "credit": float
    }
    
    Stage advances sequentially — must meet current stage criteria
    AND prior stage criteria must still be elevated.
    
    Thresholds (score out of 10):
    Stage 0: All panels below 4
    Stage 1: Inflation >= 6
    Stage 2: Stage 1 + Consumer >= 5
    Stage 3: Stage 2 + Bonds >= 6
    Stage 4: Stage 3 + Foreign demand deteriorating (manual flag for MVP)
    Stage 5: Stage 4 + Credit >= 7 OR dollar/yield divergence active
    """
    inflation = panel_scores.get("inflation", 0)
    consumer = panel_scores.get("consumer", 0)
    bonds = panel_scores.get("bonds", 0)
    credit = panel_scores.get("credit", 0)
    dollar_divergence = panel_scores.get("dollar_divergence_active", False)
    
    if inflation >= 6 and consumer >= 5 and bonds >= 6 and (credit >= 7 or dollar_divergence):
        stage = 5
        label = "Dollar/Credit Crisis Signals Active"
        color = "#FF0000"
    elif inflation >= 6 and consumer >= 5 and bonds >= 6:
        stage = 3
        label = "Bond Market Showing Strain"
        color = "#FF4444"
    elif inflation >= 6 and consumer >= 5:
        stage = 2
        label = "Consumer Stress Emerging"
        color = "#FF8800"
    elif inflation >= 6:
        stage = 1
        label = "Inflation Pressure Building"
        color = "#FFCC00"
    else:
        stage = 0
        label = "No Significant Stress"
        color = "#00CC44"
    
    return {"stage": stage, "label": label, "color": color}
```

---

## 6. SQLite Cache Schema

```sql
-- cache.db schema

CREATE TABLE IF NOT EXISTS series_cache (
    series_id TEXT NOT NULL,        -- e.g. "DGS10", "goc_10yr"
    source TEXT NOT NULL,           -- "fred", "boc", "treasury", "calculated"
    date TEXT NOT NULL,             -- ISO format YYYY-MM-DD
    value REAL,                     -- numeric value
    updated_at TEXT NOT NULL,       -- ISO datetime of cache write
    PRIMARY KEY (series_id, date)
);

CREATE TABLE IF NOT EXISTS alert_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type TEXT NOT NULL,       -- e.g. "yield_10yr_5pct"
    triggered_at TEXT NOT NULL,     -- ISO datetime
    value_at_trigger REAL,
    email_sent INTEGER DEFAULT 0    -- 0 or 1
);

CREATE TABLE IF NOT EXISTS panel_scores (
    calculated_at TEXT PRIMARY KEY, -- ISO datetime
    inflation_score REAL,
    consumer_score REAL,
    bonds_score REAL,
    credit_score REAL,
    crisis_stage INTEGER
);
```

**Cache manager (data/cache.py):**
```python
def get_cached_series(series_id: str, 
                      max_age_hours: int = 24) -> pd.Series | None:
    """
    Returns cached series if last update within max_age_hours.
    Returns None if cache is stale or empty — triggers fresh fetch.
    """

def write_series_to_cache(series_id: str, 
                          source: str, 
                          data: pd.Series) -> None:
    """Upserts series data into cache."""

def get_last_known_value(series_id: str) -> float | None:
    """
    Fallback — returns most recent value regardless of age.
    Used when API fetch fails to display stale-but-available data.
    """
```

---

## 7. Data Refresh Architecture

### Refresh Cadence by Series Type

| Series Type | Refresh Frequency | Cache TTL |
|---|---|---|
| Daily market data (yields, spreads, FX) | Every 4 hours on weekdays | 4 hours |
| Weekly data (Fed balance sheet) | Once per week (Thursday after 4:30pm ET) | 7 days |
| Monthly data (CPI, PPI, PMI, savings) | Once per day (checks for new release) | 24 hours |
| Quarterly data (current account, delinquency) | Once per day (checks for new release) | 24 hours |
| Auction data | After each auction (check daily) | 24 hours |

### Scheduler Implementation (APScheduler)

```python
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

# Market data — every 4 hours on weekdays
scheduler.add_job(
    func=refresh_daily_series,
    trigger='cron',
    day_of_week='mon-fri',
    hour='8,12,16,20',
    minute=0,
    timezone='America/New_York'
)

# Monthly data check — daily at 8am ET
scheduler.add_job(
    func=check_monthly_releases,
    trigger='cron',
    hour=8,
    minute=0,
    timezone='America/New_York'
)

scheduler.start()
```

### Weekend / Holiday Handling

```python
def is_market_open() -> bool:
    """Returns False on weekends and US federal holidays."""
    from pandas.tseries.holiday import USFederalHolidayCalendar
    today = pd.Timestamp.today().normalize()
    if today.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    cal = USFederalHolidayCalendar()
    holidays = cal.holidays(start=today, end=today)
    return today not in holidays

def get_display_value(series_id: str) -> tuple[float, str, bool]:
    """
    Returns (value, date_of_value, is_stale)
    is_stale = True if value is older than expected refresh window
    Always returns a value — falls back to last known good from cache.
    """
```

---

## 8. Alert System Specification

### Alert Definitions (config.py)

```python
ALERT_THRESHOLDS = {
    "yield_10yr_5pct": {
        "series": "yield_10yr",
        "condition": "above",
        "threshold": 5.0,
        "description": "10-Year Treasury yield has crossed 5%",
        "severity": "critical",
        "cooldown_hours": 72  # Don't re-alert for 72 hours
    },
    "hy_spread_600": {
        "series": "hy_spread_bps",
        "condition": "above",
        "threshold": 600,
        "description": "High yield spreads above 600bps — significant credit stress",
        "severity": "critical",
        "cooldown_hours": 48
    },
    "ig_spread_200": {
        "series": "ig_spread_bps",
        "condition": "above",
        "threshold": 200,
        "description": "Investment grade spreads above 200bps",
        "severity": "warning",
        "cooldown_hours": 48
    },
    "dollar_yield_divergence": {
        "series": "dollar_yield_flag",
        "condition": "equals",
        "threshold": "crisis_signal",
        "description": "Dollar weakening while yields rise — potential capital flight",
        "severity": "critical",
        "cooldown_hours": 72
    },
    "sofr_spike": {
        "series": "sofr_fed_funds_spread",
        "condition": "above",
        "threshold": 0.25,  # SOFR more than 25bps above fed funds
        "description": "Repo market stress — SOFR significantly above Fed Funds",
        "severity": "warning",
        "cooldown_hours": 24
    },
    "fed_balance_sheet_expansion": {
        "series": "fed_balance_sheet_wow_change",
        "condition": "above",
        "threshold": 50,  # $50B+ expansion in a single week
        "description": "Fed balance sheet expanding rapidly — potential emergency QE",
        "severity": "warning",
        "cooldown_hours": 168  # Weekly
    },
    "breakeven_inflation_275": {
        "series": "breakeven_10yr",
        "condition": "above",
        "threshold": 2.75,
        "description": "10-year breakeven inflation above 2.75% — Fed credibility at risk",
        "severity": "warning",
        "cooldown_hours": 48
    },
    "crisis_stage_5": {
        "series": "crisis_stage",
        "condition": "above",
        "threshold": 4,
        "description": "Dashboard has reached Stage 5 — all crisis indicators active",
        "severity": "critical",
        "cooldown_hours": 168
    }
}
```

### Alert Engine (alerts/engine.py)

```python
def check_all_alerts(current_values: dict) -> list[dict]:
    """
    Evaluates all thresholds against current values.
    Checks alert_history to prevent duplicate alerts within cooldown.
    Returns list of alerts to fire.
    """

def should_send_alert(alert_type: str, cooldown_hours: int) -> bool:
    """
    Queries alert_history table.
    Returns False if same alert_type fired within cooldown_hours.
    """
```

### Email Format (alerts/smtp.py)

```python
EMAIL_TEMPLATE = """
MacroLens Alert — {severity}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Alert: {description}
Value: {current_value}
Threshold: {threshold}
Time: {triggered_at} ET

Current Dashboard Status:
  Crisis Stage: {crisis_stage}
  Inflation Score: {inflation_score}/10
  Consumer Score: {consumer_score}/10
  Bond Score: {bonds_score}/10
  Credit Score: {credit_score}/10

View dashboard: {dashboard_url}
"""
```

---

## 9. Frontend Component Specifications

### 9.1 Layout

```python
# app.py structure
st.set_page_config(
    page_title="MacroLens",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Top bar — always visible
render_crisis_stage_banner()     # Full width

# Main grid — 2 columns
col1, col2 = st.columns(2)
with col1:
    render_panel_inflation()
    render_panel_bonds()
    render_panel_canada()
with col2:
    render_panel_consumer()
    render_panel_credit()

# Full width bottom
render_panel_foreign()
```

### 9.2 Chart Specifications

| Panel | Chart Type | Library | Config |
|---|---|---|---|
| Yield curve shape | Line chart, 3 series overlaid | Plotly | x=maturity, y=yield, colors: current=white, 1mo ago=grey, 6mo ago=dark grey |
| 10yr yield over time | Line chart with threshold line | Plotly | Add horizontal line at 5.0% in red |
| 2s10s spread | Area chart | Plotly | Fill below zero in red, above zero in green |
| CPI vs PPI | Dual line chart | Plotly | CPI in white, PPI in orange |
| ISM prices paid | Bar chart | Plotly | Color bars by threshold band |
| Credit spreads | Line chart | Plotly | IG in blue, HY in orange |
| Fed balance sheet | Area chart | Plotly | WoW change as bar overlay |
| GoC vs UST spread | Line chart | Plotly | Spread widening = Canadian outperformance |

**Plotly theme:**
```python
PLOTLY_LAYOUT = {
    "template": "plotly_dark",
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "font": {"color": "#FFFFFF", "family": "Inter, sans-serif"},
    "margin": {"l": 40, "r": 20, "t": 30, "b": 40},
}
```

### 9.3 Status Indicator Component

```python
def render_status_badge(label: str, value: str, status: str, 
                        interpretation: str):
    """
    status: "green" | "yellow" | "red"
    Renders a card with:
    - Coloured left border
    - Metric label
    - Current value (large)
    - One-line interpretation (small, muted)
    - Last updated timestamp
    """
    colors = {"green": "#00CC44", "yellow": "#FFCC00", "red": "#FF4444"}
    st.markdown(f"""
    <div style="border-left: 4px solid {colors[status]}; 
                padding: 8px 12px; margin: 4px 0;
                background: rgba(255,255,255,0.05);">
        <div style="font-size:11px; color:#888;">{label}</div>
        <div style="font-size:22px; font-weight:bold;">{value}</div>
        <div style="font-size:11px; color:#aaa;">{interpretation}</div>
    </div>
    """, unsafe_allow_html=True)
```

### 9.4 Time Range Selector

```python
TIME_RANGES = {
    "3M": 63,    # trading days
    "6M": 126,
    "1Y": 252,
    "2Y": 504,
    "5Y": 1260,
}

selected_range = st.selectbox(
    "Time range", 
    options=list(TIME_RANGES.keys()), 
    index=2,  # Default 1Y
    key="global_time_range"
)
# Apply to all charts globally
```

### 9.5 Stale Data Display

```python
def render_stale_warning(series_name: str, last_updated: str):
    """
    Displayed when data is older than expected refresh window.
    Shows yellow warning banner with last known timestamp.
    Does NOT hide the data — shows stale value with warning.
    """
    st.warning(f"⚠️ {series_name} data last updated {last_updated}. "
               f"API may be unavailable. Showing last known value.")
```

---

## 10. Error Handling Specification

```python
# Every API fetch follows this pattern:

def fetch_with_fallback(series_id: str, fetcher_func: callable) -> pd.Series:
    """
    1. Check cache — return if fresh
    2. Try live fetch
    3. On success: write to cache, return
    4. On failure: log error, return stale cache value with warning flag
    5. If no cache: return empty series with error flag
    """
    try:
        cached = get_cached_series(series_id, max_age_hours=4)
        if cached is not None:
            return cached
            
        fresh_data = fetcher_func(series_id)
        write_series_to_cache(series_id, fresh_data)
        return fresh_data
        
    except requests.exceptions.Timeout:
        log_error(series_id, "timeout")
        return get_last_known_value(series_id), "stale"
        
    except requests.exceptions.HTTPError as e:
        log_error(series_id, f"HTTP {e.response.status_code}")
        return get_last_known_value(series_id), "stale"
        
    except Exception as e:
        log_error(series_id, str(e))
        return None, "error"
```

---

## 11. Build Sequence (Recommended)

### Phase 1 — MVP (build first)
1. Set up project structure and `.env`
2. Implement FRED fetcher for Panel 3 series only (yields, spread, breakeven, term premium)
3. Implement SQLite cache
4. Build Panel 3 UI with yield curve chart and status badges
5. Add dollar/yield divergence flag
6. Add IG/HY credit spread charts (also FRED — easy add)
7. Deploy to Streamlit Cloud

**Deliverable:** Working bond stress monitor with live data

### Phase 2 — Full Dashboard
8. Add Panels 1, 2 (all FRED — straightforward)
9. Add composite panel scores and crisis stage banner
10. Add Bank of Canada Valet API and Canada panel
11. Add alerts engine and SMTP
12. Add time range selector

### Phase 3 — Complete
13. Add Treasury Direct auction data
14. Add TIC foreign holdings parser
15. Add repo market stress indicators
16. Add weekly email digest

---

## 12. Known Limitations & Notes

| Limitation | Impact | Mitigation |
|---|---|---|
| FRED data lags by 1 business day for daily series | Minor | Display "as of [date]" clearly |
| ISM data available via FRED with ~1 day lag | Acceptable | Note source and lag on panel |
| TIC data released 6 weeks after reference month | Significant lag for foreign demand panel | Display reference month clearly, note lag |
| Auction tail requires paid WI yield data | Bid-to-cover only for MVP | Note limitation on panel |
| DTWEXBGS is not DXY exactly | Slight index difference | Label as "Trade Weighted USD Index" not DXY |
| BoC Valet API has no authentication — may change | API availability risk | Cache aggressively, 7-day TTL for BoC data |
| Credit spread data (BAMLC0A0CM) is ICE BofA via FRED | Free but 1-day lag | Acceptable for this use case |
