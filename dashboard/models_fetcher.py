import os
import re
from typing import List, Optional, Tuple
import requests

DEFAULT_GEMINI_MODELS: List[Tuple[str, str]] = [
    ("gemini-3.7-flash (Gemini 3.7 Flash - Legújabb)", "gemini-3.7-flash"),
    ("gemini-3.6-flash (Gemini 3.6 Flash)", "gemini-3.6-flash"),
    ("gemini-3.5-flash (Gemini 3.5 Flash)", "gemini-3.5-flash"),
    ("gemini-3.1-pro-preview (Gemini 3.1 Pro Preview)", "gemini-3.1-pro-preview"),
    ("gemini-2.5-flash (Gemini 2.5 Flash - Stabil)", "gemini-2.5-flash"),
    ("gemini-2.5-pro (Gemini 2.5 Pro - Magas minőség)", "gemini-2.5-pro"),
    ("gemini-flash-latest (Gemini Flash Latest)", "gemini-flash-latest"),
    ("gemini-pro-latest (Gemini Pro Latest)", "gemini-pro-latest"),
    ("gemini-2.0-flash (Gemini 2.0 Flash)", "gemini-2.0-flash"),
]

DEFAULT_OPENAI_MODELS: List[Tuple[str, str]] = [
    ("gpt-4o-mini (Gyors, költséghatékony)", "gpt-4o-mini"),
    ("gpt-4o (Csúcsmodell)", "gpt-4o"),
    ("o3-mini (Reasoning modell)", "o3-mini"),
    ("gpt-4.5-preview (Legújabb GPT-4.5)", "gpt-4.5-preview"),
]


def fetch_gemini_models(api_key: Optional[str] = None) -> List[Tuple[str, str]]:
    """
    Queries Google Gemini API endpoint:
    GET https://generativelanguage.googleapis.com/v1beta/models?key={api_key}
    
    Filters models strictly by supportedGenerationMethods containing 'generateContent',
    and removes non-text/specialized preview models (robotics, tts, image-only, audio).
    Sorts dynamically by version descending so the latest release is on top.
    """
    key = api_key if api_key is not None else os.environ.get("GEMINI_API_KEY")
    if not key or not key.strip():
        return DEFAULT_GEMINI_MODELS

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key.strip()}"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            models = data.get("models", [])
            filtered: List[Tuple[str, str]] = []
            
            for m in models:
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" not in methods:
                    continue

                raw_name = m.get("name", "")
                model_id = raw_name.replace("models/", "")
                display_name = m.get("displayName", model_id)

                # Filter out specialized non-text or hardware-specific methods
                lower_id = model_id.lower()
                if any(x in lower_id for x in ["robotics", "computer-use", "embed", "imagen", "image", "banana", "aqa", "tts", "clip", "lyria"]):
                    continue

                label = f"{model_id} ({display_name})" if display_name and display_name != model_id else model_id
                filtered.append((label, model_id))

            if filtered:
                def _version_priority(item: Tuple[str, str]) -> Tuple[int, float, str]:
                    mid = item[1]
                    # Check for explicit versions like 3.7, 3.5, 2.5, 2.0
                    match = re.search(r"gemini-(\d+(?:\.\d+)?)", mid)
                    if match:
                        try:
                            ver = float(match.group(1))
                            return (0, -ver, mid)
                        except ValueError:
                            pass
                    if "latest" in mid:
                        return (1, 0, mid)
                    if "gemma" in mid:
                        return (2, 0, mid)
                    return (3, 0, mid)

                filtered.sort(key=_version_priority)
                return filtered
    except Exception:
        pass

    return DEFAULT_GEMINI_MODELS


def fetch_lmstudio_models(base_url: str = "http://localhost:1234/v1") -> List[Tuple[str, str]]:
    """
    Queries local LM Studio models endpoint: GET http://localhost:1234/v1/models
    """
    url = f"{base_url.rstrip('/')}/models"
    try:
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            models = []
            for item in data:
                mid = item.get("id", "")
                if mid:
                    models.append((f"Helyi: {mid}", mid))
            if models:
                return models
    except Exception:
        pass
    return [("Helyi modell (local-model)", "local-model")]


def get_available_models_for_provider(provider: str, api_key: Optional[str] = None) -> List[Tuple[str, str]]:
    prov = (provider or "gemini").lower().strip()
    if prov == "gemini":
        return fetch_gemini_models(api_key=api_key)
    elif prov == "lmstudio":
        return fetch_lmstudio_models()
    elif prov == "openai":
        return DEFAULT_OPENAI_MODELS
    return DEFAULT_GEMINI_MODELS
