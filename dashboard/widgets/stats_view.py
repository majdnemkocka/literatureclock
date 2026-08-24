import os
import webbrowser
from pathlib import Path
from textual.app import ComposeResult
from textual.containers import Container, Grid, Horizontal, Vertical
from textual.widgets import Button, Label, Static

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class StatsView(Container):
    """
    Statistics and Visualizations Dashboard View.
    """

    def __init__(self, **kwargs):
        super().__init__(id="stats-container", **kwargs)

    def compose(self) -> ComposeResult:
        with Vertical(id="stats-body"):
            yield Label("📊 Adatbázis és Lefedettségi Statisztikák", classes="col-header")

            with Grid(id="stats-cards-grid"):
                with Vertical(classes="stats-card"):
                    yield Label("🕒 MEK Időpont Találatok", classes="card-title")
                    yield Static("Betöltés...", id="stat-mek-hits", classes="card-value")
                    yield Static("", id="stat-mek-size", classes="card-subtext")

                with Vertical(classes="stats-card"):
                    yield Label("📅 MEK Naptár Találatok", classes="card-title")
                    yield Static("Betöltés...", id="stat-cal-hits", classes="card-value")
                    yield Static("", id="stat-cal-size", classes="card-subtext")

                with Vertical(classes="stats-card"):
                    yield Label("📚 Offline Idézetek (hits.jsonl)", classes="card-title")
                    yield Static("Betöltés...", id="stat-offline-hits", classes="card-value")
                    yield Static("", id="stat-offline-size", classes="card-subtext")

                with Vertical(classes="stats-card"):
                    yield Label("⚡ Gyorsítótár (Cache)", classes="card-title")
                    yield Static("Betöltés...", id="stat-cache-count", classes="card-value")
                    yield Static("", id="stat-cache-size", classes="card-subtext")

            with Horizontal(id="stats-actions-bar"):
                yield Button("🕒 Óra Diagram (db_stats_chart.html)", id="btn-open-db-chart", variant="primary")
                yield Button("📅 Naptár Diagram (db_calendar_stats_chart.html)", id="btn-open-cal-chart", variant="default")
                yield Button("🤖 AI Értékelés Diagram (ai_stats_chart.html)", id="btn-open-ai-chart", variant="default")
                yield Button("🏛️ MEK Letöltési Diagram (mek_stats_chart.html)", id="btn-open-mek-chart", variant="default")
                yield Button("🔄 Frissítés", id="btn-refresh-stats", variant="success")

    def on_mount(self) -> None:
        self.refresh_stats()

    def refresh_stats(self) -> None:
        # MEK Time search results (check new name first, fallback to legacy)
        mek_time_file = REPO_ROOT / "scrapers" / "mek_search" / "mek_time_search_results.jsonl"
        if not mek_time_file.exists():
            mek_time_file = REPO_ROOT / "scrapers" / "mek_search" / "mek_search_results.jsonl"
        self._update_file_stat("#stat-mek-hits", "#stat-mek-size", mek_time_file)

        # MEK Calendar search results
        mek_cal_file = REPO_ROOT / "scrapers" / "mek_search" / "mek_calendar_search_results.jsonl"
        self._update_file_stat("#stat-cal-hits", "#stat-cal-size", mek_cal_file)

        # Offline hits
        offline_file = REPO_ROOT / "hits.jsonl"
        self._update_file_stat("#stat-offline-hits", "#stat-offline-size", offline_file)

        # Cache folder
        cache_dir = REPO_ROOT / "scrapers" / "mek_search" / "cache"
        if cache_dir.exists():
            files = list(cache_dir.glob("**/*"))
            file_count = len([f for f in files if f.is_file()])
            total_size = sum(f.stat().st_size for f in files if f.is_file()) / (1024 * 1024)
            self.query_one("#stat-cache-count", Static).update(f"{file_count} fájl")
            self.query_one("#stat-cache-size", Static).update(f"{total_size:.2f} MB gyorsítótárban")
        else:
            self.query_one("#stat-cache-count", Static).update("0 fájl")
            self.query_one("#stat-cache-size", Static).update("Még nincs gyorsítótár")

    def _update_file_stat(self, hits_id: str, size_id: str, path: Path) -> None:
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            line_count = 0
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for _ in f:
                    line_count += 1
            self.query_one(hits_id, Static).update(f"{line_count:,} találat")
            self.query_one(size_id, Static).update(f"{size_mb:.2f} MB ({path.name})")
        else:
            self.query_one(hits_id, Static).update("Nincs adat")
            self.query_one(size_id, Static).update(f"Fájl nem található: {path.name}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-refresh-stats":
            self.refresh_stats()
        elif bid == "btn-open-db-chart":
            chart = REPO_ROOT / "db_stats_chart.html"
            if chart.exists():
                webbrowser.open(chart.as_uri())
        elif bid == "btn-open-cal-chart":
            chart = REPO_ROOT / "db_calendar_stats_chart.html"
            if chart.exists():
                webbrowser.open(chart.as_uri())
        elif bid == "btn-open-ai-chart":
            chart = REPO_ROOT / "ai_stats_chart.html"
            if chart.exists():
                webbrowser.open(chart.as_uri())
        elif bid == "btn-open-mek-chart":
            chart = REPO_ROOT / "mek_stats_chart.html"
            if chart.exists():
                webbrowser.open(chart.as_uri())
