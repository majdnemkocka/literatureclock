import json
import re
import sys
import unittest
from pathlib import Path

# Add literatureclock root and scrapers/mek_search to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / 'scrapers' / 'mek_search'))

from mek_time_search import TimeTermGenerator, load_rules
from stats import get_hits_stats, load_stats


class TestRulesAndTerms(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules_path = REPO_ROOT / 'rules.json5'
        cls.rules = load_rules(cls.rules_path)

    def test_rules_loaded(self):
        self.assertIsNotNone(self.rules, "rules.json5 should load successfully")
        self.assertEqual(self.rules.get("locale"), "hu")
        self.assertIn("rules", self.rules)

    def test_relative_rules_regex(self):
        rule_map = {r["id"]: r for r in self.rules["rules"]}
        
        # Test fél regex
        fel_regex = re.compile(rule_map["relative_fel"]["pattern"], re.IGNORECASE)
        self.assertTrue(fel_regex.search("pontosan fél nyolckor jött"))
        self.assertTrue(fel_regex.search("fél 8 van"))
        self.assertTrue(fel_regex.search("fél 12 tájban"))
        self.assertTrue(fel_regex.search("fél egykor"))
        # Invalid 24h relative forms should NOT match
        self.assertIsNone(fel_regex.search("fél 18 van"))
        self.assertIsNone(fel_regex.search("fél 23 tájban"))
        self.assertIsNone(fel_regex.search("fél 0"))

        # Test negyed regex
        negyed_regex = re.compile(rule_map["relative_negyed"]["pattern"], re.IGNORECASE)
        self.assertTrue(negyed_regex.search("negyed kilenc volt"))
        self.assertTrue(negyed_regex.search("negyed 9"))
        self.assertIsNone(negyed_regex.search("negyed 19"))

        # Test háromnegyed regex
        haromnegyed_regex = re.compile(rule_map["relative_haromnegyed"]["pattern"], re.IGNORECASE)
        self.assertTrue(haromnegyed_regex.search("háromnegyed tízkor"))
        self.assertTrue(haromnegyed_regex.search("háromnegyed 10"))
        self.assertIsNone(haromnegyed_regex.search("háromnegyed 22"))

    def test_time_term_generator_relative_expressions(self):
        generator = TimeTermGenerator(self.rules)

        # 00:30 -> next hour in 12h is 1 ("fél 1", "fél egy")
        terms_0030 = generator.generate_terms(0, 30)
        self.assertIn("fél 1", terms_0030)
        self.assertIn("fél egy", terms_0030)
        self.assertNotIn("fél 24", terms_0030)
        self.assertNotIn("fél 0", terms_0030)

        # 17:30 -> next hour in 12h is 6 ("fél 6", "fél hat")
        terms_1730 = generator.generate_terms(17, 30)
        self.assertIn("fél 6", terms_1730)
        self.assertIn("fél hat", terms_1730)
        self.assertNotIn("fél 18", terms_1730)

        # 23:30 -> next hour in 12h is 12 ("fél 12", "fél tizenkettő")
        terms_2330 = generator.generate_terms(23, 30)
        self.assertIn("fél 12", terms_2330)
        self.assertIn("fél tizenkettő", terms_2330)
        self.assertNotIn("fél 24", terms_2330)

        # 11:15 -> next hour in 12h is 12 ("negyed 12", "negyed tizenkettő")
        terms_1115 = generator.generate_terms(11, 15)
        self.assertIn("negyed 12", terms_1115)
        self.assertIn("negyed tizenkettő", terms_1115)

        # 23:45 -> next hour in 12h is 12 ("háromnegyed 12", "háromnegyed tizenkettő")
        terms_2345 = generator.generate_terms(23, 45)
        self.assertIn("háromnegyed 12", terms_2345)
        self.assertIn("háromnegyed tizenkettő", terms_2345)
        self.assertNotIn("háromnegyed 24", terms_2345)

    def test_full_day_coverage(self):
        generator = TimeTermGenerator(self.rules)
        invalid_relative_pattern = re.compile(r'\b(?:fél|negyed|háromnegyed)\s*(\d+)\b')

        for h in range(24):
            for m in range(60):
                terms = generator.generate_terms(h, m)
                self.assertTrue(len(terms) > 0, f"Terms should not be empty for {h:02}:{m:02}")
                for term in terms:
                    match = invalid_relative_pattern.search(term)
                    if match:
                        num = int(match.group(1))
                        self.assertTrue(1 <= num <= 12, f"Relative hour in '{term}' for {h:02}:{m:02} must be 1..12, got {num}")

    def test_stats_guards(self):
        empty_stats = get_hits_stats(REPO_ROOT / 'non_existent_file.jsonl')
        self.assertEqual(empty_stats['total_hits'], 0)
        self.assertEqual(empty_stats['ordered_norm_times'], [])
        self.assertEqual(empty_stats['rule_id_distribution'], {})

        empty_summary = load_stats(REPO_ROOT / 'non_existent_summary.json')
        self.assertEqual(empty_summary, {})

    def test_load_rules_fallback(self):
        result = load_rules(REPO_ROOT / 'non_existent_rules.json5')
        self.assertIsNone(result)

    def test_mek_searcher_webdriver_guard(self):
        import mek_time_search
        original_webdriver = mek_time_search.webdriver
        try:
            mek_time_search.webdriver = None
            with self.assertRaises(ImportError):
                mek_time_search.MekSearcher()
        finally:
            mek_time_search.webdriver = original_webdriver


if __name__ == '__main__':
    unittest.main()
