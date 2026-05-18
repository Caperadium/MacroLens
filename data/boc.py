"""Bank of Canada Valet API fetcher.

Base URL: https://www.bankofcanada.ca/valet
No authentication required.
Spec recommends 7-day cache TTL to absorb API availability risk.
"""

import requests
import pandas as pd

from data.cache import (
    get_cached_series,
    get_last_known_series,
    write_series_to_cache,
)
from config import BOC_START_DATE

BOC_BASE_URL = "https://www.bankofcanada.ca/valet"


def fetch_boc_series(
    series_name: str,
    start_date: str = BOC_START_DATE,
) -> pd.Series:
    """Live fetch from BoC Valet API. Raises on failure."""
    url = f"{BOC_BASE_URL}/observations/{series_name}/json"
    response = requests.get(url, params={"start_date": start_date}, timeout=10)
    response.raise_for_status()

    observations = response.json().get("observations", [])
    dates, values = [], []
    for obs in observations:
        raw = obs.get(series_name, {}).get("v", "")
        if raw and raw != "":
            try:
                dates.append(obs["d"])
                values.append(float(raw))
            except (ValueError, KeyError):
                continue

    if not dates:
        return pd.Series(dtype=float, name=series_name)

    return pd.Series(values, index=pd.to_datetime(dates), name=series_name)


def fetch_boc_with_fallback(
    series_name: str,
    cache_max_age_hours: int = 168,   # 7-day TTL per spec
    start_date: str = BOC_START_DATE,
) -> tuple[pd.Series | None, str]:
    """Fetch a BoC series using cache-first strategy.

    Returns (series, status) where status is "live", "stale", or "error".
    """
    cached = get_cached_series(series_name, max_age_hours=cache_max_age_hours)
    if cached is not None and not cached.empty:
        return cached, "live"

    try:
        fresh = fetch_boc_series(series_name, start_date=start_date)
        if not fresh.empty:
            write_series_to_cache(series_name, "boc", fresh)
        return fresh, "live"
    except Exception:
        stale = get_last_known_series(series_name)
        if stale is not None and not stale.empty:
            return stale, "stale"
        return None, "error"
