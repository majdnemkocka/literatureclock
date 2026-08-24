# tests/test_dayparts.py
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / 'scrapers' / 'mek_search') not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / 'scrapers' / 'mek_search'))

from extractor import load_rules, extract, extract_from_html
from mek_time_search import DaypartTermGenerator, MekQueryBuilder


@pytest.fixture(scope="module")
def rules():
    return load_rules()


class TestDaypartTermGenerator:
    def test_all_12_categories_present(self):
        queries = DaypartTermGenerator.generate_daypart_queries()
        assert len(queries) == 12
        cat_ids = [q[0] for q in queries]
        assert "hajnal" in cat_ids
        assert "reggel" in cat_ids
        assert "delelott" in cat_ids
        assert "del" in cat_ids
        assert "kora_delutan" in cat_ids
        assert "delutan" in cat_ids
        assert "keso_delutan_alkonyat" in cat_ids
        assert "kora_este" in cat_ids
        assert "este" in cat_ids
        assert "keso_este" in cat_ids
        assert "ejfel_korul" in cat_ids
        assert "ejjel" in cat_ids

    def test_query_builder_pipe_formatting(self):
        queries = DaypartTermGenerator.generate_daypart_queries()
        for cat_id, terms, query in queries:
            assert len(terms) > 0
            assert len(query) > 0
            # Multi-word terms should be quoted in query
            for t in terms:
                if " " in t:
                    assert f'"{t}"' in query or f'"{t.strip()}"' in query


class TestDaypartExtraction:
    def test_isolated_este_emits_daypart(self, rules):
        text = "Gyönyörű, hűvös este volt a Dunaparton."
        hits = list(extract(text, rules, include_dayparts=True))
        assert len(hits) == 1
        h = hits[0]
        assert h["rule_id"] == "daypart_este"
        assert h["match"] == "este"
        assert h["time_min_str"] == "18:30"
        assert h["time_max_str"] == "22:00"
        assert h["time_focus_str"] == "20:00"
        assert h["time_min_m"] == 1110
        assert h["time_max_m"] == 1320
        assert h["time_focus_m"] == 1200
        assert h["is_daypart"] is True

    def test_isolated_hajnal_emits_daypart(self, rules):
        text = "Már hajnalban útnak indultak a hegyekbe."
        hits = list(extract(text, rules, include_dayparts=True))
        assert len(hits) == 1
        h = hits[0]
        assert h["rule_id"] == "daypart_hajnal"
        assert h["match"] == "hajnalban"
        assert h["time_min_str"] == "04:00"
        assert h["time_max_str"] == "07:00"
        assert h["time_focus_str"] == "05:30"

    def test_kora_delutan_emits_daypart(self, rules):
        text = "Egy csendes kora délután sétáltunk a parkban."
        hits = list(extract(text, rules, include_dayparts=True))
        assert len(hits) == 1
        h = hits[0]
        assert h["rule_id"] == "daypart_kora_delutan"
        assert h["match"] == "kora délután"
        assert h["time_min_str"] == "12:30"
        assert h["time_max_str"] == "14:30"
        assert h["time_focus_str"] == "13:30"

    def test_clock_match_suppresses_overlapping_daypart(self, rules):
        # "Este 8 órakor" contains "Este", but the specific clock time should suppress the bare daypart
        text = "Este 8 órakor kezdődött a vacsora."
        hits = list(extract(text, rules, include_dayparts=True))
        assert len(hits) == 1
        h = hits[0]
        # Should be the clock time, not the bare daypart
        assert h.get("is_daypart") is not True
        assert h["norm_time"] == "20:00"
        assert h["time_min_m"] == 1200

    def test_disabled_include_dayparts_flag(self, rules):
        text = "Gyönyörű, hűvös este volt a Dunaparton."
        hits = list(extract(text, rules, include_dayparts=False))
        assert len(hits) == 0
