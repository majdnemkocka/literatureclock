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
    config: Dict[str, str] = {}
    if target.exists():
        loaded = dotenv_values(target)
        for k, v in loaded.items():
            if v is not None:
                config[k] = str(v)
    # Merge with active os.environ for standard keys if unset in .env
    for key in ["DATABASE_URL", "GEMINI_API_KEY", "OPENAI_API_KEY", "AI_PROVIDER", "BUDGET_USD", "MODEL_NAME"]:
        if key not in config and os.environ.get(key):
            config[key] = os.environ[key]
    return config


def save_env_config(updates: Dict[str, str], env_path: Optional[Path] = None) -> None:
    target = env_path or get_default_env_path()
    current: Dict[str, str] = {}
    if target.exists():
        loaded = dotenv_values(target)
        for k, v in loaded.items():
            if v is not None:
                current[k] = str(v)
    
    for k, v in updates.items():
        if v is None or v == "":
            current.pop(k, None)
            if k in os.environ:
                del os.environ[k]
        else:
            current[k] = str(v)
            os.environ[k] = str(v)

    lines = []
    for k in sorted(current.keys()):
        val = current[k]
        lines.append(f"{k}={val}\n")

    with open(target, "w", encoding="utf-8") as f:
        f.writelines(lines)


def check_prerequisites(step: PipelineStep, env: Optional[Dict[str, str]] = None, base_dir: Optional[Path] = None) -> Tuple[bool, str]:
    active_env = env if env is not None else load_env_config()
    root = base_dir or REPO_ROOT

    # Check env requirements
    for env_var in step.required_env:
        val = active_env.get(env_var)
        if not val or not str(val).strip():
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
