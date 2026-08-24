from datetime import datetime
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static


class AppHeader(Widget):
    """
    Top application banner with title, clock, and process status badge.
    """
    status_text = reactive("KÉSZENLÉT")
    status_class = reactive("status-idle")

    def compose(self) -> ComposeResult:
        with Horizontal(id="header-bar"):
            yield Static("📖 Literature Clock & Calendar", id="header-title")
            yield Static(id="header-clock")
            yield Static(f"[{self.status_text}]", id="header-status", classes=self.status_class)

    def on_mount(self) -> None:
        self._update_clock()
        self.set_interval(1.0, self._update_clock)

    def _update_clock(self) -> None:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        clock_widget = self.query_one("#header-clock", Static)
        clock_widget.update(f"🕒 {now_str}")

    def update_status(self, status: str) -> None:
        badge = self.query_one("#header-status", Static)
        badge.remove_class("status-idle", "status-running", "status-completed", "status-failed", "status-stopped")
        
        status_map = {
            "idle": ("KÉSZENLÉT", "status-idle"),
            "running": ("⚡ FOLYAMAT FUT", "status-running"),
            "completed": ("✅ SIKERES", "status-completed"),
            "failed": ("❌ HIBA", "status-failed"),
            "stopped": ("⏹️ MEGÁLLÍTVA", "status-stopped"),
        }
        text, cls = status_map.get(status.lower(), (status.upper(), "status-idle"))
        self.status_text = text
        self.status_class = cls
        badge.update(f"[{text}]")
        badge.add_class(cls)
