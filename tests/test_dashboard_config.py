import os
import tempfile
import unittest
from pathlib import Path
import sys

# Ensure literatureclock root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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

        bool_false_param = StepParameter(
            name="visible",
            label="Látható böngésző",
            param_type="bool",
            default=False,
            value=False,
            flag_name="--visible",
            description="Böngésző megjelenítése"
        )
        self.assertEqual(bool_false_param.to_cli_args(), [])

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

        # Missing env
        ok2, msg2 = check_prerequisites(step, env={"DATABASE_URL": ""})
        self.assertFalse(ok2)
        self.assertIn("DATABASE_URL", msg2)
