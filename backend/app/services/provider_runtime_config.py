from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _runtime_config_path() -> Path:
    # Keep secrets under backend/data so they are ignored by .gitignore.
    return Path(os.getenv("MODEL_PROVIDER_RUNTIME_CONFIG", _repo_root() / "backend" / "data" / "runtime" / "model_provider_secrets.json"))


def _load_all() -> Dict[str, Any]:
    path = _runtime_config_path()
    if not path.exists():
        return {"providers": {}}
    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return {"providers": {}}
    if not isinstance(payload, dict):
        return {"providers": {}}
    providers = payload.get("providers")
    if not isinstance(providers, dict):
        payload["providers"] = {}
    return payload


def _save_all(payload: Dict[str, Any]) -> None:
    path = _runtime_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


def mask_secret(value: str | None) -> str:
    if not value:
        return ""
    text = str(value)
    if len(text) <= 8:
        return "***"
    return f"{text[:4]}...{text[-4:]}"


def get_provider_runtime_config(provider_id: str) -> Dict[str, Any]:
    payload = _load_all()
    data = payload.get("providers", {}).get(provider_id, {})
    return data if isinstance(data, dict) else {}


def update_provider_runtime_config(provider_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    payload = _load_all()
    providers = payload.setdefault("providers", {})
    current = providers.get(provider_id) or {}
    if not isinstance(current, dict):
        current = {}

    for key in [
        "base_url",
        "api_key",
        "default_vision_model",
        "default_focus_model",
        "default_tag_model",
    ]:
        if key not in patch:
            continue
        value = patch.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
        # Empty api_key means keep existing secret. Empty other fields clear override.
        if key == "api_key" and value == "":
            continue
        if key != "api_key" and value == "":
            current.pop(key, None)
            continue
        current[key] = value

    providers[provider_id] = current
    _save_all(payload)
    return current


def public_runtime_config(provider_id: str) -> Dict[str, Any]:
    data = get_provider_runtime_config(provider_id)
    return {
        "provider_id": provider_id,
        "base_url": data.get("base_url", ""),
        "api_key_masked": mask_secret(data.get("api_key")),
        "has_api_key": bool(data.get("api_key")),
        "default_vision_model": data.get("default_vision_model", ""),
        "default_focus_model": data.get("default_focus_model", ""),
        "default_tag_model": data.get("default_tag_model", ""),
    }
