"""
Eligibility check and weighted random selection for Literature Clock quotes.
Supports interval-based times including midnight-crossing (time_max_m >= 1440).
"""
from __future__ import annotations
import random
from typing import Any

from time_utils import circular_dist


def _get(entry, attr: str):
    """Support both object attributes and dict keys."""
    if isinstance(entry, dict):
        return entry.get(attr)
    return getattr(entry, attr, None)


def is_eligible(entry, current_m: int) -> bool:
    """
    Return True if the entry's interval covers current_m.
    current_m: minutes since 00:00 (0..1439).
    Handles midnight-crossing intervals (time_max_m >= 1440) by also
    testing current_m + 1440.
    """
    min_m = _get(entry, 'time_min_m')
    max_m = _get(entry, 'time_max_m')
    if min_m is None or max_m is None:
        return False
    return (min_m <= current_m <= max_m or
            min_m <= current_m + 1440 <= max_m)


def quote_weight(entry, current_m: int) -> float:
    """
    Compute selection weight for an entry at current_m.
    Higher weight = more likely to be shown.
    Formula: 1 / ((1 + precision) * (1 + dist_to_focus))
    - precision = time_max_m - time_min_m  (0 for exact times)
    - dist_to_focus = circular distance (mod 1440) from current_m to time_focus_m
    Always > 0.
    """
    min_val = _get(entry, 'time_min_m')
    min_m = 0 if min_val is None else min_val
    max_val = _get(entry, 'time_max_m')
    max_m = 0 if max_val is None else max_val
    focus_val = _get(entry, 'time_focus_m')
    focus_m = min_m if focus_val is None else focus_val

    precision = max_m - min_m
    dist = circular_dist(current_m, focus_m % 1440)
    return 1.0 / ((1 + precision) * (1 + dist))


def pick_quote(candidates: list, current_m: int) -> Any | None:
    """
    Pick one quote using weighted random selection.
    Returns None if no candidate is eligible for current_m.
    """
    eligible = [e for e in candidates if is_eligible(e, current_m)]
    if not eligible:
        return None
    weights = [quote_weight(e, current_m) for e in eligible]
    return random.choices(eligible, weights=weights, k=1)[0]
