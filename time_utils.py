# time_utils.py
"""Utility functions for extended HH:MM time notation used by the literature clock."""

from __future__ import annotations
import re


def parse_extended_hhmm(s: str) -> int:
    """
    Parse "HH:MM" to integer minutes since 00:00.
    HH may be >= 24 for midnight-crossing intervals (e.g. "24:15" -> 1455).
    Raises ValueError on malformed input or invalid minutes.
    """
    if not isinstance(s, str):
        raise ValueError(f"Expected str, got {type(s)}")
    s = s.strip()
    if not re.match(r'^\d{1,2}:\d{2}$', s):
        raise ValueError(f"Invalid HH:MM format: {s!r}")
    h, m = map(int, s.split(':'))
    if m > 59:
        raise ValueError(f"Minutes out of range: {m}")
    return h * 60 + m


def validated_extended_hhmm(s) -> tuple[str, int] | tuple[None, None]:
    """
    Like parse_extended_hhmm but returns (None, None) instead of raising.
    Also rejects h > 48 (practical upper bound ~27:00 for 'éjjel' intervals).
    """
    if not isinstance(s, str):
        return None, None
    try:
        minutes = parse_extended_hhmm(s)
    except ValueError:
        return None, None
    h = minutes // 60
    if h > 48:
        return None, None
    return s.strip(), minutes


def minutes_to_hhmm(m: int) -> str:
    """Convert integer minutes to "HH:MM" (HH may be >= 24)."""
    return f"{m // 60:02d}:{m % 60:02d}"


def circular_dist(a_m: int, b_m: int) -> int:
    """
    Shortest circular distance between two minute values on a 1440-minute clock.
    Both inputs are taken mod 1440 first.
    Result is in [0, 720].
    """
    a = a_m % 1440
    b = b_m % 1440
    diff = abs(a - b)
    return min(diff, 1440 - diff)
