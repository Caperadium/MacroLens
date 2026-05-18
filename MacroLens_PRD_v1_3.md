# MacroLens
## Product Requirements Document
**Version 1.3 | May 2026**

---

## 1. Overview

| Field | Detail |
|---|---|
| Product Name | MacroLens (working title) |
| Version | 1.1 |
| Status | Ready for Build |
| Primary User | Retail investor with high risk tolerance and quant background |
| Stack | Python / Streamlit / SQLite / FRED API / Bank of Canada Valet API |

MacroLens is a single-screen dashboard that aggregates, displays, and interprets the key macroeconomic indicators relevant to the US and Canadian bond crisis thesis. The goal is not just data display but signal interpretation — translating raw data into actionable crisis stage awareness.

**Core Question The Dashboard Answers:** Where are we in the crisis sequence, and what should I be watching right now?

---

## 2. Design Principles

- **Interpretation over raw data** — every metric has a status (green/yellow/red) with a one-line interpretation, not just a number
- **Signal hierarchy** — indicators organised by crisis stage, not by category
- **Minimal noise** — only metrics that materially change the thesis are shown
- **Interconnection awareness** — show when multiple indicators are confirming each other
- **Refresh cadence** — clearly labelled when each data point was last updated and how frequently it updates

---

## 3. Dashboard Structure

The dashboard is organised into five panels corresponding to the crisis sequence, plus a Canada-specific panel and a global overview header.

---

### Panel 1 — Inflation Pressure Gauge

Leading indicators showing where inflation is heading. Leads the crisis sequence by approximately 4 months.

| Metric | Source | Frequency | Why It Matters |
|---|---|---|---|
| CPI YoY % | BLS via FRED | Monthly | Headline consumer inflation |
| PPI YoY % | BLS via FRED | Monthly | Leads CPI by ~2 months |
| Philadelphia Fed Mfg Prices Paid | FRED (PPCDFSA066MSFRBPHI) | Monthly | Free ISM proxy — diffusion index, leads PPI by ~2 months |
| Dallas Fed Prices Paid for Raw Materials | FRED (PRMUAMFRBDAL) | Monthly | Free ISM proxy — diffusion index, energy-sector skew |
| ISM Mfg Prices Paid | Manual input (ismworld.org) | Monthly | Gold standard leading indicator — enter after each release |
| ISM Services Prices Paid | Manual input (ismworld.org) | Monthly | Services inflation signal — enter after each release |
| KC Fed Prices Paid for Raw Materials | Manual input (kansascityfed.org) | Monthly | Supplementary regional proxy |
| Oil Price YoY % Change | WTI via FRED | Daily | Primary PPI driver — goes into everything |
| 10yr Breakeven Inflation Rate | FRED (T10YIE) | Daily | Bond market inflation expectation |

#### Interpretation Logic — Regional Fed Proxies (Diffusion Index Scale)

> Note: Philly Fed and Dallas Fed use a diffusion index scale (% reporting increases minus % reporting decreases), NOT the 0–100 ISM scale. They cannot be directly compared.

| Status | Conditions |
|---|---|
| 🟢 Green | PPI below 3%, regional diffusion indexes below 0, oil YoY negative |
| 🟡 Yellow | PPI 3–5%, regional diffusion indexes 0–40, oil YoY 0–20% |
| 🔴 Red | PPI above 5%, regional diffusion indexes above 40, oil YoY above 20% |

#### Interpretation Logic — ISM Manual Input (0–100 Scale)

ISM data displayed separately with its own scale when entered. Replaces regional proxy weighting in composite score.

| Status | Conditions |
|---|---|
| 🟢 Green | ISM Mfg and Svc both below 55 |
| 🟡 Yellow | Either index 55–65 |
| 🔴 Red | Either index above 65 |

---

### Panel 2 — Consumer Stress Indicator

Tracks how much pressure the inflation transmission to consumers is creating. Confirms whether demand destruction risk is materialising.

| Metric | Source | Frequency | Why It Matters |
|---|---|---|---|
| Real Wage Growth (MoM) | BLS | Monthly | Inflation minus wage growth — purchasing power |
| Personal Savings Rate | BEA | Monthly | Buffer depletion indicator |
| Revolving Credit Growth YoY | Fed | Monthly | Credit card debt acceleration |
| Credit Card Delinquency Rate | Fed | Quarterly | Consumer debt stress signal |
| UMich Consumer Sentiment | UMich | Monthly | Forward-looking confidence |
| UMich Current Conditions Index | UMich | Monthly | Present conditions assessment |

#### Interpretation Logic

| Status | Conditions |
|---|---|
| 🟢 Green | Real wages positive, savings rate above 5%, delinquencies stable |
| 🟡 Yellow | Real wages negative, savings rate 3–5%, delinquencies ticking up |
| 🔴 Red | Real wages deeply negative, savings rate below 3%, delinquencies accelerating |

---

### Panel 3 — Bond Market Stress Monitor

The core crisis panel. Most critical to watch. Divided into three sub-panels.

#### Sub-panel 3a: Yield Levels

| Metric | Source | Frequency | Why It Matters |
|---|---|---|---|
| 3-month T-bill yield | FRED | Daily | Fed policy proxy |
| 2-year Treasury yield | FRED | Daily | Near-term rate expectations |
| 10-year Treasury yield | FRED | Daily | Key benchmark — mortgages and corporate borrowing |
| 30-year Treasury yield | FRED | Daily | Most sensitive to fiscal confidence |
| 10-year Breakeven Rate | FRED | Daily | Inflation expectations |
| 10-year Term Premium (ACM) | NY Fed via FRED | Daily | Risk premium for holding duration |

> **Key threshold alert:** 10-year yield breaking above 5% triggers automatic red alert banner.

#### Sub-panel 3b: Yield Curve Shape

| Metric | Calculation | Why It Matters |
|---|---|---|
| 2s10s Spread | 10yr minus 2yr | Recession predictor |
| 30s2s Spread | 30yr minus 2yr | Long-end fiscal confidence |
| Bear Flattener/Steepener Flag | Direction + spread change | Crisis configuration identifier |

Visual: Real-time yield curve chart showing current curve vs 1 month ago vs 6 months ago.

#### Sub-panel 3c: Auction Health

| Metric | Source | Frequency | Why It Matters |
|---|---|---|---|
| Bid-to-Cover Ratio | Treasury Direct | Per auction | Demand for new debt issuance |
| Auction Tail (bps) | Treasury Direct | Per auction | Price concession required to clear |
| Primary Dealer Takedown % | NY Fed | Per auction | How much dealers had to absorb |

| Status | Conditions |
|---|---|
| 🟢 Green | Bid-to-cover above 2.5, tail below 1bp, dealer takedown below 20% |
| 🟡 Yellow | Bid-to-cover 2.0–2.5, tail 1–3bps |
| 🔴 Red | Bid-to-cover below 2.0, tail above 3bps, dealer takedown above 30% |

---

### Panel 4 — Foreign Demand Monitor

Tracks the shrinking buyer base for US debt. TIC data is the primary signal — released monthly with a ~6 week lag.

| Metric | Source | Frequency | Why It Matters |
|---|---|---|---|
| TIC Data — Total Foreign Holdings | Treasury MFH file¹ | Monthly | Aggregate foreign Treasury demand — primary signal |
| TIC Data — UK/Cayman Holdings | Treasury MFH file¹ | Monthly | Proxy for hedge fund demand |
| TIC Data — Belgium + Luxembourg (Euroclear Proxy)² | Treasury MFH file¹ | Monthly | Best available proxy for European institutional demand |
| USD/JPY Rate | FRED (DEXJPUS) | Daily | Japanese capital flow indicator |
| Eurozone Current Account Balance | ECB | Monthly | European capacity to buy US debt |
| US Current Account Deficit | FRED (NETFI) | Quarterly | Overall foreign credit dependence |

> ¹ **TIC data source:** All TIC rows are parsed from the Treasury's Major Foreign Holders flat file at `ticdata.treasury.gov/Publish/mfhhis01.txt` — a fixed-width text file updated monthly. Use `pd.read_fwf()` for parsing. Total foreign holdings is the primary metric driving the Panel 4 composite score. This is the single exception to the FRED-first data strategy, requiring a lightweight `requests` fetch rather than `fredapi`.

> ² **Euroclear Proxy methodology:** No FRED series or TIC aggregate exists for "Eurozone" holdings. Belgium and Luxembourg are used as a combined proxy because Euroclear (domiciled in Belgium) and fund custodians in Luxembourg collectively custody the majority of European institutional Treasury holdings. **This aggregate reflects custodial location, not ultimate ownership** — the UI must display a caveat to that effect. Do not label this series "Eurozone holdings."

Key visual: Bar chart showing monthly total foreign holdings over the past 24 months, with MoM change line overlay.

---

### Panel 5 — Dollar & Credit Stress

The crisis confirmation panel. The dollar/yield relationship is the single most important real-time crisis indicator.

#### Sub-panel 5a: Dollar Signals

| Metric | Source | Frequency | Why It Matters |
|---|---|---|---|
| Trade Weighted USD Index | FRED (DTWEXBGS) | Daily | Broad dollar strength |
| USD/CAD | FRED | Daily | Relevant to Canadian positioning |
| Dollar/Yield Divergence Flag | Calculated | Daily | THE primary crisis signal |

| Condition | Signal | Interpretation |
|---|---|---|
| 10yr yield rising AND dollar rising | 🟡 Normal Stress | Risk-off rotation within US assets — manageable |
| 10yr yield rising AND dollar falling | 🔴 Crisis Signal | Capital flight from US assets entirely — Liz Truss territory |

#### Sub-panel 5b: Credit Spreads

| Metric | Source | Frequency | Why It Matters |
|---|---|---|---|
| IG Credit Spread (OAS) | FRED (BAMLC0A0CM) | Daily | Investment grade stress |
| HY Credit Spread (OAS) | FRED (BAMLH0A0HYM2) | Daily | High yield / junk bond stress |

| Status | IG Spread | HY Spread |
|---|---|---|
| 🟢 Green | Below 100bps | Below 400bps |
| 🟡 Yellow | 100–200bps | 400–600bps |
| 🔴 Red | Above 200bps | Above 600bps |

#### Sub-panel 5c: Repo Market

| Metric | Source | Frequency | Why It Matters |
|---|---|---|---|
| SOFR Rate | NY Fed via FRED | Daily | Overnight secured rate |
| SOFR vs Fed Funds Spread | Calculated | Daily | Repo market stress indicator |
| Fed Balance Sheet Size | Fed via FRED | Weekly | QE/QT posture |
| Fed Balance Sheet WoW Change | Calculated | Weekly | Active expansion/contraction signal |

---

### Canada Panel

Tracks Canadian-specific indicators given CAD portfolio exposure and Canada's unique vulnerability to a US crisis through trade concentration and housing.

| Metric | Source | Frequency | Why It Matters |
|---|---|---|---|
| 2-year GoC yield | Bank of Canada | Daily | BoC rate expectations |
| 10-year GoC yield | Bank of Canada | Daily | Long-end Canadian benchmark |
| GoC vs UST Spread (10yr) | Calculated | Daily | Relative value — Canadian vs US bonds |
| USD/CAD | FRED | Daily | Currency positioning |
| Oil Price (WCS) | Markets | Daily | Canadian commodity proxy |
| Canadian Housing Price Index | CREA | Monthly | Key domestic vulnerability |
| BoC Balance Sheet | Bank of Canada | Weekly | Canadian QE/QT posture |
| Canadian CPI | StatsCan via FRED | Monthly | Domestic inflation |

Key relative value visual: GoC 10yr vs UST 10yr spread over time. Widening spread means Canadian bonds outperforming US bonds.

---

## 4. Global Overview Panel

A persistent header bar at the top of the dashboard showing the aggregated composite crisis stage.

| Stage | Description | Indicator |
|---|---|---|
| Stage 0 | No significant stress | 🟢 |
| Stage 1 | Inflation pressure building | 🟡 |
| Stage 2 | Consumer stress emerging | 🟡 |
| Stage 3 | Bond market showing strain | 🔴 |
| Stage 4 | Foreign demand deteriorating | 🔴 |
| Stage 5 | Dollar/credit crisis signals active | 🔴 🚨 |

Stage advancement logic: A stage activates when the majority of indicators within that panel are red, and all prior stage indicators remain elevated.

---

## 5. Alerts System

### Threshold Alerts

Push notification or email triggered when:

- 10-year UST yield crosses 5%
- HY credit spreads cross 600bps
- Dollar/yield divergence flag activates
- Treasury auction tail exceeds 3bps
- Fed announces unscheduled asset purchases
- TIC data shows month-over-month decline above $50B

### Weekly Digest

- Which indicators changed status since last week
- Direction of composite scores
- Any new indicator confirmations across panels

---

## 6. Data Sources

| Source | Data | Cost |
|---|---|---|
| FRED (St. Louis Fed) | Most US macro data — yields, spreads, CPI, PPI, Fed balance sheet, Philly Fed and Dallas Fed prices paid, USD/JPY (DEXJPUS), US current account (NETFI) | Free API |
| US Treasury TIC (MFH file) | Country-level foreign holdings of US Treasuries — parsed from `ticdata.treasury.gov/Publish/mfhhis01.txt` via `requests`. Not available as individual FRED series. | Free, monthly |
| Treasury Direct | Auction results — bid-to-cover, tail | Free, per auction |
| NY Fed | Term premium, repo, SOFR | Free |
| BLS | CPI, PPI, average hourly earnings | Free API |
| ICE BofA via FRED | Credit spreads (OAS) | Free via FRED |
| Bank of Canada Valet API | GoC yields, BoC balance sheet | Free API |
| StatsCan via FRED | Canadian CPI, current account | Free API |
| CREA | Canadian housing price index | Free monthly |
| ISM (ismworld.org) | Mfg and Services Prices Paid — manual entry after each release | Free to read, manual input |
| Kansas City Fed (kansascityfed.org) | Prices Paid for Raw Materials — manual entry after each release | Free to read, manual input |

---

## 7. Technical Stack

| Component | Technology | Rationale |
|---|---|---|
| Frontend | Streamlit | Fastest to build, deploys free on Streamlit Cloud, native Python |
| Data fetching | fredapi + requests | Native FRED library, simple REST for BoC and Treasury |
| Caching | SQLite | Prevents data loss on API failure, reduces API calls |
| Charts | Plotly | Interactive, dark theme, strong financial chart support |
| Scheduling | APScheduler | Background refresh without blocking Streamlit UI |
| Alerts | SMTP via Gmail | Free, no additional service required |
| Deployment | Streamlit Cloud | Free tier, Git-based deployment |

---

## 7b. Manual Input System

ISM and Kansas City Fed prices paid data are proprietary and not available via free API. The dashboard handles these through a persistent manual input sidebar that stores entries in SQLite.

### How It Works

- A collapsible sidebar panel labelled "Manual Data Entry" is visible on every page load
- User selects the reference month (defaults to current month) and enters the value after each release
- Values stored in SQLite — persist across sessions, enter once per month per series
- Dashboard shows "ISM pending — showing regional proxies" notice until ISM data is entered for the current month
- Once ISM data is entered, it replaces the regional proxy weighting in the composite Panel 1 score

### Release Schedule

| Series | When to Enter | Where to Find It |
|---|---|---|
| ISM Mfg Prices Paid | First business day of the following month | ismworld.org → Manufacturing Report |
| ISM Services Prices Paid | Third business day of the following month | ismworld.org → Services Report |
| KC Fed Prices Paid | Fourth week of the current month | kansascityfed.org/surveys/manufacturing-survey |

### Scale Reference

| Series | Scale | Neutral Point | Stress Signal |
|---|---|---|---|
| ISM Mfg & Services Prices Paid | 0–100 | 50 = prices unchanged | Above 65 = 🔴 Red |
| Philly Fed Prices Paid (auto) | Diffusion index (~-80 to +80) | 0 = balanced | Above 40 = 🔴 Red |
| Dallas Fed Prices Paid (auto) | Diffusion index (~-80 to +80) | 0 = balanced | Above 40 = 🔴 Red |
| KC Fed Prices Paid (manual) | Diffusion index (~-80 to +80) | 0 = balanced | Supplementary only |

> **Important:** ISM and the regional Fed indexes use different scales. The dashboard never mixes them on the same chart or axis. Each is displayed with its own clearly labelled scale.

---

## 8. Build Sequence

### Phase 1 — MVP (Build First)

1. Set up project structure and environment variables
2. Implement FRED fetcher for Panel 3 series only (yields, spread, breakeven, term premium)
3. Implement SQLite cache
4. Build Panel 3 UI with yield curve chart and status badges
5. Add dollar/yield divergence flag
6. Add IG/HY credit spread charts
7. Deploy to Streamlit Cloud

**Deliverable:** Working bond stress monitor with live data.

### Phase 2 — Full Dashboard

8. Add Panels 1 and 2 (all FRED — straightforward)
9. Add manual input sidebar for ISM and KC Fed
10. Add composite panel scores and crisis stage banner
11. Add Bank of Canada Valet API and Canada panel
12. Add alerts engine and SMTP
13. Add time range selector

### Phase 3 — Complete

14. Add Treasury Direct auction data
15. Add TIC foreign holdings parser
16. Add repo market stress indicators
17. Add weekly email digest

---

*MacroLens PRD v1.3 | May 2026 | Confidential*
