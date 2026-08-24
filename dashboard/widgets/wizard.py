from typing import List, Optional
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Button, Input, Label, OptionList, Select, Static, Switch
from textual.widgets.option_list import Option

from ..config import check_prerequisites
from ..models import Pipeline, PipelineStep, StepParameter, StepStatus


class WizardView(Container):
    """
    Step-by-step Guided Pipeline Runner for Literature Clock workflows.
    """

    class RunStepRequested(Message):
        def __init__(self, pipeline: Pipeline, step: PipelineStep):
            super().__init__()
            self.pipeline = pipeline
            self.step = step

    class StepChanged(Message):
        def __init__(self, pipeline: Pipeline, step_index: int):
            super().__init__()
            self.pipeline = pipeline
            self.step_index = step_index

    class SkipStepRequested(Message):
        def __init__(self, pipeline: Pipeline, step: PipelineStep):
            super().__init__()
            self.pipeline = pipeline
            self.step = step

    def __init__(self, pipelines: List[Pipeline], **kwargs):
        super().__init__(id="wizard-container", **kwargs)
        self.pipelines = pipelines
        self.active_pipeline_idx = 0

    @property
    def current_pipeline(self) -> Pipeline:
        return self.pipelines[self.active_pipeline_idx]

    @property
    def current_step(self) -> PipelineStep:
        idx = self.current_pipeline.current_step_index
        return self.current_pipeline.steps[idx]

    def compose(self) -> ComposeResult:
        with Horizontal(id="wizard-pipeline-selector"):
            for i, pipe in enumerate(self.pipelines):
                variant = "primary" if i == 0 else "default"
                yield Button(f"{pipe.icon} {pipe.title}", id=f"pipe-btn-{pipe.id}", variant=variant, classes="pipeline-tab-btn")

        with Horizontal(id="wizard-body"):
            with Vertical(id="wizard-step-list-col"):
                yield Label("📌 Folyamat Lépései", classes="col-header")
                yield OptionList(id="wizard-steps-option-list")

            with VerticalScroll(id="wizard-step-detail-col"):
                yield Static(id="wizard-step-title", classes="step-detail-title")
                yield Static(id="wizard-step-desc", classes="step-detail-desc")
                yield Static(id="wizard-prereq-badge", classes="prereq-badge")
                
                yield Vertical(id="wizard-params-container")

                with Horizontal(id="wizard-action-bar"):
                    yield Button("▶️ Lépés Indítása", id="btn-run-step", variant="success")
                    yield Button("⏭️ Átugrás", id="btn-skip-step", variant="warning")
                    yield Button("⬅️ Előző", id="btn-prev-step", variant="default")
                    yield Button("➡️ Következő", id="btn-next-step", variant="default")

    def on_mount(self) -> None:
        self._refresh_step_list()
        self._refresh_step_details()

    def select_pipeline(self, pipeline_id: str) -> None:
        for idx, p in enumerate(self.pipelines):
            if p.id == pipeline_id:
                self.active_pipeline_idx = idx
                break
        for p in self.pipelines:
            btn = self.query_one(f"#pipe-btn-{p.id}", Button)
            if p.id == self.current_pipeline.id:
                btn.variant = "primary"
            else:
                btn.variant = "default"
        self._refresh_step_list()
        self._refresh_step_details()

    def _get_status_icon(self, status: StepStatus) -> str:
        icons = {
            StepStatus.PENDING: "⏳",
            StepStatus.RUNNING: "⚡",
            StepStatus.COMPLETED: "✅",
            StepStatus.FAILED: "❌",
            StepStatus.SKIPPED: "⏭️",
        }
        return icons.get(status, "⚪")

    def _refresh_step_list(self) -> None:
        opt_list = self.query_one("#wizard-steps-option-list", OptionList)
        opt_list.clear_options()
        for idx, step in enumerate(self.current_pipeline.steps):
            icon = self._get_status_icon(step.status)
            opt_list.add_option(Option(f"{icon} {step.title}", id=step.id))
        opt_list.highlighted = self.current_pipeline.current_step_index

    def _refresh_step_details(self) -> None:
        step = self.current_step
        self.query_one("#wizard-step-title", Static).update(f"{step.title}")
        self.query_one("#wizard-step-desc", Static).update(f"{step.description}")

        # Check prerequisites
        ok, msg = check_prerequisites(step)
        prereq = self.query_one("#wizard-prereq-badge", Static)
        if ok:
            prereq.update("✅ Minden előfeltétel teljesült")
            prereq.remove_class("prereq-warning")
            prereq.add_class("prereq-ok")
        else:
            prereq.update(f"⚠️ {msg}")
            prereq.remove_class("prereq-ok")
            prereq.add_class("prereq-warning")

        # Build parameters UI dynamically
        params_col = self.query_one("#wizard-params-container", Vertical)
        params_col.remove_children()

        if step.parameters:
            params_col.mount(Label("⚙️ Lépés Paraméterei:", classes="params-header"))
            for param in step.parameters:
                label_widget = Label(f"{param.label}:", classes="param-label")
                if param.param_type == "bool":
                    input_widget = Switch(value=bool(param.value), id=f"param-{param.name}")
                elif param.param_type == "choice" and param.choices:
                    options = [(c, c) for c in param.choices]
                    input_widget = Select(options, value=param.value, id=f"param-{param.name}")
                else:
                    input_widget = Input(value=str(param.value if param.value is not None else ""), id=f"param-{param.name}")
                row = Horizontal(label_widget, input_widget, classes="param-row")
                params_col.mount(row)

    def _collect_parameters(self) -> None:
        step = self.current_step
        for param in step.parameters:
            try:
                if param.param_type == "bool":
                    switch = self.query_one(f"#param-{param.name}", Switch)
                    param.value = switch.value
                elif param.param_type == "choice":
                    sel = self.query_one(f"#param-{param.name}", Select)
                    param.value = sel.value
                elif param.param_type == "int":
                    inp = self.query_one(f"#param-{param.name}", Input)
                    param.value = int(inp.value.strip()) if inp.value.strip().isdigit() else param.default
                else:
                    inp = self.query_one(f"#param-{param.name}", Input)
                    param.value = inp.value.strip()
            except Exception:
                pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid.startswith("pipe-btn-"):
            pipe_id = bid.replace("pipe-btn-", "")
            self.select_pipeline(pipe_id)
        elif bid == "btn-run-step":
            self._collect_parameters()
            self.post_message(self.RunStepRequested(self.current_pipeline, self.current_step))
        elif bid == "btn-skip-step":
            self.current_step.status = StepStatus.SKIPPED
            self._advance_step()
        elif bid == "btn-next-step":
            self._advance_step()
        elif bid == "btn-prev-step":
            if self.current_pipeline.current_step_index > 0:
                self.current_pipeline.current_step_index -= 1
                self._refresh_step_list()
                self._refresh_step_details()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        idx = event.option_index
        if 0 <= idx < len(self.current_pipeline.steps):
            self.current_pipeline.current_step_index = idx
            self._refresh_step_details()

    def _advance_step(self) -> None:
        if self.current_pipeline.current_step_index < len(self.current_pipeline.steps) - 1:
            self.current_pipeline.current_step_index += 1
        self._refresh_step_list()
        self._refresh_step_details()

    def update_step_status(self, status: StepStatus) -> None:
        self.current_step.status = status
        self._refresh_step_list()
        self._refresh_step_details()
