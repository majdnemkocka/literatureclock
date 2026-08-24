import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import Footer, Header, TabbedContent, TabPane

from .config import load_env_config
from .models import Pipeline, PipelineStep, ScriptTask, StepStatus
from .pipelines import build_command_for_step, get_all_pipelines, get_all_script_tasks
from .runner import ProcessRunner
from .widgets import (
    AppHeader,
    EnvEditorView,
    ProcessConsole,
    ScriptCenterView,
    StatsView,
    WizardView,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class LiteratureClockDashboardApp(App):
    """
    Literature Clock & Calendar Interactive Textual Dashboard & Framework.
    """

    TITLE = "Irodalmi Óra & Naptár – Irányítópult"
    SUB_TITLE = "Literature Clock & Calendar Framework"
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("f1", "help", "Súgó", show=True),
        Binding("f2", "switch_tab('tab-wizard')", "🚀 Varázsló", show=True),
        Binding("f3", "switch_tab('tab-scripts')", "⚙️ Szkriptek", show=True),
        Binding("f4", "switch_tab('tab-stats')", "📊 Statisztika", show=True),
        Binding("f5", "switch_tab('tab-env')", "🛠️ Beállítások", show=True),
        Binding("ctrl+x", "stop_process", "⏹️ Leállítás", show=True),
        Binding("ctrl+q", "quit", "Kilépés", show=True),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.pipelines = get_all_pipelines()
        self.script_tasks = get_all_script_tasks()
        self.active_runner: Optional[ProcessRunner] = None
        self._timer_interval = None

    def compose(self) -> ComposeResult:
        yield AppHeader()
        
        with TabbedContent(id="main-tabs", initial="tab-wizard"):
            with TabPane("🚀 Vezetett Varázsló (Wizard)", id="tab-wizard"):
                yield WizardView(pipelines=self.pipelines)
            with TabPane("⚙️ Szkriptközpont (Scripts)", id="tab-scripts"):
                yield ScriptCenterView(tasks=self.script_tasks)
            with TabPane("📊 Statisztika & Grafikonok", id="tab-stats"):
                yield StatsView()
            with TabPane("🛠️ Beállítások (.env)", id="tab-env"):
                yield EnvEditorView()

        yield ProcessConsole()
        yield Footer()

    def action_switch_tab(self, tab_id: str) -> None:
        tabs = self.query_one("#main-tabs", TabbedContent)
        tabs.active = tab_id

    def action_help(self) -> None:
        console = self.query_one(ProcessConsole)
        console.write_info("--- SÚGÓ & GYORSBILLENTYŰK ---")
        console.write_line("[bold cyan]F2:[/] 🚀 Varázsló – lépésről lépésre végigvezet a teljes folyamaton")
        console.write_line("[bold cyan]F3:[/] ⚙️ Szkriptek – az összes egyedi modul közvetlen futtatása")
        console.write_line("[bold cyan]F4:[/] 📊 Statisztika – lefedettségi számok és böngészős HTML grafikonok")
        console.write_line("[bold cyan]F5:[/] 🛠️ Beállítások – PostgreSQL és AI kulcsok kezelése")
        console.write_line("[bold red]Ctrl+X:[/] ⏹️ Aktív folyamat azonnali leállítása")
        console.write_line("[bold red]Ctrl+Q:[/] 🚪 Kilépés a programból")
        console.write_info("---------------------------------")

    def action_stop_process(self) -> None:
        if self.active_runner and self.active_runner.is_running:
            console = self.query_one(ProcessConsole)
            console.write_info("Folyamat leállítási kérelem küldve...")
            asyncio.create_task(self.active_runner.stop())

    def on_wizard_view_run_step_requested(self, event: WizardView.RunStepRequested) -> None:
        cmd = build_command_for_step(event.step)
        cwd = REPO_ROOT / event.step.cwd if event.step.cwd else REPO_ROOT
        self._start_task(cmd=cmd, cwd=cwd, title=event.step.title, on_finish=lambda code: self._on_step_finished(event.step, code))

    def on_script_center_view_run_script_requested(self, event: ScriptCenterView.RunScriptRequested) -> None:
        cmd = list(event.task.command)
        for param in event.task.parameters:
            cmd.extend(param.to_cli_args())
        cwd = REPO_ROOT / event.task.cwd if event.task.cwd else REPO_ROOT
        self._start_task(cmd=cmd, cwd=cwd, title=event.task.title)

    def on_process_console_stop_requested(self, event: ProcessConsole.StopRequested) -> None:
        self.action_stop_process()

    def _start_task(self, cmd: list, cwd: Path, title: str, on_finish=None) -> None:
        if self.active_runner and self.active_runner.is_running:
            self.notify("Már fut egy folyamat! Állítsd le (Ctrl+X) az új indítása előtt.", severity="warning")
            return

        console = self.query_one(ProcessConsole)
        header = self.query_one(AppHeader)

        console.write_info(f"Futtatás indítása: {title}")
        console.write_line(f"[dim]Parancs: {' '.join(cmd)}[/]")
        console.write_line(f"[dim]Munkakönyvtár: {cwd}[/]")
        header.update_status("running")

        env = load_env_config()
        self.active_runner = ProcessRunner(
            command=cmd,
            cwd=cwd,
            env=env,
            on_line=lambda line, is_err: self.call_from_thread(console.write_line, line, is_err),
            on_status_change=lambda status: self.call_from_thread(header.update_status, status),
        )

        self.run_worker(self._execute_runner(self.active_runner, title, on_finish), exclusive=True)

    async def _execute_runner(self, runner: ProcessRunner, title: str, on_finish=None) -> None:
        console = self.query_one(ProcessConsole)
        header = self.query_one(AppHeader)

        # Start timer updater
        async def _timer_tick():
            while runner.is_running:
                console.update_timer(runner.elapsed_seconds)
                await asyncio.sleep(0.5)
            console.update_timer(runner.elapsed_seconds)

        timer_task = asyncio.create_task(_timer_tick())

        try:
            exit_code = await runner.run_async()
            if exit_code == 0:
                console.write_success(f"{title} sikeresen befejeződött ({runner.elapsed_seconds:.1f}s)")
                header.update_status("completed")
            elif runner._stopped_manually:
                console.write_info(f"{title} manuálisan leállítva ({runner.elapsed_seconds:.1f}s)")
                header.update_status("stopped")
            else:
                console.write_error(f"{title} hibával leállt (hibakód: {exit_code}, {runner.elapsed_seconds:.1f}s)")
                header.update_status("failed")

            if on_finish:
                on_finish(exit_code)
        finally:
            timer_task.cancel()
            self.active_runner = None

    def _on_step_finished(self, step: PipelineStep, exit_code: int) -> None:
        wizard = self.query_one(WizardView)
        if exit_code == 0:
            wizard.update_step_status(StepStatus.COMPLETED)
        else:
            wizard.update_step_status(StepStatus.FAILED)


def main():
    app = LiteratureClockDashboardApp()
    app.run()


if __name__ == "__main__":
    main()
