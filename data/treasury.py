"""Treasury Direct auction fetcher and TIC foreign holdings parser.

Two separate concerns:
  - fetch_auctions_with_fallback()  Treasury Direct API (per auction)
  - get_tic_data()                  TIC MFH flat-file parser (monthly)
"""

import logging

import pandas as pd
import requests

from data.cache import (
    get_cached_series,
    get_last_known_series,
    write_series_to_cache,
)

logger = logging.getLogger(__name__)

TREASURY_DIRECT_URL = "https://www.treasurydirect.gov/TA_WS/securities/search"
TIC_MFH_URL = "https://ticdata.treasury.gov/Publish/mfhhis01.txt"

AUCTION_CACHE_HOURS = 24
TIC_CACHE_HOURS = 7 * 24

# ---------------------------------------------------------------------------
# Treasury Direct — auction results
# ---------------------------------------------------------------------------

_AUCTION_FIELDS = [
    "auctionDate", "bidToCoverRatio", "highYield", "interestRate",
    "primaryDealerTendered", "primaryDealerAccepted", "offeringAmount",
    "securityTerm",
]


def _fetch_auctions_live(security_type: str, pagesize: int = 10) -> pd.DataFrame:
    """Live fetch from Treasury Direct API.  Raises on failure."""
    resp = requests.get(
        TREASURY_DIRECT_URL,
        params={"type": security_type, "pagesize": pagesize, "format": "json"},
        timeout=10,
    )
    resp.raise_for_status()
    raw = resp.json()
    if not raw:
        return pd.DataFrame()
    df = pd.DataFrame(raw)

    for col in _AUCTION_FIELDS:
        if col not in df.columns:
            df[col] = None

    # Dealer takedown % = primaryDealerAccepted / offeringAmount
    df["dealerTakedownPct"] = None
    try:
        accepted = pd.to_numeric(df["primaryDealerAccepted"], errors="coerce")
        offering = pd.to_numeric(df["offeringAmount"], errors="coerce")
        mask = offering > 0
        df.loc[mask, "dealerTakedownPct"] = (accepted[mask] / offering[mask]) * 100
    except Exception:
        pass

    return df


def fetch_auctions_with_fallback(
    security_type: str,
) -> tuple[pd.DataFrame, str]:
    """Return (DataFrame, status) for recent auctions of security_type.

    Follows the fetch_with_fallback() pattern: cache-first, live fetch on miss,
    stale BTC series as fallback on failure.
    Status is "live", "stale", or "error".
    """
    cache_key = f"auction_btc_{security_type.lower()}"

    try:
        df = _fetch_auctions_live(security_type)
        if not df.empty:
            btc = pd.to_numeric(df["bidToCoverRatio"], errors="coerce")
            dates = pd.to_datetime(df["auctionDate"], errors="coerce")
            valid = btc.notna() & dates.notna()
            if valid.any():
                s = pd.Series(btc[valid].values, index=dates[valid])
                write_series_to_cache(cache_key, "treasury", s)
        return df, "live"

    except requests.exceptions.Timeout:
        logger.warning("Treasury Direct timeout for %s auctions", security_type)
    except requests.exceptions.HTTPError as exc:
        logger.warning(
            "Treasury Direct HTTP %s for %s auctions",
            exc.response.status_code, security_type,
        )
    except Exception as exc:
        logger.warning("Treasury Direct fetch failed (%s): %s", security_type, exc)

    stale = get_last_known_series(cache_key)
    if stale is not None and not stale.empty:
        fallback_df = pd.DataFrame({
            "auctionDate":    stale.index.strftime("%Y-%m-%d"),
            "bidToCoverRatio": stale.values,
        })
        return fallback_df, "stale"

    return pd.DataFrame(), "error"


# ---------------------------------------------------------------------------
# TIC MFH flat-file parser
# ---------------------------------------------------------------------------

_TIC_ROWS = {
    "Grand Total":    "total_foreign",
    "United Kingdom": "united_kingdom",
    "Cayman Islands": "cayman_islands",
    "Belgium":        "belgium",
    "Luxembourg":     "luxembourg",
}

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

_TIC_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MacroLens/1.0)"}


def _parse_tic_file(text: str) -> pd.DataFrame:
    """Parse TIC MFH tab-delimited file into a long-format DataFrame.

    Actual file structure (as of 2025) — tab-separated, NOT fixed-width:

      Row 0-4:  Preamble (title, blank lines)
      Row 5:    Month header  [blank tab] Dec [tab] Nov [tab] Oct ...
      Row 6:    Year header   Country [tab] 2025 [tab] 2025 ...
      Row 7:    Separator     [blank] ------ ...
      Row 8:    [blank]
      Row 9+:   Country data  Japan [tab] 1185.5 [tab] 1202.7 ...
      Row N:    Grand Total   Grand Total [tab] 9270.9 ...
      [blank rows]
      --- repeats for next year section ---

    Column 0 = country label; columns 1..N = monthly values newest-first.
    The file contains one 12-column section per calendar year going back ~20 years.
    """
    rows = [line.split("\t") for line in text.splitlines()]

    records: list[dict] = []
    current_date_cols: dict[int, pd.Period] = {}  # col_idx -> Period

    i = 0
    while i < len(rows):
        row = rows[i]
        col0 = row[0].strip() if row else ""

        # ── Month header row: first column is blank, rest are month abbreviations
        if not col0:
            month_hits = [
                (j, _MONTH_MAP[row[j].strip()[:3].lower()])
                for j in range(1, len(row))
                if row[j].strip()[:3].lower() in _MONTH_MAP
            ]
            if len(month_hits) >= 6:
                # Scan forward (up to 4 rows) for the year row
                found_year = False
                for k in range(i + 1, min(i + 5, len(rows))):
                    yr_row = rows[k]
                    year_hits = [
                        (j, int(yr_row[j].strip()))
                        for j in range(1, len(yr_row))
                        if yr_row[j].strip().isdigit()
                        and len(yr_row[j].strip()) == 4
                        and 2000 <= int(yr_row[j].strip()) <= 2035
                    ]
                    if len(year_hits) >= 6:
                        # Build date_cols: align col positions from month and year rows
                        new_date_cols: dict[int, pd.Period] = {}
                        for col_j, m_num in month_hits:
                            if col_j < len(yr_row):
                                y_str = yr_row[col_j].strip()
                                if y_str.isdigit() and len(y_str) == 4:
                                    new_date_cols[col_j] = pd.Period(
                                        f"{y_str}-{m_num:02d}", freq="M"
                                    )
                        if new_date_cols:
                            current_date_cols = new_date_cols
                        i = k + 2   # skip separator row
                        found_year = True
                        break
                if not found_year:
                    i += 1
                continue

        # ── Data row: check col0 against tracked countries
        if col0 and current_date_cols:
            matched_id = None
            for row_label, series_id in _TIC_ROWS.items():
                if row_label.lower() in col0.lower():
                    matched_id = series_id
                    break
            if matched_id:
                for col_j, period in current_date_cols.items():
                    if col_j < len(row):
                        val_str = row[col_j].strip().replace(",", "")
                        if val_str and val_str not in ("", "nan", "------"):
                            try:
                                records.append(
                                    {
                                        "date": period,
                                        "series_id": matched_id,
                                        "value_usd_billions": float(val_str),
                                    }
                                )
                            except ValueError:
                                pass
        i += 1

    if not records:
        raise ValueError("No data extracted from TIC file for tracked countries")

    df = pd.DataFrame(records).drop_duplicates(subset=["series_id", "date"])

    # Derived series
    derived: list[dict] = []
    for date, grp in df.groupby("date"):
        rm = dict(zip(grp["series_id"], grp["value_usd_billions"]))
        uk    = rm.get("united_kingdom")
        cayman = rm.get("cayman_islands")
        bel   = rm.get("belgium")
        lux   = rm.get("luxembourg")
        if uk is not None and cayman is not None:
            derived.append(
                {"date": date, "series_id": "uk_cayman",
                 "value_usd_billions": uk + cayman}
            )
        if bel is not None and lux is not None:
            derived.append(
                {"date": date, "series_id": "euroclear_proxy",
                 "value_usd_billions": bel + lux}
            )

    if derived:
        df = pd.concat([df, pd.DataFrame(derived)], ignore_index=True)

    return df.sort_values(["series_id", "date"]).reset_index(drop=True)


def _reconstruct_tic_from_cache() -> pd.DataFrame:
    """Rebuild TIC DataFrame from individual cached series.  Used on stale fallback."""
    TIC_SERIES = [
        "total_foreign", "united_kingdom", "cayman_islands",
        "belgium", "luxembourg", "uk_cayman", "euroclear_proxy",
    ]
    records: list[dict] = []
    for sid in TIC_SERIES:
        s = get_last_known_series(f"tic_{sid}")
        if s is None or s.empty:
            continue
        for dt, val in s.items():
            records.append(
                {
                    "date": pd.Period(str(dt)[:7], freq="M"),
                    "series_id": sid,
                    "value_usd_billions": float(val),
                }
            )
    if not records:
        return pd.DataFrame()
    return (
        pd.DataFrame(records)
        .sort_values(["series_id", "date"])
        .reset_index(drop=True)
    )


def get_tic_data() -> tuple[pd.DataFrame, str]:
    """Fetch and parse TIC Major Foreign Holdings data.

    Returns (long-format DataFrame, status).
    DataFrame columns: [date (Period M), series_id, value_usd_billions]
    Status: "live", "stale", or "error".

    ⚠️ Custodial bias: Belgium + Luxembourg reflect Euroclear custody location,
    NOT ultimate beneficial ownership.  The 'euroclear_proxy' series must be
    displayed with a UI caveat — do not label it 'Eurozone holdings'.

    Cache strategy: 7-day TTL.  On fetch failure, serves stale cache.
    """
    # Freshness gate: if total_foreign is fresh in cache, use cached data
    fresh_check = get_cached_series("tic_total_foreign", max_age_hours=TIC_CACHE_HOURS)
    if fresh_check is not None and not fresh_check.empty:
        df = _reconstruct_tic_from_cache()
        if not df.empty:
            return df, "live"

    try:
        resp = requests.get(TIC_MFH_URL, headers=_TIC_HEADERS, timeout=30)
        resp.raise_for_status()
        df = _parse_tic_file(resp.text)

        # Cache all individual series for stale fallback
        for sid, grp in df.groupby("series_id"):
            idx = pd.to_datetime([str(p) for p in grp["date"]])
            s = pd.Series(grp["value_usd_billions"].values, index=idx)
            write_series_to_cache(f"tic_{sid}", "treasury", s)

        return df, "live"

    except requests.exceptions.Timeout:
        logger.warning("TIC MFH fetch timed out")
    except requests.exceptions.HTTPError as exc:
        logger.warning("TIC MFH HTTP error: %s", exc)
    except Exception as exc:
        logger.warning("TIC MFH parse/fetch failed: %s", exc)

    # Stale fallback
    df = _reconstruct_tic_from_cache()
    if not df.empty:
        return df, "stale"
    return pd.DataFrame(), "error"


def get_total_foreign_holdings() -> tuple[pd.Series, str]:
    """Return monthly total foreign holdings time series ($B).

    Used by app.py to compute the TIC MoM alert value.
    Returns (series, status).
    """
    df, status = get_tic_data()
    if df.empty:
        return pd.Series(dtype=float), status
    total = df[df["series_id"] == "total_foreign"].copy()
    if total.empty:
        return pd.Series(dtype=float), status
    idx = pd.to_datetime([str(p) for p in total["date"]])
    s = pd.Series(total["value_usd_billions"].values, index=idx, name="total_foreign")
    return s.sort_index(), status
