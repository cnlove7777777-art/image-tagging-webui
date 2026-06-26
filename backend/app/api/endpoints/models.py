from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.model_providers import get_provider, public_provider_payload
from app.services.provider_runtime_config import (
    create_provider_runtime_config,
    delete_provider_runtime_config,
    public_runtime_config,
    update_provider_runtime_config,
)

router = APIRouter()


class ProviderModelPayload(BaseModel):
    id: str
    label: Optional[str] = None
    tasks: Optional[List[str]] = None


class ProviderRuntimeConfigUpdate(BaseModel):
    display_name: Optional[str] = None
    enabled: Optional[bool] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    api_format: Optional[str] = "openai_chat_completions"
    model_list_path: Optional[str] = "/models"
    dynamic_model_list: Optional[bool] = True
    default_vision_model: Optional[str] = None
    default_focus_model: Optional[str] = None
    default_tag_model: Optional[str] = None
    models: Optional[List[ProviderModelPayload]] = None


class ProviderCreatePayload(ProviderRuntimeConfigUpdate):
    provider_id: Optional[str] = None
    display_name: str


class ProviderTestPayload(BaseModel):
    model: Optional[str] = None


@router.get("/models", tags=["models"])
async def get_models(refresh: bool = Query(False)):
    """Return provider-driven model lists.

    Public response never contains raw API keys. Runtime overrides are read by
    the backend and only reflected as configured/masked status.
    """
    return public_provider_payload(refresh_dynamic=refresh)


@router.post("/models/providers", tags=["models"])
async def create_provider(payload: ProviderCreatePayload):
    """Create a custom provider in local runtime config."""
    created = create_provider_runtime_config(payload.model_dump(exclude_unset=True))
    provider_id = str(created.get("provider_id"))
    return public_runtime_config(provider_id)


@router.delete("/models/providers/{provider_id}", tags=["models"])
async def delete_provider(provider_id: str):
    """Delete a runtime-created provider or runtime overrides for a provider."""
    deleted = delete_provider_runtime_config(provider_id)
    return {"provider_id": provider_id, "deleted": deleted}


@router.get("/models/providers/{provider_id}/runtime-config", tags=["models"])
async def get_provider_runtime_config(provider_id: str):
    """Return local runtime config for one provider without exposing secrets."""
    return public_runtime_config(provider_id)


@router.post("/models/providers/{provider_id}/runtime-config", tags=["models"])
async def save_provider_runtime_config(provider_id: str, payload: ProviderRuntimeConfigUpdate):
    """Save provider runtime config to a local ignored backend data file.

    This endpoint intentionally allows frontend-driven configuration while
    keeping secrets out of Git and out of API responses.
    """
    update_provider_runtime_config(provider_id, payload.model_dump(exclude_unset=True))
    return public_runtime_config(provider_id)


@router.post("/models/providers/{provider_id}/test", tags=["models"])
async def test_provider(provider_id: str, payload: ProviderTestPayload):
    """Test provider connectivity using backend-held credentials.

    First try the OpenAI-compatible /models endpoint. This is safer and cheaper
    than a chat completion. If /models is unsupported, return the provider error
    so the UI can show what failed.
    """
    try:
        provider = get_provider(provider_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    if not provider.base_url:
        return {"ok": False, "provider_id": provider_id, "error": "Base URL is empty"}
    if not provider.configured:
        return {"ok": False, "provider_id": provider_id, "error": "API Key is missing"}

    url = provider.base_url.rstrip("/") + "/" + provider.model_list_path.lstrip("/")
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, headers={"Authorization": f"Bearer {provider.api_key}"})
            text = response.text[:500]
            if response.status_code >= 400:
                return {
                    "ok": False,
                    "provider_id": provider_id,
                    "status_code": response.status_code,
                    "url": url,
                    "error": text,
                }
            data: Dict[str, Any] = response.json()
            models = data.get("data") if isinstance(data, dict) else None
            return {
                "ok": True,
                "provider_id": provider_id,
                "url": url,
                "status_code": response.status_code,
                "model_count": len(models) if isinstance(models, list) else None,
                "sample_models": [m.get("id") for m in models[:5] if isinstance(m, dict) and m.get("id")] if isinstance(models, list) else [],
            }
    except Exception as exc:
        return {"ok": False, "provider_id": provider_id, "url": url, "error": str(exc)}
