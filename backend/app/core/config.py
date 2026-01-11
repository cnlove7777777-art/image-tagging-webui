from pydantic_settings import BaseSettings
from typing import Optional
import json
from pathlib import Path


def _load_ports_config() -> dict:
    ports_path = Path(__file__).resolve().parents[3] / "config" / "ports.json"
    if not ports_path.exists():
        return {}
    try:
        with ports_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


_PORTS = _load_ports_config()
_REDIS_PORT = _PORTS.get("redis_port", 6379)


class Settings(BaseSettings):
    # Database configuration
    DATABASE_URL: str = "sqlite:///./data/db.sqlite3"

    # Redis configuration
    REDIS_URL: str = f"redis://localhost:{_REDIS_PORT}/0"

    # Model configuration
    MODELSCOPE_TOKEN: str
    BASE_URL: str = "https://api-inference.modelscope.cn/v1/"
    FOCUS_MODEL: str = "Qwen/Qwen3-VL-30B-A3B-Instruct"
    TAG_MODEL: str = "Qwen/Qwen3-VL-235B-A22B-Instruct"
    FALLBACK_MODEL: str = "Qwen/Qwen3-VL-32B-Instruct"

    # Processing configuration
    MAX_UPLOAD_MB: int = 2048
    PHASH_THRESHOLD: int = 6
    KEEP_PER_CLUSTER: int = 2
    PREVIEW_MAX_SIDE: int = 1280
    PREVIEW_JPEG_QUALITY: int = 86
    MAX_IMAGE_PIXELS: int = 1000000000

    # Celery configuration
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # Logging configuration
    LOG_LEVEL: str = "INFO"

    # Application configuration
    APP_NAME: str = "LoRA Dataset Builder"
    APP_VERSION: str = "1.0.0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
