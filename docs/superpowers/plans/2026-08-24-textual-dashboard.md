# Literature Clock Textual Dashboard & Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a comprehensive, interactive Textual-based Terminal User Interface (TUI) dashboard and pipeline framework that guides users step-by-step through scraping, extraction, database seeding, AI grading, statistics visualization, and web app launching.

**Architecture:** A modular Python package (`dashboard/`) built on `Textual` and `Rich`. It provides:
1. A reactive async process execution engine (`ProcessRunner`) that streams stdout/stderr without blocking the UI and supports graceful termination.
2. A declarative pipeline & step engine (`Pipeline`, `PipelineStep`, `StepParameter`) with pre-flight prerequisite validation and parameter schemas.
3. A rich multi-tab TUI interface featuring:
   - **Guided Wizard View:** Step-by-step guidance for the 4 primary workflows (Literature Clock, Literature Calendar, Offline Processing, Diagnostics).
   - **Script Center View:** Direct execution of individual scripts with configurable CLI flags and argument inputs.
   - **Live Process Console:** Real-time colored log output, status badges, execution timer, search filter, and process stop/kill controls.
   - **Stats & Visualization View:** Coverage and database metric cards, with one-click HTML chart generation and browser opening.
   - **Environment & Config View:** `.env` validation, connection tests, and in-TUI configuration editor.
4. Comprehensive automated unit and integration tests using `pytest` and Textual's test pilot.

**Tech Stack:** Python 3.10+, Textual (>=8.0.0), Rich (>=13.0.0), asyncio, pytest, psycopg2-binary, python-dotenv.

**Spec:** Guided workflow and script runner framework for Literature Clock as described in `literatureclock/readme.md` and user requirements.

## Global Constraints

- Must run smoothly on Windows (PowerShell/CMD) and POSIX terminals.
- Non-blocking async process execution using `asyncio.create_subprocess_exec` / Textual workers.
- Backwards compatible with existing scripts (`scrapers/mek_search/mek_time_search.py`, `extractor.py`, `seed_db.py`, `ai_grader.py`, `grading-app`, etc.) without breaking their CLI interfaces.
- TUI must use Hungarian as primary language (with clear bilingual tooltips/labels where standard).
- All changes must be fully tested with `pytest`.

---

### Task 1: Core Models and Environment Configuration Manager

**Files:**
- Create: `literatureclock/dashboard/__init__.py`
- Create: `literatureclock/dashboard/models.py`
- Create: `literatureclock/dashboard/config.py`
- Test: `literatureclock/tests/test_dashboard_config.py`

**Interfaces:**
- Consumes: `.env` file, environment variables.
- Produces:
  - `models.py`: `StepStatus`, `StepParameter`, `PipelineStep`, `Pipeline`, `ScriptTask`, `LogMessage`
  - `config.py`: `load_env_config() -> Dict[str, Any]`, `save_env_config(updates: Dict[str, str]) -> None`, `check_prerequisites(step: PipelineStep) -> Tuple[bool, str]`, `get_system_info() -> Dict[str, Any]`

- [ ] **Step 1: Write failing tests for models and config manager**

Create `literatureclock/tests/test_dashboard_config.py`:
```python
import os
import tempfile
import unittest
from pathlib import Path
from dashboard.models import StepStatus, StepParameter, PipelineStep, Pipeline
from dashboard.config import load_env_config, save_env_config, check_prerequisites, get_system_info


class TestDashboardConfigAndModels(unittest.TestCase):
    def test_step_parameter_defaults_and_formatting(self):
        param = StepParameter(
            name="limit",
            label="Keresési limit",
            param_type="int",
            default=50,
            value=50,
            flag_name="--limit",
            description="Találatok maximális száma"
        )
        self.assertEqual(param.to_cli_args(), ["--limit", "50"])

        bool_param = StepParameter(
            name="visible",
            label="Látható böngésző",
            param_type="bool",
            default=False,
            value=True,
            flag_name="--visible",
            description="Böngésző megjelenítése"
        )
        self.assertEqual(bool_param.to_cli_args(), ["--visible"])

    def test_env_config_load_and_save(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".env") as tmp:
            tmp.write("DATABASE_URL=postgresql://localhost/test\nBUDGET_USD=3.5\n")
            tmp_path = Path(tmp.name)

        try:
            config = load_env_config(env_path=tmp_path)
            self.assertEqual(config.get("DATABASE_URL"), "postgresql://localhost/test")
            self.assertEqual(config.get("BUDGET_USD"), "3.5")

            save_env_config({"BUDGET_USD": "5.0", "AI_PROVIDER": "gemini"}, env_path=tmp_path)
            updated = load_env_config(env_path=tmp_path)
            self.assertEqual(updated.get("BUDGET_USD"), "5.0")
            self.assertEqual(updated.get("AI_PROVIDER"), "gemini")
            self.assertEqual(updated.get("DATABASE_URL"), "postgresql://localhost/test")
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_check_prerequisites(self):
        # Step requiring existing file
        step = PipelineStep(
            id="seed",
            title="Adatbázis feltöltés",
            description="Feltöltés",
            command=["python", "seed_db.py"],
            required_files=["non_existent_file_12345.jsonl"],
            required_env=["DATABASE_URL"]
        )
        ok, msg = check_prerequisites(step, env={"DATABASE_URL": "postgresql://..."})
        self.assertFalse(ok)
        self.assertIn("non_existent_file_12345.jsonl", msg)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dashboard_config.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'dashboard')

- [ ] **Step 3: Implement `literatureclock/dashboard/__init__.py`, `models.py`, and `config.py`**

Create `literatureclock/dashboard/__init__.py`:
```python
"""
Literature Clock Dashboard & Workflow Automation Framework.
"""
__version__ = "0.1.0"
```

Create `literatureclock/dashboard/models.py`:
```python
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
```

Create `literatureclock/dashboard/config.py`:
```python
import os
import platform
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dotenv import dotenv_values
from .models import PipelineStep

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_default_env_path() -> Path:
    return REPO_ROOT / ".env"


def load_env_config(env_path: Optional[Path] = None) -> Dict[str, str]:
    target = env_path or get_default_env_path()
    config = {}
    if target.exists():
        loaded = dotenv_values(target)
        for k, v in loaded.items():
            if v is not None:
                config[k] = v
    # Merge with active os.environ for unset keys
    for key in ["DATABASE_URL", "GEMINI_API_KEY", "OPENAI_API_KEY", "AI_PROVIDER", "BUDGET_USD", "MODEL_NAME"]:
        if key not in config and os.environ.get(key):
            config[key] = os.environ[key]
    return config


def save_env_config(updates: Dict[str, str], env_path: Optional[Path] = None) -> None:
    target = env_path or get_default_env_path()
    current = {}
    if target.exists():
        current = dict(dotenv_values(target))
    
    for k, v in updates.items():
        if v is None or v == "":
            current.pop(k, None)
        else:
            current[k] = str(v)
            os.environ[k] = str(v)

    lines = []
    for k, v in sorted(current.items()):
        if v is not None:
            lines.append(f"{k}={v}\n")

    with open(target, "w", encoding="utf-8") as f:
        f.writelines(lines)


def check_prerequisites(step: PipelineStep, env: Optional[Dict[str, str]] = None, base_dir: Optional[Path] = None) -> Tuple[bool, str]:
    active_env = env if env is not None else load_env_config()
    root = base_dir or REPO_ROOT

    # Check env requirements
    for env_var in step.required_env:
        val = active_env.get(env_var) or os.environ.get(env_var)
        if not val or not val.strip():
            return False, f"Hiányzó környezeti változó: '{env_var}' (állítsd be a .env fájlban vagy a Beállítások fülön)"

    # Check file requirements
    for req_file in step.required_files:
        p = root / req_file if not Path(req_file).is_absolute() else Path(req_file)
        if not p.exists():
            return False, f"Hiányzó bemeneti fájl: '{req_file}' (futtasd az előző lépést)"

    return True, "Minden előfeltétel teljesült"


def get_system_info() -> Dict[str, Any]:
    return {
        "python_version": sys.version.split()[0],
        "os": f"{platform.system()} {platform.release()}",
        "repo_root": str(REPO_ROOT),
        "has_env": (REPO_ROOT / ".env").exists(),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dashboard_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add dashboard/__init__.py dashboard/models.py dashboard/config.py tests/test_dashboard_config.py
git commit -m "feat(dashboard): add core models and environment configuration manager"
```

---

### Task 2: Asynchronous Process Runner and Output Interceptor

**Files:**
- Create: `literatureclock/dashboard/runner.py`
- Test: `literatureclock/tests/test_dashboard_runner.py`

**Interfaces:**
- Consumes: `command: List[str]`, `cwd: Path`, `env: Dict[str, str]`, line callback functions.
- Produces: `ProcessRunner` class with `start()`, `stop()`, `is_running`, `elapsed_seconds`, `exit_code`, and async line generator / listener.

- [ ] **Step 1: Write failing tests for ProcessRunner**

Create `literatureclock/tests/test_dashboard_runner.py`:
```python
import asyncio
import sys
import unittest
from dashboard.runner import ProcessRunner


class TestProcessRunner(unittest.TestCase):
    def test_run_command_captures_output_and_exit_code(self):
        async def _run():
            lines = []
            runner = ProcessRunner(
                command=[sys.executable, "-c", "import sys; print('Hello Textual'); sys.stderr.write('Warning log\\n'); sys.exit(0)"],
                on_line=lambda line, is_err: lines.append((line, is_err))
            )
            code = await runner.run_async()
            self.assertEqual(code, 0)
            self.assertFalse(runner.is_running)
            text_outputs = [l[0] for l in lines]
            self.assertTrue(any("Hello Textual" in l for l in text_outputs))
            self.assertTrue(any("Warning log" in l for l in text_outputs))

        asyncio.run(_run())

    def test_stop_running_process(self):
        async def _run():
            runner = ProcessRunner(
                command=[sys.executable, "-c", "import time; time.sleep(10)"],
            )
            task = asyncio.create_task(runner.run_async())
            await asyncio.sleep(0.2)
            self.assertTrue(runner.is_running)
            await runner.stop()
            code = await task
            self.assertFalse(runner.is_running)
            self.assertIsNotNone(code)

        asyncio.run(_run())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dashboard_runner.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'dashboard.runner')

- [ ] **Step 3: Implement `literatureclock/dashboard/runner.py`**

Create `literatureclock/dashboard/runner.py`:
```python
import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional


class ProcessRunner:
    """
    Asynchronous process runner that executes commands, streams stdout and stderr
    line-by-line via callbacks, and allows clean cancellation.
    """

    def __init__(
        self,
        command: List[str],
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        on_line: Optional[Callable[[str, bool], None]] = None,
        on_status_change: Optional[Callable[[str], None]] = None,
    ):
        self.command = command
        self.cwd = cwd or Path.cwd()
        self.env = env
        self.on_line = on_line
        self.on_status_change = on_status_change
        
        self.process: Optional[asyncio.subprocess.Process] = None
        self.is_running = False
        self.exit_code: Optional[int] = None
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self._stopped_manually = False

    @property
    def elapsed_seconds(self) -> float:
        if self.start_time is None:
            return 0.0
        if self.end_time is not None:
            return self.end_time - self.start_time
        return time.time() - self.start_time

    async def run_async(self) -> int:
        self.is_running = True
        self._stopped_manually = False
        self.start_time = time.time()
        self.end_time = None
        self.exit_code = None

        if self.on_status_change:
            self.on_status_change("running")

        # Merge environment
        merged_env = os.environ.copy()
        # Ensure unbuffered python output
        merged_env["PYTHONUNBUFFERED"] = "1"
        if self.env:
            merged_env.update(self.env)

        try:
            self.process = await asyncio.create_subprocess_exec(
                *self.command,
                cwd=str(self.cwd),
                env=merged_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            async def _stream_reader(stream, is_err: bool):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    decoded = line.decode("utf-8", errors="replace").rstrip("\r\n")
                    if self.on_line:
                        self.on_line(decoded, is_err)

            await asyncio.gather(
                _stream_reader(self.process.stdout, False),
                _stream_reader(self.process.stderr, True),
            )

            self.exit_code = await self.process.wait()
        except asyncio.CancelledError:
            await self.stop()
            self.exit_code = -1
        except Exception as e:
            if self.on_line:
                self.on_line(f"Végrehajtási hiba: {str(e)}", True)
            self.exit_code = 1
        finally:
            self.end_time = time.time()
            self.is_running = False
            status = "completed" if self.exit_code == 0 else ("stopped" if self._stopped_manually else "failed")
            if self.on_status_change:
                self.on_status_change(status)

        return self.exit_code or 0

    async def stop(self) -> None:
        if self.process and self.is_running:
            self._stopped_manually = True
            try:
                self.process.terminate()
                # Wait up to 1.5 seconds for graceful shutdown
                for _ in range(15):
                    if self.process.returncode is not None:
                        break
                    await asyncio.sleep(0.1)
                if self.process.returncode is None:
                    self.process.kill()
            except ProcessLookupError:
                pass
            except Exception:
                pass
            self.is_running = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dashboard_runner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add dashboard/runner.py tests/test_dashboard_runner.py
git commit -m "feat(dashboard): add asynchronous process runner with output interceptor"
```

---

### Task 3: Pipeline and Script Task Definitions

**Files:**
- Create: `literatureclock/dashboard/pipelines.py`
- Test: `literatureclock/tests/test_dashboard_pipelines.py`

**Interfaces:**
- Consumes: `models.py`, `config.py`
- Produces: `get_all_pipelines() -> List[Pipeline]`, `get_all_script_tasks() -> List[ScriptTask]`, `build_command_for_step(step: PipelineStep) -> List[str]`

- [ ] **Step 1: Write failing tests for pipeline definitions**

Create `literatureclock/tests/test_dashboard_pipelines.py`:
```python
import sys
import unittest
from dashboard.pipelines import get_all_pipelines, get_all_script_tasks, build_command_for_step
from dashboard.models import StepParameter


class TestDashboardPipelines(unittest.TestCase):
    def test_pipelines_structure(self):
        pipelines = get_all_pipelines()
        self.assertGreaterEqual(len(pipelines), 3)
        ids = [p.id for p in pipelines]
        self.assertIn("clock", ids)
        self.assertIn("calendar", ids)
        self.assertIn("offline", ids)

        clock_pipeline = next(p for p in pipelines if p.id == "clock")
        step_ids = [s.id for s in clock_pipeline.steps]
        self.assertIn("search", step_ids)
        self.assertIn("seed", step_ids)
        self.assertIn("ai_grade", step_ids)

    def test_build_command_with_parameters(self):
        clock_pipeline = next(p for p in get_all_pipelines() if p.id == "clock")
        search_step = next(s for s in clock_pipeline.steps if s.id == "search")
        
        # Override limit parameter
        for p in search_step.parameters:
            if p.name == "limit":
                p.value = 250

        cmd = build_command_for_step(search_step)
        self.assertIn("scrapers/mek_search/mek_time_search.py", " ".join(cmd))
        self.assertIn("--limit", cmd)
        self.assertIn("250", cmd)

    def test_script_tasks_catalog(self):
        tasks = get_all_script_tasks()
        self.assertGreaterEqual(len(tasks), 8)
        categories = {t.category for t in tasks}
        self.assertIn("Keresés & Scraper", categories)
        self.assertIn("Adatbázis", categories)
        self.assertIn("AI Minőség", categories)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dashboard_pipelines.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'dashboard.pipelines')

- [ ] **Step 3: Implement `literatureclock/dashboard/pipelines.py`**

Create `literatureclock/dashboard/pipelines.py`:
```python
import sys
from pathlib import Path
from typing import List
from .models import Pipeline, PipelineStep, ScriptTask, StepParameter

REPO_ROOT = Path(__file__).resolve().parent.parent


def build_command_for_step(step: PipelineStep) -> List[str]:
    cmd = list(step.command)
    for param in step.parameters:
        cmd.extend(param.to_cli_args())
    return cmd


def get_all_pipelines() -> List[Pipeline]:
    py = sys.executable

    # 1. Literature Clock Pipeline (Időpont folyamat)
    clock_steps = [
        PipelineStep(
            id="search",
            title="1. Hibrid MEK Időpont Keresés",
            description="Kifejezések keresése a MEK-en, fejezetek letöltése, kerek bekezdések és LOD metaadatok kinyerése.",
            command=[py, "scrapers/mek_search/mek_time_search.py"],
            parameters=[
                StepParameter("limit", "Keresési limit (0 = mind)", "int", 50, 50, flag_name="--limit", description="Maximálisan keresendő kifejezések"),
                StepParameter("deep_extract", "Mélykeresés (fejezet letöltés)", "bool", True, True, flag_name="--deep-extract", description="Teljes fejezetek letöltése kerek bekezdésekért"),
                StepParameter("download_covers", "Borítóképek letöltése", "bool", False, False, flag_name="--download-covers", description="Könyvborítók mentése covers/ mappába"),
                StepParameter("visible", "Böngésző láthatóvá tétele", "bool", False, False, flag_name="--visible", description="Selenium böngészőablak megnyitása"),
            ],
            output_files=["scrapers/mek_search/mek_search_results.jsonl"],
        ),
        PipelineStep(
            id="seed",
            title="2. Adatbázis Inicializálás & Feltöltés",
            description="PostgreSQL 'entries' és 'votes' táblák létrehozása és a talált idézetek betöltése.",
            command=[py, "seed_db.py"],
            required_files=["scrapers/mek_search/mek_search_results.jsonl"],
            required_env=["DATABASE_URL"],
        ),
        PipelineStep(
            id="ai_grade",
            title="3. AI Minőségellenőrzés & Szűrés",
            description="LLM (Gemini / OpenAI / LM Studio) segítségével ellenőrzi az irodalmi minőséget és kontextust.",
            command=[py, "ai_grader.py"],
            required_env=["DATABASE_URL"],
            parameters=[
                StepParameter("budget", "Költségkeret (USD)", "str", "2.0", "2.0", description="Maximális költési keret USD-ben"),
                StepParameter("provider", "AI Szolgáltató", "choice", "gemini", "gemini", choices=["gemini", "openai", "lmstudio"], description="AI API szolgáltató"),
            ],
        ),
        PipelineStep(
            id="viz",
            title="4. Statisztikák és Diagramok Frissítése",
            description="Lefedettségi és minőségi diagramok generálása HTML formátumban.",
            command=[py, "db_stats_viz.py"],
            required_env=["DATABASE_URL"],
            output_files=["db_stats_chart.html"],
        ),
        PipelineStep(
            id="web_app",
            title="5. Grading App Webes Felület Indítása",
            description="SvelteKit webalkalmazás elindítása az idézetek böngészéséhez (http://localhost:5173).",
            command=["npm", "run", "dev"],
            cwd="grading-app",
            required_env=["DATABASE_URL"],
        ),
    ]

    # 2. Literature Calendar Pipeline (Naptári folyamat)
    calendar_steps = [
        PipelineStep(
            id="cal_search",
            title="1. MEK Naptári Dátum Keresés",
            description="Naptári kifejezések (hónap, nap) keresése a MEK-en LOD metaadatokkal.",
            command=[py, "scrapers/mek_search/mek_calendar_search.py"],
            parameters=[
                StepParameter("limit", "Keresési limit", "int", 50, 50, flag_name="--limit"),
                StepParameter("deep_extract", "Mélykeresés", "bool", True, True, flag_name="--deep-extract"),
            ],
            output_files=["scrapers/mek_search/mek_calendar_search_results.jsonl"],
        ),
        PipelineStep(
            id="cal_migrate",
            title="2. Naptár DB Migráció",
            description="Naptári táblák létrehozása az adatbázisban.",
            command=["node", "migrate_calendar.js"],
            cwd="grading-app",
            required_env=["DATABASE_URL"],
        ),
        PipelineStep(
            id="cal_seed",
            title="3. Naptár Adatbázis Feltöltés",
            description="Naptári találatok betöltése a táblákba.",
            command=[py, "seed_calendar_db.py"],
            required_files=["scrapers/mek_search/mek_calendar_search_results.jsonl"],
            required_env=["DATABASE_URL"],
        ),
        PipelineStep(
            id="cal_ai",
            title="4. Naptári AI Értékelés",
            description="Naptári idézetek automatikus AI osztályozása és pontozása.",
            command=[py, "calendar_ai_grader.py"],
            required_env=["DATABASE_URL"],
        ),
    ]

    # 3. Offline Books Pipeline (Könyvtár letöltés & feldolgozás)
    offline_steps = [
        PipelineStep(
            id="scrape_mek",
            title="1. MEK Könyvek Letöltése",
            description="Magyar szerzők műveinek tömeges letöltése HTML/TXT formátumban a mek_downloads/ mappába.",
            command=[py, "scrapers/mek_scraper.py"],
        ),
        PipelineStep(
            id="extract_hits",
            title="2. Időpontok Kinyerése Kötetekből",
            description="Szövegfeldolgozás és időpont-szabályok illesztése a letöltött kötetekre.",
            command=[py, "extractor.py", "mek_downloads/"],
            output_files=["hits.jsonl"],
        ),
        PipelineStep(
            id="stats_summary",
            title="3. Statisztikai Összesítés",
            description="Időbeli lefedettség és szabály-gyakoriság kimutatása.",
            command=[py, "stats.py"],
            required_files=["hits.jsonl"],
        ),
    ]

    # 4. Diagnostics & Tests (Tesztelés & Rendszer-ellenőrzés)
    diag_steps = [
        PipelineStep(
            id="run_tests",
            title="1. Projekt Egységtesztek Futtatása",
            description="Időpont-szabályok, LOD metaadatok és gyorsítótárazás ellenőrzése pytesttel.",
            command=[py, "-m", "pytest", "tests/test_rules_and_terms.py", "-v"],
        ),
        PipelineStep(
            id="dedup_check",
            title="2. MEK Duplikációk Szűrése",
            description="Keresési találatok és letöltések közötti átfedések elemzése.",
            command=[py, "deduplicate_mek.py"],
        ),
    ]

    return [
        Pipeline("clock", "Irodalmi Óra Folyamat (Literature Clock)", "Hibrid keresés, betöltés, AI pontozás és webes megjelenítés.", "🕒", clock_steps),
        Pipeline("calendar", "Irodalmi Naptár Folyamat (Literature Calendar)", "Éves naptári napok idézeteinek gyűjtése és feldolgozása.", "📅", calendar_steps),
        Pipeline("offline", "Offline Könyvtár & Batch Feldolgozás", "Teljes kötetek letöltése és offline időpont-kinyerés.", "📚", offline_steps),
        Pipeline("diagnostics", "Diagnosztika & Tesztek", "Rendszer-ellenőrzés, duplikáció-szűrés és egységtesztek.", "🧪", diag_steps),
    ]


def get_all_script_tasks() -> List[ScriptTask]:
    py = sys.executable
    return [
        ScriptTask(
            id="time_search",
            category="Keresés & Scraper",
            title="MEK Időpont Kereső (mek_time_search.py)",
            description="Időpont-kifejezések keresése a MEK-en mély fejezet-extrakcióval és LOD metaadatokkal.",
            command=[py, "scrapers/mek_search/mek_time_search.py"],
            parameters=[
                StepParameter("limit", "Limit", "int", 50, 50, flag_name="--limit"),
                StepParameter("term", "Egyedi kifejezés", "str", "", "", flag_name="--term"),
                StepParameter("deep_extract", "Mélykeresés", "bool", True, True, flag_name="--deep-extract"),
                StepParameter("download_covers", "Borítók letöltése", "bool", False, False, flag_name="--download-covers"),
                StepParameter("visible", "Látható böngésző", "bool", False, False, flag_name="--visible"),
            ],
        ),
        ScriptTask(
            id="calendar_search",
            category="Keresés & Scraper",
            title="MEK Naptár Kereső (mek_calendar_search.py)",
            description="Naptári dátumok keresése a MEK-en.",
            command=[py, "scrapers/mek_search/mek_calendar_search.py"],
            parameters=[
                StepParameter("limit", "Limit", "int", 50, 50, flag_name="--limit"),
                StepParameter("term", "Egyedi kifejezés", "str", "", "", flag_name="--term"),
                StepParameter("deep_extract", "Mélykeresés", "bool", True, True, flag_name="--deep-extract"),
            ],
        ),
        ScriptTask(
            id="mek_scraper",
            category="Keresés & Scraper",
            title="MEK Könyv Letöltő (mek_scraper.py)",
            description="Szerzők műveinek letöltése a MEK-ről a mek_downloads/ mappába.",
            command=[py, "scrapers/mek_scraper.py"],
        ),
        ScriptTask(
            id="dia_scraper",
            category="Keresés & Scraper",
            title="DIA Katalógus Scraper (dia_scraper.py)",
            description="Digitális Irodalmi Akadémia online műveinek feltérképezése.",
            command=[py, "scrapers/dia_scraper.py"],
        ),
        ScriptTask(
            id="extractor",
            category="Kinyerés & Elemzés",
            title="Időpont Extractor (extractor.py)",
            description="Időpontok kinyerése helyi HTML/TXT állományokból a rules.json5 szabályai alapján.",
            command=[py, "extractor.py", "mek_downloads/"],
        ),
        ScriptTask(
            id="deduplicate",
            category="Kinyerés & Elemzés",
            title="Duplikáció Szűrő (deduplicate_mek.py)",
            description="Találatok egyediségének vizsgálata és duplikációk kiszűrése.",
            command=[py, "deduplicate_mek.py"],
        ),
        ScriptTask(
            id="seed_db",
            category="Adatbázis",
            title="Adatbázis Seeder (seed_db.py)",
            description="PostgreSQL táblák inicializálása és adatok betöltése.",
            command=[py, "seed_db.py"],
            required_env=["DATABASE_URL"],
        ),
        ScriptTask(
            id="seed_calendar_db",
            category="Adatbázis",
            title="Naptár Adatbázis Seeder (seed_calendar_db.py)",
            description="Naptári adatok betöltése az adatbázisba.",
            command=[py, "seed_calendar_db.py"],
            required_env=["DATABASE_URL"],
        ),
        ScriptTask(
            id="ai_grader",
            category="AI Minőség",
            title="AI Időpont Értékelő (ai_grader.py)",
            description="LLM alapú minőségellenőrzés és pontozás.",
            command=[py, "ai_grader.py"],
            required_env=["DATABASE_URL"],
            parameters=[
                StepParameter("budget", "Költségkeret USD", "str", "2.0", "2.0"),
                StepParameter("provider", "AI Szolgáltató", "choice", "gemini", "gemini", choices=["gemini", "openai", "lmstudio"]),
            ],
        ),
        ScriptTask(
            id="calendar_ai_grader",
            category="AI Minőség",
            title="AI Naptár Értékelő (calendar_ai_grader.py)",
            description="LLM alapú naptári idézet ellenőrzés.",
            command=[py, "calendar_ai_grader.py"],
            required_env=["DATABASE_URL"],
        ),
        ScriptTask(
            id="stats",
            category="Statisztika & Vizualizáció",
            title="Lefedettség Statisztika (stats.py)",
            description="hits.jsonl fájl elemzése és lefedettségi mutatók kiírása.",
            command=[py, "stats.py"],
        ),
        ScriptTask(
            id="db_stats_viz",
            category="Statisztika & Vizualizáció",
            title="Adatbázis Diagram Készítő (db_stats_viz.py)",
            description="Interaktív db_stats_chart.html diagram generálása.",
            command=[py, "db_stats_viz.py"],
            required_env=["DATABASE_URL"],
        ),
        ScriptTask(
            id="ai_stats_viz",
            category="Statisztika & Vizualizáció",
            title="AI Statisztika Diagram (ai_stats_viz.py)",
            description="AI pontozási eloszlás vizualizáció készítése.",
            command=[py, "ai_stats_viz.py"],
            required_env=["DATABASE_URL"],
        ),
        ScriptTask(
            id="mek_stats_viz",
            category="Statisztika & Vizualizáció",
            title="MEK Scraper Diagram (mek_stats_viz.py)",
            description="MEK letöltési megoszlás diagram generálása.",
            command=[py, "mek_stats_viz.py"],
        ),
        ScriptTask(
            id="pytest_all",
            category="Tesztek & Karbantartás",
            title="Egységtesztek Futtatása (pytest)",
            description="Az összes egységteszt automatikus futtatása.",
            command=[py, "-m", "pytest", "tests/", "-v"],
        ),
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dashboard_pipelines.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add dashboard/pipelines.py tests/test_dashboard_pipelines.py
git commit -m "feat(dashboard): add pipeline workflows and script task definitions"
```

---

### Task 4: Textual UI Components and Widgets

**Files:**
- Create: `literatureclock/dashboard/widgets/__init__.py`
- Create: `literatureclock/dashboard/widgets/header.py`
- Create: `literatureclock/dashboard/widgets/console.py`
- Create: `literatureclock/dashboard/widgets/wizard.py`
- Create: `literatureclock/dashboard/widgets/script_center.py`
- Create: `literatureclock/dashboard/widgets/stats_view.py`
- Create: `literatureclock/dashboard/widgets/env_editor.py`
- Test: `literatureclock/tests/test_dashboard_widgets.py`

**Interfaces:**
- Consumes: Textual widgets (`Static`, `Button`, `RichLog`, `Input`, `Switch`, `Select`, `TabbedContent`, `ProgressBar`), `models.py`, `runner.py`, `config.py`
- Produces: Specialized modular Textual widgets:
  - `AppHeader`: Title, subtitle, clock, active task status badge.
  - `ProcessConsole`: Live streaming log view with Clear, Stop, Copy, Autoscroll toggles.
  - `WizardView`: Step-by-step pipeline view with visual status checklist, parameter inputs, prerequisite warnings, "Lépés indítása" button, "Következő" / "Előző" navigation.
  - `ScriptCenterView`: Categorized searchable list of scripts with inline parameter editors and direct run buttons.
  - `StatsView`: Metric overview tiles (hits, database coverage, AI checked) with quick-action buttons to open HTML charts in browser.
  - `EnvEditorView`: Interactive `.env` key-value viewer and editor with connection check helper.

- [ ] **Step 1: Write failing tests for widget instantiation and layout**

Create `literatureclock/tests/test_dashboard_widgets.py`:
```python
import unittest
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

        import asyncio
        asyncio.run(_run())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dashboard_widgets.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'dashboard.widgets')

- [ ] **Step 3: Implement `literatureclock/dashboard/widgets/` modules**

Implement `widgets/__init__.py`, `widgets/header.py`, `widgets/console.py`, `widgets/wizard.py`, `widgets/script_center.py`, `widgets/stats_view.py`, and `widgets/env_editor.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dashboard_widgets.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add dashboard/widgets/ tests/test_dashboard_widgets.py
git commit -m "feat(dashboard): create Textual TUI widgets for wizard, console, scripts, stats, and env"
```

---

### Task 5: Main Application Assembly, CSS Styling, and Entry Points

**Files:**
- Create: `literatureclock/dashboard/styles.tcss`
- Create: `literatureclock/dashboard/app.py`
- Create: `literatureclock/dashboard_app.py`
- Modify: `literatureclock/requirements.txt`
- Modify: `literatureclock/readme.md`
- Test: `literatureclock/tests/test_dashboard_app.py`

**Interfaces:**
- Consumes: All `dashboard/` widgets, runner, pipelines, config.
- Produces:
  - `LiteratureClockDashboardApp` class.
  - CLI entry point `dashboard_app.py`.
  - Keyboard shortcuts (`F1` Help modal, `F2` Wizard tab, `F3` Scripts tab, `F4` Stats tab, `F5` Settings tab, `Ctrl+X` Stop process, `Ctrl+Q` Quit).

- [ ] **Step 1: Write integration tests for main application flow**

Create `literatureclock/tests/test_dashboard_app.py`:
```python
import unittest
from dashboard.app import LiteratureClockDashboardApp


class TestDashboardApp(unittest.TestCase):
    def test_app_startup_and_tab_switching(self):
        async def _run():
            app = LiteratureClockDashboardApp()
            async with app.run_test() as pilot:
                # App title and components exist
                self.assertEqual(app.title, "Irodalmi Óra & Naptár – Irányítópult")
                
                # Switch to Scripts tab via keybinding F3
                await pilot.press("f3")
                self.assertEqual(app.query_one("#main-tabs").active, "tab-scripts")
                
                # Switch to Stats tab via F4
                await pilot.press("f4")
                self.assertEqual(app.query_one("#main-tabs").active, "tab-stats")

                # Switch to Settings tab via F5
                await pilot.press("f5")
                self.assertEqual(app.query_one("#main-tabs").active, "tab-env")

                # Switch back to Wizard tab via F2
                await pilot.press("f2")
                self.assertEqual(app.query_one("#main-tabs").active, "tab-wizard")

        import asyncio
        asyncio.run(_run())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dashboard_app.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'dashboard.app')

- [ ] **Step 3: Implement `styles.tcss`, `app.py`, `dashboard_app.py`, and update `requirements.txt` / `readme.md`**

Create `literatureclock/dashboard/styles.tcss` with clean layout and modern dark palette.
Create `literatureclock/dashboard/app.py` connecting the runner to the console, wizard, script center, stats, and settings.
Create `literatureclock/dashboard_app.py` as executable entry point:
```python
#!/usr/bin/env python3
"""
Literature Clock TUI Dashboard
Indítás: python dashboard_app.py
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.app import LiteratureClockDashboardApp

if __name__ == "__main__":
    app = LiteratureClockDashboardApp()
    app.run()
```
Add `textual>=8.0.0` to `requirements.txt`.
Update `readme.md` with instructions on using `python dashboard_app.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dashboard_app.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add dashboard/ dashboard_app.py requirements.txt readme.md tests/test_dashboard_app.py
git commit -m "feat(dashboard): assemble full Textual dashboard application and CLI entrypoint"
```

---

## Verification Plan

### Automated Tests
- `pytest tests/test_dashboard_config.py -v` (Tests models, configuration loading/saving, and prerequisite validation)
- `pytest tests/test_dashboard_runner.py -v` (Tests async subprocess spawning, real-time line streaming, exit codes, and process cancellation)
- `pytest tests/test_dashboard_pipelines.py -v` (Tests pipeline step definitions, parameters, and CLI argument generation)
- `pytest tests/test_dashboard_widgets.py -v` (Tests Textual widget creation and rendering)
- `pytest tests/test_dashboard_app.py -v` (Tests Textual App lifecycle, tab switching, and keyboard navigation)
- `pytest tests/ -v` (Full project test suite)

### Manual Verification
1. Launch dashboard in terminal: `python dashboard_app.py`
2. Test Guided Wizard:
   - Select "Irodalmi Óra Folyamat"
   - Inspect step 1 parameters (limit, deep extract)
   - Run step 1 or diagnostics step (Egységtesztek) and observe live console output streaming with timestamps and progress
   - Verify process stop button (`Ctrl+X`) terminates running task cleanly
3. Test Script Center:
   - Browse scripts by category
   - Trigger a fast script (e.g. `stats.py` or `deduplicate_mek.py`)
   - Check real-time log output and exit code badge
4. Test Stats & Charts:
   - View summary metrics (hits, cache status, DB status)
   - Click "Diagram megnyitása" to test browser opening
5. Test Environment Editor:
   - View configured `.env` keys and verify editing works
