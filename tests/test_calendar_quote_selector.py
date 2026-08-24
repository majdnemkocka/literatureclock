# tests/test_calendar_quote_selector.py
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from calendar_quote_selector import (
    is_calendar_eligible,
    calendar_quote_weight,
    pick_calendar_quote,
)


def make_entry(min_d=None, max_d=None, focus_d=None, dow=None, dow_num=None):
    return SimpleNamespace(
        date_min_d=min_d,
        date_max_d=max_d,
        date_focus_d=focus_d,
        day_of_week=dow,
        day_of_week_num=dow_num,
    )


class TestIsCalendarEligible:
    def test_exact_date_match(self):
        e = make_entry(min_d=75, max_d=75, focus_d=75)  # March 15
        assert is_calendar_eligible(e, 75, 1) is True
        assert is_calendar_eligible(e, 76, 1) is False

    def test_fuzzy_date_interval(self):
        e = make_entry(min_d=61, max_d=70, focus_d=65)  # March 1-10
        assert is_calendar_eligible(e, 65, 1) is True
        assert is_calendar_eligible(e, 71, 1) is False

    def test_year_crossing_winter(self):
        # Dec 1 (335) to Feb 28 (424)
        e = make_entry(min_d=335, max_d=424, focus_d=380)
        assert is_calendar_eligible(e, 350, 1) is True  # Dec 15
        assert is_calendar_eligible(e, 15, 1) is True   # Jan 15 (15 + 366 = 381 in [335, 424])
        assert is_calendar_eligible(e, 100, 1) is False # Apr 10

    def test_weekday_match(self):
        e = make_entry(dow="MONDAY", dow_num=1)
        assert is_calendar_eligible(e, 100, 1) is True   # Monday
        assert is_calendar_eligible(e, 100, 2) is False  # Tuesday

    def test_weekend_match(self):
        e = make_entry(dow="WEEKEND", dow_num=None)
        assert is_calendar_eligible(e, 100, 6) is True  # Saturday
        assert is_calendar_eligible(e, 100, 7) is True  # Sunday
        assert is_calendar_eligible(e, 100, 5) is False # Friday

    def test_dict_entry_support(self):
        e = {"date_min_d": 75, "date_max_d": 75, "date_focus_d": 75, "day_of_week_num": None}
        assert is_calendar_eligible(e, 75, 1) is True

    def test_none_fields_ineligible(self):
        e = make_entry()
        assert is_calendar_eligible(e, 75, 1) is False


class TestCalendarQuoteWeight:
    def test_exact_date_highest_weight(self):
        exact = make_entry(min_d=75, max_d=75, focus_d=75)
        fuzzy = make_entry(min_d=61, max_d=91, focus_d=75)
        assert calendar_quote_weight(exact, 75, 1) > calendar_quote_weight(fuzzy, 75, 1)

    def test_weekday_hybrid_bonus(self):
        # A quote that matches BOTH the date and the day of week gets bonus
        date_only = make_entry(min_d=75, max_d=75, focus_d=75)
        hybrid = make_entry(min_d=75, max_d=75, focus_d=75, dow="MONDAY", dow_num=1)
        assert calendar_quote_weight(hybrid, 75, 1) > calendar_quote_weight(date_only, 75, 1)

    def test_weight_never_zero(self):
        e = make_entry(min_d=1, max_d=366, focus_d=183)
        assert calendar_quote_weight(e, 1, 1) > 0


class TestPickCalendarQuote:
    def test_empty_candidates_returns_none(self):
        assert pick_calendar_quote([], 75, 1) is None

    def test_filters_ineligible_candidates(self):
        e_ok = make_entry(min_d=75, max_d=75, focus_d=75)
        e_bad = make_entry(min_d=100, max_d=100, focus_d=100)
        res = pick_calendar_quote([e_ok, e_bad], 75, 1)
        assert res is e_ok
