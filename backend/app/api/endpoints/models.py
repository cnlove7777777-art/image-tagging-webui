from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.core.model_providers import public_provider_payload
from app.services.provider_runtime_config import public_runtime_config, update_provider_runtime_config

router = APIRouter()


class ProviderRuntimeConfigUpdate(BaseModel):
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    default_vision_model: Optional[str] = None
    default_focus_model: Optional[str] = None
    default_tag_model: Optional[str] = None


@router.get("/models", tags=["models"])
async def get_models(refresh: bool = Query(False)):
    """Return provider-driven model lists.

    Public response never contains raw API keys. Runtime overrides are read by
    the backend and only reflected as configured/masked status.
    """
    return public_provider_payload(refresh_dynamic=refresh)


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
