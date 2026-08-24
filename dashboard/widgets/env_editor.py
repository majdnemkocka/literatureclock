from typing import Dict
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, Label, Select, Static

from ..config import load_env_config, save_env_config


class EnvEditorView(Container):
    """
    Environment configuration (.env) editor and validator widget.
    """

    def __init__(self, **kwargs):
        super().__init__(id="env-editor-container", **kwargs)

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="env-editor-body"):
            yield Label("🛠️ Környezeti Változók és Beállítások (.env)", classes="col-header")
            yield Static("Itt állíthatod be a PostgreSQL adatbázis kapcsolatot és az AI API kulcsokat.", classes="step-detail-desc")

            with Vertical(id="env-fields-list"):
                with Horizontal(classes="env-field-row"):
                    yield Label("PostgreSQL Adatbázis (DATABASE_URL):", classes="env-label")
                    yield Input(id="env-input-DATABASE_URL", placeholder="postgresql://user:pass@host/db", password=True)

                with Horizontal(classes="env-field-row"):
                    yield Label("AI Szolgáltató (AI_PROVIDER):", classes="env-label")
                    yield Select([("Gemini API", "gemini"), ("OpenAI API", "openai"), ("Helyi LM Studio", "lmstudio")], value="gemini", id="env-select-AI_PROVIDER")

                with Horizontal(classes="env-field-row"):
                    yield Label("Gemini API Kulcs (GEMINI_API_KEY):", classes="env-label")
                    yield Input(id="env-input-GEMINI_API_KEY", placeholder="AIzaSy...", password=True)

                with Horizontal(classes="env-field-row"):
                    yield Label("OpenAI API Kulcs (OPENAI_API_KEY):", classes="env-label")
                    yield Input(id="env-input-OPENAI_API_KEY", placeholder="sk-...", password=True)

                with Horizontal(classes="env-field-row"):
                    yield Label("AI Költségkeret USD (BUDGET_USD):", classes="env-label")
                    yield Input(id="env-input-BUDGET_USD", placeholder="2.0")

                with Horizontal(classes="env-field-row"):
                    yield Label("Modell Név (MODEL_NAME / GEMINI_MODEL):", classes="env-label")
                    yield Input(id="env-input-MODEL_NAME", placeholder="gemini-2.0-flash")

            yield Static("", id="env-status-msg", classes="env-status-msg")

            with Horizontal(id="env-actions-bar"):
                yield Button("💾 Mentés .env fájlba", id="btn-save-env", variant="success")
                yield Button("🔌 Kapcsolatok Tesztelése", id="btn-test-env", variant="primary")
                yield Button("🔄 Visszaállítás", id="btn-reload-env", variant="default")

    def on_mount(self) -> None:
        self.reload_config()

    def reload_config(self) -> None:
        config = load_env_config()
        self.query_one("#env-input-DATABASE_URL", Input).value = config.get("DATABASE_URL", "")
        self.query_one("#env-input-GEMINI_API_KEY", Input).value = config.get("GEMINI_API_KEY", "")
        self.query_one("#env-input-OPENAI_API_KEY", Input).value = config.get("OPENAI_API_KEY", "")
        self.query_one("#env-input-BUDGET_USD", Input).value = config.get("BUDGET_USD", "2.0")
        self.query_one("#env-input-MODEL_NAME", Input).value = config.get("MODEL_NAME", config.get("GEMINI_MODEL", ""))

        provider = config.get("AI_PROVIDER", "gemini").lower()
        if provider in ["gemini", "openai", "lmstudio"]:
            self.query_one("#env-select-AI_PROVIDER", Select).value = provider

        status_msg = self.query_one("#env-status-msg", Static)
        status_msg.update("Konfiguráció betöltve a .env fájlból.")
        status_msg.remove_class("error", "success")

        model_val = self.query_one("#env-input-MODEL_NAME", Input).value.strip()
        updates = {
            "DATABASE_URL": self.query_one("#env-input-DATABASE_URL", Input).value.strip(),
            "AI_PROVIDER": str(self.query_one("#env-select-AI_PROVIDER", Select).value),
            "GEMINI_API_KEY": self.query_one("#env-input-GEMINI_API_KEY", Input).value.strip(),
            "OPENAI_API_KEY": self.query_one("#env-input-OPENAI_API_KEY", Input).value.strip(),
            "BUDGET_USD": self.query_one("#env-input-BUDGET_USD", Input).value.strip(),
            "MODEL_NAME": model_val,
            "GEMINI_MODEL": model_val,
        }
        save_env_config(updates)
        status_msg = self.query_one("#env-status-msg", Static)
        status_msg.update("✅ Beállítások sikeresen elmentve a .env fájlba!")
        status_msg.remove_class("error")
        status_msg.add_class("success")

    def test_connections(self) -> None:
        db_url = self.query_one("#env-input-DATABASE_URL", Input).value.strip()
        status_msg = self.query_one("#env-status-msg", Static)

        if not db_url:
            status_msg.update("⚠️ DATABASE_URL nincs megadva.")
            status_msg.remove_class("success")
            status_msg.add_class("error")
            return

        try:
            import psycopg2
            conn = psycopg2.connect(db_url, connect_timeout=3)
            conn.close()
            status_msg.update("✅ PostgreSQL adatbázis kapcsolat sikeres!")
            status_msg.remove_class("error")
            status_msg.add_class("success")
        except Exception as e:
            status_msg.update(f"❌ Adatbázis kapcsolódási hiba: {str(e)}")
            status_msg.remove_class("success")
            status_msg.add_class("error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save-env":
            self.save_config()
        elif event.button.id == "btn-test-env":
            self.test_connections()
        elif event.button.id == "btn-reload-env":
            self.reload_config()
