"""SQLite cache manager — stores last-known-good values for all series."""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# cache.db lives at the macrolens/ project root
DB_PATH = Path(__file__).resolve().parent.parent / "cache.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist. Called once at app startup."""
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS series_cache (
            series_id  TEXT NOT NULL,
            source     TEXT NOT NULL,
            date       TEXT NOT NULL,
            value      REAL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (series_id, date)
        );

        CREATE TABLE IF NOT EXISTS alert_history (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type       TEXT    NOT NULL,
            triggered_at     TEXT    NOT NULL,
            value_at_trigger REAL,
            email_sent       INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS panel_scores (
            calculated_at  TEXT PRIMARY KEY,
            inflation_score REAL,
            consumer_score  REAL,
            bonds_score     REAL,
            credit_score    REAL,
            crisis_stage    INTEGER
        );
    """)
    conn.commit()
    conn.close()


def get_cached_series(series_id: str, max_age_hours: int = 24) -> pd.Series | None:
    """Return a cached series if the most recent write is within max_age_hours.

    Returns None when the cache is empty or stale — the caller should trigger
    a live fetch.
    """
    cutoff = (datetime.utcnow() - timedelta(hours=max_age_hours)).isoformat()
    conn = _connect()
    rows = conn.execute(
        """
        SELECT date, value FROM series_cache
        WHERE series_id = ? AND updated_at >= ?
        ORDER BY date ASC
        """,
        (series_id, cutoff),
    ).fetchall()
    conn.close()

    if not rows:
        return None

    index = pd.to_datetime([r["date"] for r in rows])
    values = [r["value"] for r in rows]
    return pd.Series(values, index=index, name=series_id)


def write_series_to_cache(series_id: str, source: str, data: pd.Series) -> None:
    """Upsert a pandas Series into the cache."""
    if data is None or data.empty:
        return

    now = datetime.utcnow().isoformat()
    rows = [
        (series_id, source, str(idx.date()), float(val), now)
        for idx, val in data.items()
        if val is not None and not pd.isna(val)
    ]
    if not rows:
        return

    conn = _connect()
    conn.executemany(
        """
        INSERT OR REPLACE INTO series_cache
            (series_id, source, date, value, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()


def get_last_known_value(series_id: str) -> tuple[float | None, str | None]:
    """Return (value, date_str) of the most recent cached observation regardless of age.

    Used as a fallback when a live fetch fails.
    """
    conn = _connect()
    row = conn.execute(
        """
        SELECT value, date FROM series_cache
        WHERE series_id = ?
        ORDER BY date DESC
        LIMIT 1
        """,
        (series_id,),
    ).fetchone()
    conn.close()

    if row:
        return row["value"], row["date"]
    return None, None


def get_last_known_series(series_id: str) -> pd.Series | None:
    """Return all cached observations for a series, regardless of age."""
    conn = _connect()
    rows = conn.execute(
        """
        SELECT date, value FROM series_cache
        WHERE series_id = ?
        ORDER BY date ASC
        """,
        (series_id,),
    ).fetchall()
    conn.close()

    if not rows:
        return None

    index = pd.to_datetime([r["date"] for r in rows])
    values = [r["value"] for r in rows]
    return pd.Series(values, index=index, name=series_id)
