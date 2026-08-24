import asyncio
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.app import LiteratureClockDashboardApp
from dashboard.widgets.wizard import WizardView
from dashboard.widgets.script_center import ScriptCenterView
from dashboard.widgets.stats_view import StatsView
from dashboard.widgets.env_editor import EnvEditorView


class TestDashboardApp(unittest.TestCase):
    def test_app_startup_and_tab_switching(self):
        async def _run():
            app = LiteratureClockDashboardApp()
            async with app.run_test() as pilot:
                self.assertEqual(app.title, "Irodalmi Óra & Naptár – Irányítópult")
                
                # Check tabs exist
                self.assertIsNotNone(app.query_one(WizardView))
                self.assertIsNotNone(app.query_one(ScriptCenterView))
                self.assertIsNotNone(app.query_one(StatsView))
                self.assertIsNotNone(app.query_one(EnvEditorView))

                # Switch to Scripts tab via keybinding F3
                await pilot.press("f3")
                self.assertEqual(app.query_one("#main-tabs").active, "tab-scripts")
                
                # Switch to Stats tab via F4
                await pilot.press("f4")
                self.assertEqual(app.query_one("#main-tabs").active, "tab-stats")

                # Switch to Settings tab via F5
                await pilot.press("f5")
                self.assertEqual(app.query_one("#main-tabs").active, "tab-env")

                # Switch back to Wizard tab via F2
                await pilot.press("f2")
                self.assertEqual(app.query_one("#main-tabs").active, "tab-wizard")

        asyncio.run(_run())
