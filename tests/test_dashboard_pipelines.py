import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.pipelines import get_all_pipelines, get_all_script_tasks, build_command_for_step
from dashboard.models import StepParameter


class TestDashboardPipelines(unittest.TestCase):
    def test_pipelines_structure(self):
        pipelines = get_all_pipelines()
        self.assertGreaterEqual(len(pipelines), 3)
        ids = [p.id for p in pipelines]
        self.assertIn("clock", ids)
        self.assertIn("calendar", ids)
        self.assertIn("offline", ids)

        clock_pipeline = next(p for p in pipelines if p.id == "clock")
        step_ids = [s.id for s in clock_pipeline.steps]
        self.assertIn("search", step_ids)
        self.assertIn("seed", step_ids)
        self.assertIn("ai_grade", step_ids)

    def test_build_command_with_parameters(self):
        clock_pipeline = next(p for p in get_all_pipelines() if p.id == "clock")
        search_step = next(s for s in clock_pipeline.steps if s.id == "search")
        
        # Override limit parameter
        for p in search_step.parameters:
            if p.name == "limit":
                p.value = 250

        cmd = build_command_for_step(search_step)
        self.assertTrue(any("mek_time_search.py" in str(x) for x in cmd))
        self.assertIn("--limit", cmd)
        self.assertIn("250", cmd)

    def test_script_tasks_catalog(self):
        tasks = get_all_script_tasks()
        self.assertGreaterEqual(len(tasks), 8)
        categories = {t.category for t in tasks}
        self.assertIn("Keresés & Scraper", categories)
        self.assertIn("Adatbázis", categories)
        self.assertIn("AI Minőség", categories)
