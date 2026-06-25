from fastapi import APIRouter, Query

from app.core.model_providers import public_provider_payload

router = APIRouter()


@router.get("/models", tags=["models"])
async def get_models(refresh: bool = Query(False)):
    """Return backend-owned model provider and model lists.

    The frontend must not send API keys or base URLs. It only receives public
    provider metadata, configured status, and selectable model ids.
    """
    return public_provider_payload(refresh_dynamic=refresh)
