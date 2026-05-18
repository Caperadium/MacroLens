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

        CREATE TABLE IF NOT EXISTS manual_inputs (
            series_id       TEXT NOT NULL,
            reference_month TEXT NOT NULL,
            value           REAL NOT NULL,
            entered_at      TEXT NOT NULL,
            entered_by      TEXT DEFAULT 'user',
            PRIMARY KEY (series_id, reference_month)
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


# ---------------------------------------------------------------------------
# Panel score history (used by weekly digest)
# ---------------------------------------------------------------------------

def write_panel_scores(scores: dict) -> None:
    """Write current panel scores to the panel_scores table."""
    conn = _connect()
    conn.execute(
        """
        INSERT OR REPLACE INTO panel_scores
            (calculated_at, inflation_score, consumer_score,
             bonds_score, credit_score, crisis_stage)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.utcnow().isoformat(),
            scores.get("inflation"),
            scores.get("consumer"),
            scores.get("bonds"),
            scores.get("credit"),
            scores.get("crisis_stage"),
        ),
    )
    conn.commit()
    conn.close()


def get_panel_scores_7d_ago() -> dict | None:
    """Return panel scores from approximately 7 days ago, or None if not available."""
    cutoff_old = (datetime.utcnow() - timedelta(hours=8 * 24)).isoformat()
    cutoff_new = (datetime.utcnow() - timedelta(hours=6 * 24)).isoformat()
    conn = _connect()
    row = conn.execute(
        """
        SELECT * FROM panel_scores
        WHERE calculated_at BETWEEN ? AND ?
        ORDER BY calculated_at DESC
        LIMIT 1
        """,
        (cutoff_old, cutoff_new),
    ).fetchone()
    conn.close()
    if row:
        return {
            "inflation":   row["inflation_score"],
            "consumer":    row["consumer_score"],
            "bonds":       row["bonds_score"],
            "credit":      row["credit_score"],
            "crisis_stage": row["crisis_stage"],
        }
    return None


def get_recent_alerts(days_back: int = 7) -> list[dict]:
    """Return alerts fired in the last days_back days."""
    cutoff = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
    conn = _connect()
    rows = conn.execute(
        """
        SELECT alert_type, triggered_at, value_at_trigger, email_sent
        FROM alert_history
        WHERE triggered_at >= ?
        ORDER BY triggered_at DESC
        """,
        (cutoff,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Manual input helpers (ISM, KC Fed — not available via free API)
# ---------------------------------------------------------------------------

def get_last_6_months() -> list[str]:
    """Return list of 'YYYY-MM' strings for the current and prior 5 months."""
    today = datetime.utcnow()
    months = []
    year, month = today.year, today.month
    for _ in range(6):
        months.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return months


def get_manual_input(series_id: str, reference_month: str) -> float | None:
    """Return the stored value for a series/month, or None if not yet entered."""
    conn = _connect()
    row = conn.execute(
        "SELECT value FROM manual_inputs WHERE series_id = ? AND reference_month = ?",
        (series_id, reference_month),
    ).fetchone()
    conn.close()
    return float(row["value"]) if row else None


def get_manual_input_with_meta(
    series_id: str, reference_month: str
) -> dict | None:
    """Return {'value': float, 'entered_at': str} or None."""
    conn = _connect()
    row = conn.execute(
        "SELECT value, entered_at FROM manual_inputs "
        "WHERE series_id = ? AND reference_month = ?",
        (series_id, reference_month),
    ).fetchone()
    conn.close()
    if row:
        return {"value": float(row["value"]), "entered_at": row["entered_at"]}
    return None


def save_manual_input(series_id: str, reference_month: str, value: float) -> None:
    """Upsert a manual input value."""
    now = datetime.utcnow().isoformat()
    conn = _connect()
    conn.execute(
        """
        INSERT OR REPLACE INTO manual_inputs
            (series_id, reference_month, value, entered_at)
        VALUES (?, ?, ?, ?)
        """,
        (series_id, reference_month, value, now),
    )
    conn.commit()
    conn.close()


def get_current_month_manual() -> dict:
    """Return manual inputs for the current month.

    Returns dict with keys ism_mfg_prices, ism_svc_prices, kc_fed_prices_paid.
    Values are float | None.
    """
    today = datetime.utcnow()
    current_month = f"{today.year:04d}-{today.month:02d}"
    return {
        "ism_mfg_prices":    get_manual_input("ism_mfg_prices",    current_month),
        "ism_svc_prices":    get_manual_input("ism_svc_prices",    current_month),
        "kc_fed_prices_paid": get_manual_input("kc_fed_prices_paid", current_month),
        "reference_month":   current_month,
    }
