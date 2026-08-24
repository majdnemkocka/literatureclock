# tests/test_calendar_search.py
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / 'scrapers' / 'mek_search') not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / 'scrapers' / 'mek_search'))

from mek_calendar_search import DateTermGenerator, MekQueryBuilder, load_rules


@pytest.fixture(scope="module")
def rules():
    return load_rules(REPO_ROOT / "rules_calendar.json5")


class TestCalendarDateTermGenerator:
    def test_exact_date_terms_generation(self, rules):
        gen = DateTermGenerator(rules)
        terms = gen.generate_terms_for_date(3, 15)
        assert len(terms) > 0
        # Check numeric variants
        assert "03.15." in terms or "3.15." in terms or "15.03." in terms or "15. 03." in terms
        # Check month word variants
        has_marc = any("március" in t or "marcius" in t or "márc" in t for t in terms)
        assert has_marc

    def test_month_part_queries_generation(self, rules):
        gen = DateTermGenerator(rules)
        queries = gen.generate_month_part_queries()
        # 12 months * 3 parts = 36 queries
        assert len(queries) == 36
        q_ids = [q[0] for q in queries]
        assert "month_part_03_start" in q_ids
        assert "month_part_12_end" in q_ids

        # Check meta for March start
        mar_start = next(q for q in queries if q[0] == "month_part_03_start")
        meta = mar_start[3]
        assert meta["date_min_str"] == "03-01"
        assert meta["date_max_str"] == "03-10"
        assert meta["date_focus_str"] == "03-05"

    def test_season_queries_generation(self, rules):
        gen = DateTermGenerator(rules)
        seasons = gen.generate_season_queries()
        assert len(seasons) == 4
        s_ids = [s[0] for s in seasons]
        assert "season_tavasz" in s_ids
        assert "season_nyar" in s_ids
        assert "season_osz" in s_ids
        assert "season_tel" in s_ids

        tel = next(s for s in seasons if s[0] == "season_tel")
        assert tel[3]["date_min_str"] == "12-01"
        assert tel[3]["date_max_str"] == "02-28"

    def test_weekday_queries_generation(self, rules):
        gen = DateTermGenerator(rules)
        weekdays = gen.generate_weekday_queries()
        assert len(weekdays) >= 7
        w_ids = [w[0] for w in weekdays]
        assert "dow_hetfo" in w_ids
        assert "dow_pentek" in w_ids
        assert "dow_vasarnap" in w_ids

        hetfo = next(w for w in weekdays if w[0] == "dow_hetfo")
        assert hetfo[3]["day_of_week"] == "MONDAY"

    def test_query_builder_pipe_and_quotes(self):
        terms = ["március 15.", "03.15.", "hétfő*"]
        query = MekQueryBuilder.build_query(terms)
        assert "|" in query
        assert '"március 15."' in query
