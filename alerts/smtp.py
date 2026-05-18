"""SMTP email dispatch for MacroLens alerts and weekly digest."""

import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

EMAIL_TEMPLATE = """\
MacroLens Alert — {severity}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Alert: {description}
Value: {current_value}
Threshold: {threshold}
Time: {triggered_at} UTC

Current Dashboard Status:
  Crisis Stage: {crisis_stage}
  Inflation Score: {inflation_score}/10
  Consumer Score:  {consumer_score}/10
  Bond Score:      {bonds_score}/10
  Credit Score:    {credit_score}/10
"""


def _smtp_configured() -> bool:
    return bool(
        os.getenv("ALERT_EMAIL_FROM")
        and os.getenv("ALERT_EMAIL_TO")
        and os.getenv("ALERT_EMAIL_PASSWORD")
    )


def send_alert_email(alert: dict, panel_scores: dict) -> bool:
    """Send a single alert email via SMTP.

    Returns True if the email was sent successfully, False otherwise.
    Silently skips if SMTP credentials are not configured.
    """
    if not _smtp_configured():
        return False

    from_addr = os.getenv("ALERT_EMAIL_FROM", "")
    to_addr   = os.getenv("ALERT_EMAIL_TO", "")
    password  = os.getenv("ALERT_EMAIL_PASSWORD", "")
    smtp_host = os.getenv("ALERT_SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("ALERT_SMTP_PORT", "587"))

    severity = alert.get("severity", "warning").upper()
    body = EMAIL_TEMPLATE.format(
        severity      = severity,
        description   = alert.get("description", ""),
        current_value = alert.get("current_value", "N/A"),
        threshold     = alert.get("threshold", "N/A"),
        triggered_at  = datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
        crisis_stage  = panel_scores.get("crisis_stage", "N/A"),
        inflation_score = panel_scores.get("inflation", "N/A"),
        consumer_score  = panel_scores.get("consumer",  "N/A"),
        bonds_score     = panel_scores.get("bonds",     "N/A"),
        credit_score    = panel_scores.get("credit",    "N/A"),
    )

    msg = MIMEMultipart()
    msg["From"]    = from_addr
    msg["To"]      = to_addr
    msg["Subject"] = f"MacroLens Alert [{severity}]: {alert.get('description', '')}"
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(from_addr, password)
            server.sendmail(from_addr, to_addr, msg.as_string())
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Weekly digest
# ---------------------------------------------------------------------------

WEEKLY_DIGEST_TEMPLATE = """\
MacroLens — Weekly Digest
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Week ending {week_ending}

CRISIS STAGE: Stage {crisis_stage} — {crisis_label}

PANEL SCORES  (1–10, higher = more stress):
  Inflation:  {inflation_score}/10  {inflation_arrow}
  Consumer:   {consumer_score}/10   {consumer_arrow}
  Bonds:      {bonds_score}/10      {bonds_arrow}
  Credit:     {credit_score}/10     {credit_arrow}

CHANGES SINCE LAST WEEK:
{changes}

ALERTS THIS WEEK:
{recent_alerts}
"""

_STAGE_LABELS = {
    0: "No Significant Stress",
    1: "Inflation Pressure Building",
    2: "Consumer Stress Emerging",
    3: "Bond Market Showing Strain",
    4: "Foreign Demand Deteriorating",
    5: "Dollar/Credit Crisis Signals Active",
}


def _arrow(current: float | None, prior: float | None) -> str:
    if current is None or prior is None:
        return ""
    diff = current - prior
    if diff > 0.5:
        return f"▲ +{diff:.1f}"
    if diff < -0.5:
        return f"▼ {diff:.1f}"
    return "→"


def _format_changes(current: dict, prior: dict | None) -> str:
    if prior is None:
        return "  No prior-week scores available for comparison."
    lines = []
    panels = [("Inflation", "inflation"), ("Consumer", "consumer"),
              ("Bonds", "bonds"), ("Credit", "credit")]
    for label, key in panels:
        c = current.get(key)
        p = prior.get(key)
        if c is not None and p is not None:
            diff = c - p
            if abs(diff) >= 0.5:
                direction = "increased" if diff > 0 else "decreased"
                lines.append(f"  {label}: {direction} {abs(diff):.1f} pts ({p:.1f} → {c:.1f})")
    if not lines:
        return "  No significant score changes (all panels stable within ±0.5 pts)."
    return "\n".join(lines)


def _format_alerts(recent_alerts: list[dict]) -> str:
    from config import ALERT_THRESHOLDS
    if not recent_alerts:
        return "  No alerts fired this week."
    lines = []
    for a in recent_alerts[:8]:  # cap at 8 entries
        cfg = ALERT_THRESHOLDS.get(a["alert_type"], {})
        desc = cfg.get("description", a["alert_type"])
        ts = a.get("triggered_at", "")[:16]
        lines.append(f"  [{ts}] {desc}")
    return "\n".join(lines)


def send_weekly_digest(panel_scores: dict, crisis_info: dict) -> bool:
    """Send the weekly digest email.

    panel_scores: {"inflation": float, "consumer": float, "bonds": float,
                   "credit": float, "crisis_stage": int}
    crisis_info:  {"stage": int, "label": str, "color": str}

    Returns True if sent successfully, False otherwise.
    Silently skips if SMTP credentials are not configured.
    """
    if not _smtp_configured():
        return False

    from data.cache import get_panel_scores_7d_ago, get_recent_alerts
    prior = get_panel_scores_7d_ago()
    recent_alerts = get_recent_alerts(days_back=7)

    changes = _format_changes(panel_scores, prior)
    alert_text = _format_alerts(recent_alerts)

    stage = crisis_info.get("stage", panel_scores.get("crisis_stage", 0))
    stage_label = crisis_info.get("label", _STAGE_LABELS.get(stage, "Unknown"))

    def _fmt(key: str) -> str:
        v = panel_scores.get(key)
        return f"{v:.1f}" if v is not None else "N/A"

    body = WEEKLY_DIGEST_TEMPLATE.format(
        week_ending    = datetime.utcnow().strftime("%Y-%m-%d"),
        crisis_stage   = stage,
        crisis_label   = stage_label,
        inflation_score = _fmt("inflation"),
        consumer_score  = _fmt("consumer"),
        bonds_score     = _fmt("bonds"),
        credit_score    = _fmt("credit"),
        inflation_arrow = _arrow(panel_scores.get("inflation"), prior.get("inflation") if prior else None),
        consumer_arrow  = _arrow(panel_scores.get("consumer"),  prior.get("consumer")  if prior else None),
        bonds_arrow     = _arrow(panel_scores.get("bonds"),     prior.get("bonds")     if prior else None),
        credit_arrow    = _arrow(panel_scores.get("credit"),    prior.get("credit")    if prior else None),
        changes         = changes,
        recent_alerts   = alert_text,
    )

    from_addr = os.getenv("ALERT_EMAIL_FROM", "")
    to_addr   = os.getenv("ALERT_EMAIL_TO", "")
    password  = os.getenv("ALERT_EMAIL_PASSWORD", "")
    smtp_host = os.getenv("ALERT_SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("ALERT_SMTP_PORT", "587"))

    msg = MIMEMultipart()
    msg["From"]    = from_addr
    msg["To"]      = to_addr
    msg["Subject"] = (
        f"MacroLens Weekly Digest — Stage {stage}: {stage_label} "
        f"[{datetime.utcnow().strftime('%Y-%m-%d')}]"
    )
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(from_addr, password)
            server.sendmail(from_addr, to_addr, msg.as_string())
        return True
    except Exception:
        return False
