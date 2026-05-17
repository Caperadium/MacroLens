"""Derived metrics — all pure functions, no I/O."""

import pandas as pd


def classify_yield_curve_move(
    spread_current: float,
    spread_prior: float,
    yield_2yr_current: float,
    yield_2yr_prior: float,
) -> str:
    """Classify the 20-day yield curve regime.

    Both arguments for spread are in basis points.
    Both yield arguments are in percent.
    Returns one of: Bear Flattener, Bear Steepener, Bull Flattener,
    Bull Steepener, Unchanged.
    """
    MOVE_THRESHOLD_BPS = 5

    yields_rising  = yield_2yr_current > yield_2yr_prior + (MOVE_THRESHOLD_BPS / 100)
    yields_falling = yield_2yr_current < yield_2yr_prior - (MOVE_THRESHOLD_BPS / 100)
    spread_narrowing = spread_current < spread_prior - MOVE_THRESHOLD_BPS
    spread_widening  = spread_current > spread_prior + MOVE_THRESHOLD_BPS

    if yields_rising and spread_narrowing:
        return "Bear Flattener"
    if yields_rising and spread_widening:
        return "Bear Steepener"
    if yields_falling and spread_narrowing:
        return "Bull Flattener"
    if yields_falling and spread_widening:
        return "Bull Steepener"
    return "Unchanged"


def dollar_yield_divergence(
    yield_10yr_series: pd.Series,
    dxy_series: pd.Series,
) -> dict:
    """Detect dollar/yield divergence over the past 20 trading days.

    Normal stress:  yields rising + dollar rising
    Crisis signal:  yields rising + dollar FALLING (potential capital flight)

    Returns a dict with keys: flag, yield_trend, dollar_trend, description.
    """
    WINDOW = 20
    THRESHOLD_DAYS = 10

    combined = pd.DataFrame(
        {"yield": yield_10yr_series, "dxy": dxy_series}
    ).dropna()

    if len(combined) < WINDOW:
        return {
            "flag":         "neutral",
            "yield_trend":  "flat",
            "dollar_trend": "flat",
            "description":  "Insufficient data for divergence analysis",
        }

    recent = combined.tail(WINDOW)
    yield_changes  = recent["yield"].diff().dropna()
    dollar_changes = recent["dxy"].diff().dropna()

    yield_rising_days  = (yield_changes > 0).sum()
    dollar_rising_days = (dollar_changes > 0).sum()

    def _trend(rising_days: int) -> str:
        if rising_days >= THRESHOLD_DAYS:
            return "rising"
        if rising_days <= WINDOW - THRESHOLD_DAYS:
            return "falling"
        return "flat"

    yield_trend  = _trend(yield_rising_days)
    dollar_trend = _trend(dollar_rising_days)

    if yield_trend == "rising" and dollar_trend == "falling":
        flag = "crisis_signal"
        description = (
            "Yields rising while dollar weakening — "
            "potential capital flight from US assets"
        )
    elif yield_trend == "rising" and dollar_trend == "rising":
        flag = "normal_stress"
        description = (
            "Yields and dollar both rising — "
            "normal risk-off rotation, not a crisis signal"
        )
    else:
        flag = "neutral"
        description = "No significant dollar/yield divergence detected"

    return {
        "flag":         flag,
        "yield_trend":  yield_trend,
        "dollar_trend": dollar_trend,
        "description":  description,
    }


def yoy_pct_change(series: pd.Series) -> pd.Series:
    """Year-over-year % change. Uses 12-period shift for monthly, 252 for daily."""
    inferred = pd.infer_freq(series.index)
    if inferred and inferred.startswith("M"):
        return (series / series.shift(12) - 1) * 100
    return (series / series.shift(252) - 1) * 100


def calculate_real_wage_growth(
    avg_hourly_earnings: pd.Series,
    cpi: pd.Series,
) -> pd.Series:
    wage_mom = avg_hourly_earnings.pct_change() * 100
    cpi_mom  = cpi.pct_change() * 100
    return (wage_mom - cpi_mom).dropna()


def score_indicator(value: float, series_name: str) -> int:
    """Map a single indicator value to a 1-10 stress score using threshold bands."""
    from config import SCORE_THRESHOLDS

    config = SCORE_THRESHOLDS.get(series_name)
    if config is None:
        return 5
    for upper_bound, score in config["bands"]:
        if value <= upper_bound:
            return score
    return 10


def calculate_panel_score(panel_name: str, indicator_values: dict) -> float:
    """Weighted average stress score (1–10) for a panel.

    Skips indicators that are missing or None; normalises by the weight of
    indicators that were successfully scored so the result stays on a 1-10 scale
    even when some inputs are unavailable.
    """
    from config import PANEL_WEIGHTS

    weights = PANEL_WEIGHTS.get(panel_name, {})
    total_score  = 0.0
    total_weight = 0.0

    for indicator, weight in weights.items():
        value = indicator_values.get(indicator)
        if value is None:
            continue
        raw_score     = score_indicator(value, indicator)
        total_score  += raw_score * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0
    return round(total_score / total_weight, 1)
