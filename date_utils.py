# date_utils.py
"""
Date utility functions for perpetual calendar (MM-DD) mapping, year-crossing intervals,
circular day distance, and Hungarian weekday normalization.
Uses a 366-day leap year base (Feb 29 = Day 60, Dec 31 = Day 366).
"""
from __future__ import annotations
import re
import unicodedata
from typing import Optional, Tuple

MONTH_DAYS = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
MONTH_OFFSETS = [0]
for d in MONTH_DAYS[:-1]:
    MONTH_OFFSETS.append(MONTH_OFFSETS[-1] + d)

WEEKDAY_MAP = {
    "hetfo": ("MONDAY", 1),
    "hetfon": ("MONDAY", 1),
    "hetfoi": ("MONDAY", 1),
    "kedd": ("TUESDAY", 2),
    "kedden": ("TUESDAY", 2),
    "keddi": ("TUESDAY", 2),
    "szerda": ("WEDNESDAY", 3),
    "szerdan": ("WEDNESDAY", 3),
    "szerdai": ("WEDNESDAY", 3),
    "csutortok": ("THURSDAY", 4),
    "csutortokon": ("THURSDAY", 4),
    "csutortoki": ("THURSDAY", 4),
    "pentek": ("FRIDAY", 5),
    "penteken": ("FRIDAY", 5),
    "penteki": ("FRIDAY", 5),
    "szombat": ("SATURDAY", 6),
    "szombaton": ("SATURDAY", 6),
    "szombati": ("SATURDAY", 6),
    "vasarnap": ("SUNDAY", 7),
    "vasarnapi": ("SUNDAY", 7),
    "hetvege": ("WEEKEND", None),
    "hetvegen": ("WEEKEND", None),
    "hetvegi": ("WEEKEND", None),
}


def _norm(s: str) -> str:
    s = s.lower().strip()
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def mmdd_to_day_of_year(s: str) -> int:
    """
    Parse "MM-DD" to integer day of year in 1..366.
    Raises ValueError on malformed format or out-of-range dates.
    """
    if not isinstance(s, str):
        raise ValueError(f"Expected str, got {type(s)}")
    s = s.strip()
    match = re.match(r"^(\d{1,2})[-/.](\d{1,2})$", s)
    if not match:
        raise ValueError(f"Invalid MM-DD format: {s!r}")
    m = int(match.group(1))
    d = int(match.group(2))
    if not (1 <= m <= 12):
        raise ValueError(f"Month out of range: {m}")
    max_days = MONTH_DAYS[m - 1]
    if not (1 <= d <= max_days):
        raise ValueError(f"Day out of range for month {m}: {d} (max {max_days})")
    return MONTH_OFFSETS[m - 1] + d


def day_of_year_to_mmdd(day: int) -> str:
    """
    Convert integer day (1..366, or >366 for year-crossing intervals) to "MM-DD".
    """
    if day <= 0:
        day = 1
    # Wrap day modulo 366 (1-indexed)
    normalized_day = ((day - 1) % 366) + 1
    for m in range(12, 0, -1):
        if normalized_day > MONTH_OFFSETS[m - 1]:
            d = normalized_day - MONTH_OFFSETS[m - 1]
            return f"{m:02d}-{d:02d}"
    return "01-01"


def validated_mmdd(s: Optional[str]) -> Tuple[Optional[str], Optional[int]]:
    """
    Safe validator: returns (formatted_mmdd, day_of_year) or (None, None).
    """
    if not isinstance(s, str):
        return None, None
    try:
        day = mmdd_to_day_of_year(s)
        formatted = day_of_year_to_mmdd(day)
        return formatted, day
    except ValueError:
        return None, None


def circular_day_dist(d1: int, d2: int) -> int:
    """
    Shortest circular distance between two days on a 366-day circular calendar.
    Result in [0, 183].
    """
    a = ((d1 - 1) % 366) + 1
    b = ((d2 - 1) % 366) + 1
    diff = abs(a - b)
    return min(diff, 366 - diff)


def parse_day_of_week(s: Optional[str]) -> Tuple[Optional[str], Optional[int]]:
    """
    Parse a Hungarian weekday or weekend string.
    Returns (UPPER_NAME, 1..7) or ("WEEKEND", None) or (None, None).
    """
    if not isinstance(s, str):
        return None, None
    norm_s = _norm(s)
    if norm_s in WEEKDAY_MAP:
        return WEEKDAY_MAP[norm_s]
    # Check English enum values
    upper = s.strip().upper()
    if upper in ("MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"):
        num = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"].index(upper) + 1
        return upper, num
    if upper == "WEEKEND":
        return "WEEKEND", None
    return None, None


def dow_name_to_num(name: Optional[str]) -> Optional[int]:
    """Convert English DOW string to 1..7 (Monday=1, Sunday=7) or None."""
    if not name:
        return None
    name = name.strip().upper()
    mapping = {
        "MONDAY": 1, "TUESDAY": 2, "WEDNESDAY": 3,
        "THURSDAY": 4, "FRIDAY": 5, "SATURDAY": 6, "SUNDAY": 7
    }
    return mapping.get(name)
