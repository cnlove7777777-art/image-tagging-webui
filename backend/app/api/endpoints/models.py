from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.database import get_db

router = APIRouter()


@router.get("/models", tags=["models"])
async def get_models(db: Session = Depends(get_db)):
    """获取支持的模型列表"""
    return {
        "focus_models": [
            "Qwen/Qwen3-VL-30B-A3B-Instruct",
            "Qwen/Qwen3-VL-235B-A22B-Instruct",
            "Qwen/Qwen3-VL-32B-Instruct",
            "Qwen/Qwen3-VL-72B-Instruct"
        ],
        "tag_models": [
            "Qwen/Qwen3-VL-235B-A22B-Instruct",
            "Qwen/Qwen3-VL-30B-A3B-Instruct",
            "Qwen/Qwen3-VL-32B-Instruct",
            "Qwen/Qwen3-VL-72B-Instruct"
        ],
        "default_focus_model": settings.FOCUS_MODEL,
        "default_tag_model": settings.TAG_MODEL
    }
