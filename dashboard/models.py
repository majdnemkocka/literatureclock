from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepParameter:
    name: str
    label: str
    param_type: str  # "int", "str", "bool", "choice"
    default: Any
    value: Any
    flag_name: Optional[str] = None
    choices: Optional[List[str]] = None
    description: str = ""

    def to_cli_args(self) -> List[str]:
        if self.param_type == "bool":
            if self.value and self.flag_name:
                return [self.flag_name]
            return []
        if self.flag_name and self.value is not None:
            if str(self.value).strip() != "":
                return [self.flag_name, str(self.value)]
        return []


@dataclass
class PipelineStep:
    id: str
    title: str
    description: str
    command: List[str]
    cwd: Optional[str] = None
    parameters: List[StepParameter] = field(default_factory=list)
    required_files: List[str] = field(default_factory=list)
    required_env: List[str] = field(default_factory=list)
    output_files: List[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    exit_code: Optional[int] = None
    duration_seconds: float = 0.0
    error_message: Optional[str] = None


@dataclass
class Pipeline:
    id: str
    title: str
    description: str
    icon: str
    steps: List[PipelineStep] = field(default_factory=list)
    current_step_index: int = 0


@dataclass
class ScriptTask:
    id: str
    category: str
    title: str
    description: str
    command: List[str]
    cwd: Optional[str] = None
    parameters: List[StepParameter] = field(default_factory=list)
    required_env: List[str] = field(default_factory=list)
