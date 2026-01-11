from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime
from app.models.task import TaskStatus, TaskStage


class TaskBatchResponse(BaseModel):
    id: int
    zip_name: str


class ProgressInfo(BaseModel):
    overall_percent: float
    stage_index: int
    stage_total: int
    stage_name: str
    stage_percent: float
    step_hint: Optional[str] = None


class TaskResponse(BaseModel):
    id: int
    name: str
    status: TaskStatus
    stage: TaskStage
    progress: int
    message: str
    created_at: datetime
    updated_at: datetime
    focus_model: str
    tag_model: str
    stats: Dict
    upload_path: Optional[str] = None
    export_path: Optional[str] = None
    export_ready: bool = False
    config: Dict = {}
    progress_detail: ProgressInfo
    items: Optional[list] = None

    class Config:
        from_attributes = True
