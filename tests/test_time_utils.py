# tests/test_time_utils.py
import pytest
from time_utils import parse_extended_hhmm, validated_extended_hhmm, minutes_to_hhmm, circular_dist

class TestParseExtendedHHMM:
    def test_normal(self):
        assert parse_extended_hhmm("17:30") == 1050
    def test_midnight_exact(self):
        assert parse_extended_hhmm("00:00") == 0
    def test_extended_24(self):
        assert parse_extended_hhmm("24:15") == 1455
    def test_extended_26(self):
        assert parse_extended_hhmm("26:00") == 1560
    def test_bad_format_raises(self):
        with pytest.raises(ValueError):
            parse_extended_hhmm("badvalue")
    def test_bad_minutes_raises(self):
        with pytest.raises(ValueError):
            parse_extended_hhmm("10:60")

class TestValidatedExtendedHHMM:
    def test_valid_normal(self):
        assert validated_extended_hhmm("13:45") == ("13:45", 825)
    def test_valid_extended(self):
        assert validated_extended_hhmm("24:15") == ("24:15", 1455)
    def test_none_input(self):
        assert validated_extended_hhmm(None) == (None, None)
    def test_bad_minutes(self):
        assert validated_extended_hhmm("10:60") == (None, None)
    def test_h_too_large(self):
        assert validated_extended_hhmm("49:00") == (None, None)
    def test_non_string(self):
        assert validated_extended_hhmm(1730) == (None, None)

class TestMinutesToHHMM:
    def test_normal(self):
        assert minutes_to_hhmm(1050) == "17:30"
    def test_midnight(self):
        assert minutes_to_hhmm(1440) == "24:00"
    def test_extended(self):
        assert minutes_to_hhmm(1455) == "24:15"

class TestCircularDist:
    def test_same(self):
        assert circular_dist(600, 600) == 0
    def test_simple(self):
        assert circular_dist(600, 620) == 20
    def test_wrap_midnight(self):
        # 23:50 (1430) to 00:10 (10): dist = 20, not 1420
        assert circular_dist(1430, 10) == 20
    def test_max_dist(self):
        assert circular_dist(0, 720) == 720
