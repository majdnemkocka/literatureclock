from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, RichLog, Static


class ProcessConsole(Vertical):
    """
    Console log viewer widget for real-time subprocess stdout/stderr streaming.
    """

    class StopRequested(Message):
        """Dispatched when the user clicks the Stop button."""
        pass

    class ClearRequested(Message):
        """Dispatched when the user clicks the Clear button."""
        pass

    def __init__(self, **kwargs):
        super().__init__(id="console-container", **kwargs)

    def compose(self) -> ComposeResult:
        with Horizontal(id="console-toolbar"):
            yield Static("📟 Élő Folyamatkonzol", id="console-title")
            yield Static("", id="console-timer")
            yield Button("⏹️ Leállítás (Ctrl+X)", id="btn-stop-process", variant="error")
            yield Button("🧹 Törlés", id="btn-clear-console", variant="default")
        
        yield RichLog(id="console-log", highlight=True, markup=True, wrap=True)

    def write_line(self, text: str, is_err: bool = False) -> None:
        log = self.query_one("#console-log", RichLog)
        if is_err:
            log.write(f"[bold red]{text}[/]")
        else:
            log.write(text)

    def write_info(self, text: str) -> None:
        log = self.query_one("#console-log", RichLog)
        log.write(f"[bold cyan]ℹ️  {text}[/]")

    def write_success(self, text: str) -> None:
        log = self.query_one("#console-log", RichLog)
        log.write(f"[bold green]✅ {text}[/]")

    def write_error(self, text: str) -> None:
        log = self.query_one("#console-log", RichLog)
        log.write(f"[bold red]❌ {text}[/]")

    def clear(self) -> None:
        log = self.query_one("#console-log", RichLog)
        log.clear()

    def update_timer(self, seconds: float) -> None:
        timer = self.query_one("#console-timer", Static)
        if seconds > 0:
            timer.update(f"⏱️ {seconds:.1f}s")
        else:
            timer.update("")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-stop-process":
            self.post_message(self.StopRequested())
        elif event.button.id == "btn-clear-console":
            self.clear()
            self.post_message(self.ClearRequested())
