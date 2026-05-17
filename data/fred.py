"""FRED API fetcher with SQLite cache fallback."""

import os

import pandas as pd
from dotenv import load_dotenv
from fredapi import Fred

from data.cache import (
    get_cached_series,
    get_last_known_series,
    write_series_to_cache,
)
from config import FRED_START_DATE

load_dotenv()

_fred_client: Fred | None = None


def _get_fred() -> Fred:
    global _fred_client
    if _fred_client is None:
        api_key = os.getenv("FRED_API_KEY")
        if not api_key:
            raise ValueError(
                "FRED_API_KEY is not set. Add it to your .env file."
            )
        _fred_client = Fred(api_key=api_key)
    return _fred_client


def fetch_series(series_id: str, start_date: str = FRED_START_DATE) -> pd.Series:
    """Live fetch from FRED. Raises on API failure."""
    fred = _get_fred()
    data = fred.get_series(series_id, observation_start=start_date)
    return data.dropna()


def fetch_with_fallback(
    series_id: str,
    source: str = "fred",
    cache_max_age_hours: int = 4,
    start_date: str = FRED_START_DATE,
) -> tuple[pd.Series | None, str]:
    """Fetch a series using cache-first strategy.

    Returns:
        (series, status) where status is one of:
            "live"  — returned from fresh cache or successful live fetch
            "stale" — live fetch failed; returning last known cached value
            "error" — live fetch failed and no cache available
    """
    # 1. Return cached data if fresh enough
    cached = get_cached_series(series_id, max_age_hours=cache_max_age_hours)
    if cached is not None and not cached.empty:
        return cached, "live"

    # 2. Try live fetch
    try:
        fresh = fetch_series(series_id, start_date=start_date)
        if not fresh.empty:
            write_series_to_cache(series_id, source, fresh)
        return fresh, "live"

    except Exception:
        # 3. Fall back to stale cache
        stale = get_last_known_series(series_id)
        if stale is not None and not stale.empty:
            return stale, "stale"
        return None, "error"
