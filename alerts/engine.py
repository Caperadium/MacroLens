"""Alert engine — threshold evaluation and cooldown management."""

from datetime import datetime, timedelta

from data.cache import _connect
from config import ALERT_THRESHOLDS


def should_send_alert(alert_type: str, cooldown_hours: int) -> bool:
    """Return True if this alert has NOT fired within its cooldown window."""
    cutoff = (datetime.utcnow() - timedelta(hours=cooldown_hours)).isoformat()
    conn = _connect()
    row = conn.execute(
        """
        SELECT id FROM alert_history
        WHERE alert_type = ? AND triggered_at >= ?
        ORDER BY triggered_at DESC
        LIMIT 1
        """,
        (alert_type, cutoff),
    ).fetchone()
    conn.close()
    return row is None


def record_alert_fired(alert_type: str, value: float | str, email_sent: bool) -> None:
    """Write a fired alert to alert_history."""
    conn = _connect()
    conn.execute(
        """
        INSERT INTO alert_history (alert_type, triggered_at, value_at_trigger, email_sent)
        VALUES (?, ?, ?, ?)
        """,
        (
            alert_type,
            datetime.utcnow().isoformat(),
            float(value) if isinstance(value, (int, float)) else None,
            int(email_sent),
        ),
    )
    conn.commit()
    conn.close()


def check_all_alerts(current_values: dict) -> list[dict]:
    """Evaluate every threshold in ALERT_THRESHOLDS against current_values.

    Returns a list of alert dicts (one per triggered, non-cooldown-blocked alert).
    Each dict has keys: alert_type, description, severity, current_value, threshold.
    """
    fired = []

    for alert_type, cfg in ALERT_THRESHOLDS.items():
        series    = cfg["series"]
        condition = cfg["condition"]
        threshold = cfg["threshold"]
        cooldown  = cfg["cooldown_hours"]

        current_value = current_values.get(series)
        if current_value is None:
            continue

        triggered = False
        if condition == "above" and isinstance(current_value, (int, float)):
            triggered = current_value > threshold
        elif condition == "below" and isinstance(current_value, (int, float)):
            triggered = current_value < threshold
        elif condition == "equals":
            triggered = current_value == threshold

        if triggered and should_send_alert(alert_type, cooldown):
            fired.append({
                "alert_type":    alert_type,
                "description":   cfg["description"],
                "severity":      cfg["severity"],
                "current_value": current_value,
                "threshold":     threshold,
            })

    return fired
