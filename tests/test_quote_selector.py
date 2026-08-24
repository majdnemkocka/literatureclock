import pytest
from types import SimpleNamespace
from quote_selector import is_eligible, quote_weight, pick_quote

def make_entry(min_m, max_m, focus_m):
    return SimpleNamespace(time_min_m=min_m, time_max_m=max_m, time_focus_m=focus_m)

class TestIsEligible:
    def test_exact_match(self):
        e = make_entry(1050, 1050, 1050)
        assert is_eligible(e, 1050) is True

    def test_exact_no_match(self):
        e = make_entry(1050, 1050, 1050)
        assert is_eligible(e, 1051) is False

    def test_fuzzy_inside(self):
        e = make_entry(1040, 1060, 1050)
        assert is_eligible(e, 1045) is True

    def test_fuzzy_outside(self):
        e = make_entry(1040, 1060, 1050)
        assert is_eligible(e, 1039) is False

    def test_midnight_crossing_before(self):
        # "éjfél körül": 23:45(1425) - 24:15(1455)
        e = make_entry(1425, 1455, 1440)
        assert is_eligible(e, 1430) is True  # 23:50, normal range

    def test_midnight_crossing_after(self):
        # current=0:05=5, check via +1440=1445 which is in [1425,1455]
        e = make_entry(1425, 1455, 1440)
        assert is_eligible(e, 5) is True   # 00:05

    def test_midnight_crossing_outside(self):
        e = make_entry(1425, 1455, 1440)
        assert is_eligible(e, 30) is False  # 00:30, too late

    def test_none_fields_not_eligible(self):
        e = SimpleNamespace(time_min_m=None, time_max_m=None, time_focus_m=None)
        assert is_eligible(e, 600) is False

    def test_dict_entry_eligible(self):
        e = {"time_min_m": 600, "time_max_m": 660, "time_focus_m": 630}
        assert is_eligible(e, 620) is True
        assert is_eligible(e, 700) is False


class TestQuoteWeight:
    def test_exact_at_focus_max_weight(self):
        e = make_entry(1050, 1050, 1050)
        w = quote_weight(e, 1050)
        assert w == pytest.approx(1.0)

    def test_wider_interval_lower_weight(self):
        exact = make_entry(1050, 1050, 1050)
        fuzzy = make_entry(1040, 1060, 1050)
        assert quote_weight(exact, 1050) > quote_weight(fuzzy, 1050)

    def test_farther_from_focus_lower_weight(self):
        e = make_entry(1000, 1100, 1050)
        w_close = quote_weight(e, 1050)   # at focus
        w_far   = quote_weight(e, 1010)   # near edge
        assert w_close > w_far

    def test_never_zero(self):
        e = make_entry(1140, 1380, 1260)  # "este"
        assert quote_weight(e, 1140) > 0

    def test_dict_entry_weight(self):
        e = {"time_min_m": 1050, "time_max_m": 1050, "time_focus_m": 1050}
        assert quote_weight(e, 1050) == pytest.approx(1.0)


class TestPickQuote:
    def test_returns_none_for_empty(self):
        assert pick_quote([], 600) is None

    def test_returns_eligible(self):
        e = make_entry(600, 600, 600)
        result = pick_quote([e], 600)
        assert result is e

    def test_filters_ineligible(self):
        e_ok  = make_entry(600, 600, 600)
        e_bad = make_entry(700, 700, 700)
        result = pick_quote([e_ok, e_bad], 600)
        assert result is e_ok

    def test_none_eligible_returns_none(self):
        e = make_entry(700, 700, 700)
        assert pick_quote([e], 600) is None

    def test_pick_with_dict_candidates(self):
        e_ok = {"time_min_m": 600, "time_max_m": 600, "time_focus_m": 600}
        e_bad = {"time_min_m": 700, "time_max_m": 700, "time_focus_m": 700}
        result = pick_quote([e_ok, e_bad], 600)
        assert result == e_ok
