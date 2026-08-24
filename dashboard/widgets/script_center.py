from typing import List, Optional
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Button, Input, Label, OptionList, Select, Static, Switch
from textual.widgets.option_list import Option

from ..models import ScriptTask, StepParameter
from ..pipelines import get_all_script_tasks


class ScriptCenterView(Container):
    """
    Central Script Runner allowing direct execution of any tool in the repo.
    """

    class RunScriptRequested(Message):
        def __init__(self, task: ScriptTask):
            super().__init__()
            self.task = task

    def __init__(self, tasks: Optional[List[ScriptTask]] = None, **kwargs):
        super().__init__(id="script-center-container", **kwargs)
        self.tasks = tasks or get_all_script_tasks()
        self.active_task_idx = 0

    @property
    def current_task(self) -> ScriptTask:
        return self.tasks[self.active_task_idx]

    def compose(self) -> ComposeResult:
        with Horizontal(id="script-center-body"):
            with Vertical(id="script-list-col"):
                yield Label("📂 Szkript Katalógus", classes="col-header")
                yield OptionList(id="script-option-list")

            with VerticalScroll(id="script-detail-col"):
                yield Static(id="script-detail-title", classes="step-detail-title")
                yield Static(id="script-detail-category", classes="script-category-badge")
                yield Static(id="script-detail-desc", classes="step-detail-desc")
                
                yield Vertical(id="script-params-container")

                with Horizontal(id="script-action-bar"):
                    yield Button("▶️ Szkript Futtatása", id="btn-run-script", variant="success")

    def on_mount(self) -> None:
        self._refresh_list()
        self._refresh_details()

    def _refresh_list(self) -> None:
        opt_list = self.query_one("#script-option-list", OptionList)
        opt_list.clear_options()
        for t in self.tasks:
            opt_list.add_option(Option(f"[{t.category}] {t.title}", id=t.id))
        opt_list.highlighted = self.active_task_idx

    def _refresh_details(self) -> None:
        t = self.current_task
        self.query_one("#script-detail-title", Static).update(f"{t.title}")
        self.query_one("#script-detail-category", Static).update(f"🏷️ Kategória: {t.category}")
        self.query_one("#script-detail-desc", Static).update(f"{t.description}")

        params_col = self.query_one("#script-params-container", Vertical)
        params_col.remove_children()

        if t.parameters:
            params_col.mount(Label("⚙️ Paraméterek & Kapcsolók:", classes="params-header"))
            for param in t.parameters:
                label_widget = Label(f"{param.label}:", classes="param-label")
                if param.param_type == "bool":
                    input_widget = Switch(value=bool(param.value), id=f"sparam-{param.name}")
                elif param.param_type == "choice" and param.choices:
                    options = [(c, c) for c in param.choices]
                    input_widget = Select(options, value=param.value, id=f"sparam-{param.name}")
                else:
                    input_widget = Input(value=str(param.value if param.value is not None else ""), id=f"sparam-{param.name}")
                row = Horizontal(label_widget, input_widget, classes="param-row")
                params_col.mount(row)

    def _collect_parameters(self) -> None:
        t = self.current_task
        for param in t.parameters:
            try:
                if param.param_type == "bool":
                    switch = self.query_one(f"#sparam-{param.name}", Switch)
                    param.value = switch.value
                elif param.param_type == "choice":
                    sel = self.query_one(f"#sparam-{param.name}", Select)
                    param.value = sel.value
                elif param.param_type == "int":
                    inp = self.query_one(f"#sparam-{param.name}", Input)
                    param.value = int(inp.value.strip()) if inp.value.strip().isdigit() else param.default
                else:
                    inp = self.query_one(f"#sparam-{param.name}", Input)
                    param.value = inp.value.strip()
            except Exception:
                pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-run-script":
            self._collect_parameters()
            self.post_message(self.RunScriptRequested(self.current_task))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        idx = event.option_index
        if 0 <= idx < len(self.tasks):
            self.active_task_idx = idx
            self._refresh_details()
