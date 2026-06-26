from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List


_PROVIDER_ID_RE = re.compile(r"[^a-z0-9_-]+")


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


def normalize_provider_id(value: str) -> str:
    raw = str(value or "").strip().lower()
    raw = _PROVIDER_ID_RE.sub("_", raw).strip("_")
    if not raw:
        raw = "custom_provider"
    return raw[:64]


def mask_secret(value: str | None) -> str:
    if not value:
        return ""
    text = str(value)
    if len(text) <= 8:
        return "***"
    return f"{text[:4]}...{text[-4:]}"


def sanitize_models(models: Any) -> List[Dict[str, Any]]:
    if not isinstance(models, list):
        return []
    cleaned: List[Dict[str, Any]] = []
    seen = set()
    for item in models:
        if isinstance(item, str):
            model_id = item.strip()
            label = model_id
            tasks = ["vision_analyze", "focus", "caption", "tag"]
        elif isinstance(item, dict):
            model_id = str(item.get("id") or item.get("model") or item.get("name") or "").strip()
            label = str(item.get("label") or model_id).strip()
            raw_tasks = item.get("tasks")
            tasks = raw_tasks if isinstance(raw_tasks, list) else ["vision_analyze", "focus", "caption", "tag"]
        else:
            continue
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        cleaned.append({
            "id": model_id,
            "label": label or model_id,
            "tasks": [str(t) for t in tasks if str(t).strip()],
        })
    return cleaned


def get_all_provider_runtime_configs() -> Dict[str, Dict[str, Any]]:
    payload = _load_all()
    result: Dict[str, Dict[str, Any]] = {}
    for provider_id, data in payload.get("providers", {}).items():
        if isinstance(data, dict):
            result[str(provider_id)] = data
    return result


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

    string_keys = [
        "display_name",
        "base_url",
        "api_key",
        "api_format",
        "model_list_path",
        "default_vision_model",
        "default_focus_model",
        "default_tag_model",
    ]
    for key in string_keys:
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

    if "enabled" in patch and patch.get("enabled") is not None:
        current["enabled"] = bool(patch.get("enabled"))
    if "dynamic_model_list" in patch and patch.get("dynamic_model_list") is not None:
        current["dynamic_model_list"] = bool(patch.get("dynamic_model_list"))
    if "models" in patch:
        current["models"] = sanitize_models(patch.get("models"))

    providers[provider_id] = current
    _save_all(payload)
    return current


def create_provider_runtime_config(patch: Dict[str, Any]) -> Dict[str, Any]:
    display_name = str(patch.get("display_name") or patch.get("provider_id") or "自定义供应商").strip()
    provider_id = normalize_provider_id(str(patch.get("provider_id") or display_name))
    payload = _load_all()
    providers = payload.setdefault("providers", {})
    if provider_id in providers:
        suffix = 2
        base = provider_id
        while f"{base}_{suffix}" in providers:
            suffix += 1
        provider_id = f"{base}_{suffix}"
    data = update_provider_runtime_config(provider_id, {**patch, "display_name": display_name, "enabled": True})
    data["provider_id"] = provider_id
    return data


def delete_provider_runtime_config(provider_id: str) -> bool:
    payload = _load_all()
    providers = payload.setdefault("providers", {})
    existed = provider_id in providers
    if existed:
        providers.pop(provider_id, None)
        _save_all(payload)
    return existed


def public_runtime_config(provider_id: str) -> Dict[str, Any]:
    data = get_provider_runtime_config(provider_id)
    return {
        "provider_id": provider_id,
        "display_name": data.get("display_name", ""),
        "enabled": data.get("enabled", True),
        "base_url": data.get("base_url", ""),
        "api_format": data.get("api_format", "openai_chat_completions"),
        "model_list_path": data.get("model_list_path", "/models"),
        "dynamic_model_list": data.get("dynamic_model_list", True),
        "api_key_masked": mask_secret(data.get("api_key")),
        "has_api_key": bool(data.get("api_key")),
        "default_vision_model": data.get("default_vision_model", ""),
        "default_focus_model": data.get("default_focus_model", ""),
        "default_tag_model": data.get("default_tag_model", ""),
        "models": sanitize_models(data.get("models")),
    }
