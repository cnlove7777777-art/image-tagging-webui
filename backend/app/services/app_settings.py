from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.defaults import DEFAULT_CAPTION_PROMPT, DEFAULT_DEDUP_PARAMS
from app.models.app_setting import AppSetting


def _get_or_create_setting(db: Session, key: str, default_value: Any) -> AppSetting:
    setting = db.query(AppSetting).filter(AppSetting.key == key).first()
    if setting:
        return setting
    setting = AppSetting(key=key, value=default_value)
    db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting


def get_app_settings(db: Session) -> Dict[str, Any]:
    caption = _get_or_create_setting(db, "caption_prompt", DEFAULT_CAPTION_PROMPT).value
    dedup_params = _get_or_create_setting(db, "dedup_params", DEFAULT_DEDUP_PARAMS).value
    if isinstance(dedup_params, dict):
        merged = {**DEFAULT_DEDUP_PARAMS, **dedup_params}
        if merged != dedup_params:
            set_setting(db, "dedup_params", merged)
        dedup_params = merged
    else:
        dedup_params = DEFAULT_DEDUP_PARAMS
        set_setting(db, "dedup_params", dedup_params)
    return {
        "caption_prompt": caption,
        "dedup_params": dedup_params,
    }


def set_setting(db: Session, key: str, value: Any) -> None:
    setting = db.query(AppSetting).filter(AppSetting.key == key).first()
    if setting:
        setting.value = value
    else:
        setting = AppSetting(key=key, value=value)
        db.add(setting)
    db.commit()


def update_app_settings(
    db: Session,
    caption_prompt: Optional[str] = None,
    dedup_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    current = get_app_settings(db)

    if caption_prompt is not None:
        set_setting(db, "caption_prompt", caption_prompt)
        current["caption_prompt"] = caption_prompt

    if dedup_params is not None:
        merged = {**current.get("dedup_params", DEFAULT_DEDUP_PARAMS), **dedup_params}
        set_setting(db, "dedup_params", merged)
        current["dedup_params"] = merged

    return current
