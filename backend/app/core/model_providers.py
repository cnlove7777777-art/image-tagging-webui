from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import yaml


@dataclass
class ModelProviderConfig:
    id: str
    enabled: bool
    display_name: str
    base_url: str
    api_key_env: str
    dynamic_model_list: bool
    model_list_path: str
    default_vision_model: str
    default_focus_model: str
    default_tag_model: str
    models: List[Dict[str, Any]]

    @property
    def configured(self) -> bool:
        return bool(os.getenv(self.api_key_env, "").strip())

    @property
    def api_key(self) -> str:
        return os.getenv(self.api_key_env, "").strip()


def _repo_root() -> Path:
    # backend/app/core/model_providers.py -> backend/app/core -> repo root
    return Path(__file__).resolve().parents[3]


def _config_path() -> Path:
    return Path(os.getenv("MODEL_PROVIDERS_CONFIG", _repo_root() / "config" / "model_providers.yml"))


def _load_yaml() -> Dict[str, Any]:
    path = _config_path()
    if not path.exists():
        return {"default_provider": "modelscope", "providers": {}}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"default_provider": "modelscope", "providers": {}}


def _provider_from_dict(provider_id: str, raw: Dict[str, Any]) -> ModelProviderConfig:
    return ModelProviderConfig(
        id=provider_id,
        enabled=bool(raw.get("enabled", False)),
        display_name=str(raw.get("display_name") or provider_id),
        base_url=str(raw.get("base_url") or "").rstrip("/"),
        api_key_env=str(raw.get("api_key_env") or ""),
        dynamic_model_list=bool(raw.get("dynamic_model_list", False)),
        model_list_path=str(raw.get("model_list_path") or "/models"),
        default_vision_model=str(raw.get("default_vision_model") or raw.get("default_focus_model") or ""),
        default_focus_model=str(raw.get("default_focus_model") or raw.get("default_vision_model") or ""),
        default_tag_model=str(raw.get("default_tag_model") or raw.get("default_vision_model") or ""),
        models=list(raw.get("models") or []),
    )


def get_default_provider_id() -> str:
    raw = _load_yaml()
    return str(raw.get("default_provider") or "modelscope")


def list_providers(include_disabled: bool = False, refresh_dynamic: bool = False) -> List[ModelProviderConfig]:
    raw = _load_yaml()
    providers: List[ModelProviderConfig] = []
    for provider_id, provider_raw in (raw.get("providers") or {}).items():
        provider = _provider_from_dict(provider_id, provider_raw or {})
        if not include_disabled and not provider.enabled:
            continue
        if refresh_dynamic:
            provider.models = _try_fetch_dynamic_models(provider) or provider.models
        providers.append(provider)
    return providers


def get_provider(provider_id: Optional[str] = None) -> ModelProviderConfig:
    target = provider_id or get_default_provider_id()
    for provider in list_providers(include_disabled=False, refresh_dynamic=False):
        if provider.id == target:
            return provider
    providers = list_providers(include_disabled=False, refresh_dynamic=False)
    if providers:
        return providers[0]
    raise RuntimeError("No enabled model provider configured")


def _try_fetch_dynamic_models(provider: ModelProviderConfig) -> Optional[List[Dict[str, Any]]]:
    if not provider.dynamic_model_list or not provider.configured or not provider.base_url:
        return None
    url = provider.base_url.rstrip("/") + "/" + provider.model_list_path.lstrip("/")
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, headers={"Authorization": f"Bearer {provider.api_key}"})
            response.raise_for_status()
            payload = response.json()
    except Exception:
        return None

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return None
    models: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id") or item.get("model") or item.get("name")
        if not model_id:
            continue
        models.append({"id": str(model_id), "label": str(model_id), "tasks": ["vision_analyze", "focus", "caption", "tag"]})
    return models or None


def public_provider_payload(refresh_dynamic: bool = False) -> Dict[str, Any]:
    default_provider = get_default_provider_id()
    providers = list_providers(include_disabled=False, refresh_dynamic=refresh_dynamic)

    public = []
    focus_models: List[str] = []
    tag_models: List[str] = []
    default_focus_model = ""
    default_tag_model = ""

    for provider in providers:
        task_models = provider.models
        provider_focus = [m["id"] for m in task_models if "focus" in (m.get("tasks") or []) or "vision_analyze" in (m.get("tasks") or [])]
        provider_tag = [m["id"] for m in task_models if "tag" in (m.get("tasks") or []) or "caption" in (m.get("tasks") or [])]
        focus_models.extend(provider_focus)
        tag_models.extend(provider_tag)
        if provider.id == default_provider:
            default_focus_model = provider.default_focus_model or (provider_focus[0] if provider_focus else "")
            default_tag_model = provider.default_tag_model or (provider_tag[0] if provider_tag else "")
        public.append(
            {
                "id": provider.id,
                "display_name": provider.display_name,
                "enabled": provider.enabled,
                "configured": provider.configured,
                "base_url": provider.base_url,
                "dynamic_model_list": provider.dynamic_model_list,
                "default_vision_model": provider.default_vision_model,
                "default_focus_model": provider.default_focus_model,
                "default_tag_model": provider.default_tag_model,
                "models": task_models,
            }
        )

    if not default_focus_model and focus_models:
        default_focus_model = focus_models[0]
    if not default_tag_model and tag_models:
        default_tag_model = tag_models[0]

    return {
        "default_provider": default_provider,
        "providers": public,
        # Legacy fields kept so the current frontend does not break while being migrated.
        "focus_models": focus_models,
        "tag_models": tag_models,
        "default_focus_model": default_focus_model,
        "default_tag_model": default_tag_model,
    }
