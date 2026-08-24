# tests/test_date_utils.py
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from date_utils import (
    mmdd_to_day_of_year,
    day_of_year_to_mmdd,
    validated_mmdd,
    circular_day_dist,
    parse_day_of_week,
    dow_name_to_num,
)


class TestMMDDToDayOfYear:
    def test_january_first(self):
        assert mmdd_to_day_of_year("01-01") == 1

    def test_february_29(self):
        # 366-day leap year base: Jan = 31 days, Feb 29 = 31 + 29 = 60
        assert mmdd_to_day_of_year("02-29") == 60

    def test_march_first(self):
        # 31 + 29 + 1 = 61
        assert mmdd_to_day_of_year("03-01") == 61

    def test_august_24(self):
        # Jan 31 + Feb 29 + Mar 31 + Apr 30 + May 31 + Jun 30 + Jul 31 + 24 = 237
        assert mmdd_to_day_of_year("08-24") == 237

    def test_december_31(self):
        assert mmdd_to_day_of_year("12-31") == 366

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            mmdd_to_day_of_year("invalid")

    def test_invalid_month_raises(self):
        with pytest.raises(ValueError):
            mmdd_to_day_of_year("13-01")

    def test_invalid_day_raises(self):
        with pytest.raises(ValueError):
            mmdd_to_day_of_year("02-30")


class TestDayOfYearToMMDD:
    def test_day_1(self):
        assert day_of_year_to_mmdd(1) == "01-01"

    def test_day_60(self):
        assert day_of_year_to_mmdd(60) == "02-29"

    def test_day_61(self):
        assert day_of_year_to_mmdd(61) == "03-01"

    def test_day_366(self):
        assert day_of_year_to_mmdd(366) == "12-31"

    def test_year_crossing_extended_day(self):
        # Day 367 = Jan 1 of next year
        assert day_of_year_to_mmdd(367) == "01-01"
        # Day 425 = Feb 28 of next year (366 + 31 + 28 = 425)
        assert day_of_year_to_mmdd(425) == "02-28"


class TestValidatedMMDD:
    def test_valid(self):
        assert validated_mmdd("03-15") == ("03-15", 75)

    def test_none_input(self):
        assert validated_mmdd(None) == (None, None)

    def test_invalid_str(self):
        assert validated_mmdd("bad-date") == (None, None)


class TestCircularDayDist:
    def test_same_day(self):
        assert circular_day_dist(100, 100) == 0

    def test_simple_diff(self):
        assert circular_day_dist(100, 120) == 20

    def test_year_end_wrap(self):
        # Dec 31 (366) to Jan 5 (5): distance is 5 days, not 361
        assert circular_day_dist(366, 5) == 5

    def test_max_dist(self):
        # 366 // 2 = 183
        assert circular_day_dist(1, 184) == 183


class TestParseDayOfWeek:
    def test_hungarian_weekdays(self):
        assert parse_day_of_week("hétfő") == ("MONDAY", 1)
        assert parse_day_of_week("hétfőn") == ("MONDAY", 1)
        assert parse_day_of_week("kedd") == ("TUESDAY", 2)
        assert parse_day_of_week("kedden") == ("TUESDAY", 2)
        assert parse_day_of_week("szerda") == ("WEDNESDAY", 3)
        assert parse_day_of_week("szerdán") == ("WEDNESDAY", 3)
        assert parse_day_of_week("csütörtök") == ("THURSDAY", 4)
        assert parse_day_of_week("csütörtökön") == ("THURSDAY", 4)
        assert parse_day_of_week("péntek") == ("FRIDAY", 5)
        assert parse_day_of_week("pénteken") == ("FRIDAY", 5)
        assert parse_day_of_week("szombat") == ("SATURDAY", 6)
        assert parse_day_of_week("szombaton") == ("SATURDAY", 6)
        assert parse_day_of_week("vasárnap") == ("SUNDAY", 7)
        assert parse_day_of_week("hétvége") == ("WEEKEND", None)
        assert parse_day_of_week("hétvégén") == ("WEEKEND", None)

    def test_none_or_unknown(self):
        assert parse_day_of_week(None) == (None, None)
        assert parse_day_of_week("valami") == (None, None)
