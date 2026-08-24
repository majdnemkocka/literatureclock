import asyncio
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from textual.app import App, ComposeResult
from dashboard.widgets.header import AppHeader
from dashboard.widgets.console import ProcessConsole
from dashboard.widgets.wizard import WizardView
from dashboard.widgets.script_center import ScriptCenterView
from dashboard.widgets.stats_view import StatsView
from dashboard.widgets.env_editor import EnvEditorView
from dashboard.pipelines import get_all_pipelines


class WidgetTestApp(App):
    def compose(self) -> ComposeResult:
        yield AppHeader()
        yield ProcessConsole()
        yield WizardView(pipelines=get_all_pipelines())
        yield ScriptCenterView()
        yield StatsView()
        yield EnvEditorView()


class TestDashboardWidgets(unittest.TestCase):
    def test_widgets_compose_without_error(self):
        async def _run():
            app = WidgetTestApp()
            async with app.run_test() as pilot:
                self.assertIsNotNone(app.query_one(AppHeader))
                self.assertIsNotNone(app.query_one(ProcessConsole))
                self.assertIsNotNone(app.query_one(WizardView))
                self.assertIsNotNone(app.query_one(ScriptCenterView))
                self.assertIsNotNone(app.query_one(StatsView))
                self.assertIsNotNone(app.query_one(EnvEditorView))

        asyncio.run(_run())
