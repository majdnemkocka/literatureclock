from typing import Dict, List, Tuple
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, Label, Select, Static

from ..config import load_env_config, save_env_config
from ..models_fetcher import get_available_models_for_provider, DEFAULT_GEMINI_MODELS


class EnvEditorView(Container):
    """
    Environment configuration (.env) editor and validator widget with dynamic model listing.
    """

    def __init__(self, **kwargs):
        super().__init__(id="env-editor-container", **kwargs)
        self.available_models: List[Tuple[str, str]] = list(DEFAULT_GEMINI_MODELS)

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="env-editor-body"):
            yield Label("🛠️ Környezeti Változók és Beállítások (.env)", classes="col-header")
            yield Static("Itt állíthatod be a PostgreSQL adatbázis kapcsolatot, az AI szolgáltatót és a modellt.", classes="step-detail-desc")

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
                    yield Label("Értékelő Modell (generateContent szerint szűrve):", classes="env-label")
                    yield Select(self.available_models, value="gemini-2.5-flash", id="env-select-MODEL_NAME")
                    yield Button("🔄 API Modellek", id="btn-fetch-models", variant="default")

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

        provider = config.get("AI_PROVIDER", "gemini").lower()
        if provider in ["gemini", "openai", "lmstudio"]:
            self.query_one("#env-select-AI_PROVIDER", Select).value = provider

        target_model = config.get("GEMINI_MODEL") or config.get("MODEL_NAME") or "gemini-2.5-flash"
        self._refresh_model_options(provider, config.get("GEMINI_API_KEY", ""), target_model)

        status_msg = self.query_one("#env-status-msg", Static)
        status_msg.update("Konfiguráció betöltve a .env fájlból.")
        status_msg.remove_class("error", "success")

    def _refresh_model_options(self, provider: str, api_key: str, selected_value: Optional[str] = None) -> None:
        models = get_available_models_for_provider(provider, api_key=api_key)
        self.available_models = models
        
        sel = self.query_one("#env-select-MODEL_NAME", Select)
        options = [(label, val) for label, val in models]

        # If current selected value not in options, add it as custom entry
        model_ids = [val for _, val in models]
        active_val = selected_value or (sel.value if sel.value != Select.BLANK else "gemini-2.5-flash")
        if active_val and active_val not in model_ids:
            options.insert(0, (f"Egyedi: {active_val}", active_val))
            model_ids.insert(0, active_val)

        sel.set_options(options)
        if active_val in model_ids:
            sel.value = active_val
        elif options:
            sel.value = options[0][1]

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "env-select-AI_PROVIDER":
            provider = str(event.value)
            api_key = self.query_one("#env-input-GEMINI_API_KEY", Input).value.strip()
            self._refresh_model_options(provider, api_key)

    def save_config(self) -> None:
        model_sel = self.query_one("#env-select-MODEL_NAME", Select)
        model_val = str(model_sel.value) if model_sel.value != Select.BLANK else "gemini-2.5-flash"
        
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
        status_msg.update(f"✅ Beállítások sikeresen mentve! Aktív modell: {model_val}")
        status_msg.remove_class("error")
        status_msg.add_class("success")

    def fetch_live_models(self) -> None:
        provider = str(self.query_one("#env-select-AI_PROVIDER", Select).value)
        api_key = self.query_one("#env-input-GEMINI_API_KEY", Input).value.strip()
        status_msg = self.query_one("#env-status-msg", Static)
        status_msg.update("⏳ Modellek lekérése az API-tól és szűrése (supportedGenerationMethods)...")

        cur_val = self.query_one("#env-select-MODEL_NAME", Select).value
        target_val = str(cur_val) if cur_val != Select.BLANK else None
        self._refresh_model_options(provider, api_key, target_val)

        count = len(self.available_models)
        status_msg.update(f"✅ {count} szöveggeneráló modell lekérve és betöltve a listába!")
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
        elif event.button.id == "btn-fetch-models":
            self.fetch_live_models()
