# calendar_quote_selector.py
"""
Eligibility check and 2D weighted random selection for Literature Calendar quotes.
Supports date intervals (including year-crossing 365+ intervals) and days of the week.
"""
from __future__ import annotations
import random
from typing import Any, List, Optional

from date_utils import circular_day_dist


def _get(entry: Any, attr: str) -> Any:
    """Support both object attributes and dictionary keys."""
    if isinstance(entry, dict):
        return entry.get(attr)
    return getattr(entry, attr, None)


def is_calendar_eligible(entry: Any, current_day: int, current_dow: int) -> bool:
    """
    Check if a quote is eligible for current day-of-year (1..366) and day-of-week (1..7).
    Eligible if its date interval covers current_day OR its weekday matches current_dow.
    """
    min_d = _get(entry, "date_min_d")
    max_d = _get(entry, "date_max_d")
    dow_num = _get(entry, "day_of_week_num")
    dow_str = _get(entry, "day_of_week")

    date_match = False
    if min_d is not None and max_d is not None:
        date_match = (min_d <= current_day <= max_d or min_d <= current_day + 366 <= max_d)

    dow_match = False
    if dow_num is not None:
        dow_match = (dow_num == current_dow)
    elif dow_str == "WEEKEND" and current_dow in (6, 7):
        dow_match = True

    return date_match or dow_match


def calendar_quote_weight(entry: Any, current_day: int, current_dow: int) -> float:
    """
    Compute 2D selection weight for a calendar entry.
    Considers date interval precision, circular distance to focus, and weekday alignment.
    Always returns a strictly positive float (> 0).
    """
    min_d = _get(entry, "date_min_d")
    max_d = _get(entry, "date_max_d")
    focus_d = _get(entry, "date_focus_d")
    dow_num = _get(entry, "day_of_week_num")
    dow_str = _get(entry, "day_of_week")

    # Date component
    date_match = False
    if min_d is not None and max_d is not None:
        date_match = (min_d <= current_day <= max_d or min_d <= current_day + 366 <= max_d)
        precision = max(0, max_d - min_d)
        foc = focus_d if focus_d is not None else min_d
        dist = circular_day_dist(current_day, ((foc - 1) % 366) + 1)
        date_factor = 1.0 / ((1 + precision) * (1 + dist))
    else:
        date_factor = 0.2  # Weekday-only baseline

    # Weekday component
    dow_match = False
    if dow_num is not None:
        dow_match = (dow_num == current_dow)
    elif dow_str == "WEEKEND" and current_dow in (6, 7):
        dow_match = True

    # Multipliers
    if date_match and dow_match:
        multiplier = 4.0  # Hybrid match: both date and weekday match!
    elif dow_match:
        multiplier = 2.0
    else:
        multiplier = 1.0

    return max(0.0001, date_factor * multiplier)


def pick_calendar_quote(candidates: List[Any], current_day: int, current_dow: int) -> Optional[Any]:
    """
    Select one candidate using weighted random sampling.
    Returns None if no candidate is eligible.
    """
    eligible = [e for e in candidates if is_calendar_eligible(e, current_day, current_dow)]
    if not eligible:
        return None
    weights = [calendar_quote_weight(e, current_day, current_dow) for e in eligible]
    return random.choices(eligible, weights=weights, k=1)[0]
