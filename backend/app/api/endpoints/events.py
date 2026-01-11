from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import asyncio
import json
from app.models.task import Task, TaskStage, TaskStatus
from app.core.config import settings
from app.db.database import get_db
from app.schemas.task import ProgressInfo

router = APIRouter()


async def event_generator(task_id: int, db):
    """Generate SSE events for task progress"""
    last_progress = -1
    last_stage = ""
    last_message = ""
    last_status = ""
    last_detail = None

    def _stage_meta(task: Task) -> ProgressInfo:
        stage_order = {
            TaskStage.UNPACKING: 1,
            TaskStage.PREVIEW_GENERATION: 1,
            TaskStage.DE_DUPLICATION: 2,
            TaskStage.FOCUS_DETECTION: 3,
            TaskStage.CROPPING: 3,
            TaskStage.TAGGING: 4,
            TaskStage.PACKAGING: 4,
            TaskStage.FINISHED: 4,
            TaskStage.INITIAL: 1,
        }
        stage_names = {
            1: "上传/解压",
            2: "去重",
            3: "裁切",
            4: "打标/导出",
        }
        stage_total = 4
        stage_index = stage_order.get(task.stage, 1)
        segment = 100 / stage_total
        overall_raw = max(0.0, min(100.0, float(task.progress)))
        if task.status == TaskStatus.COMPLETED:
            overall_raw = 100.0
            stage_index = stage_total
            stage_percent = 100.0
        else:
            stage_start = segment * (stage_index - 1)
            stage_percent = (overall_raw - stage_start) / segment * 100
            stage_percent = max(0.0, min(100.0, stage_percent))
        return ProgressInfo(
            overall_percent=overall_raw,
            stage_index=stage_index,
            stage_total=stage_total,
            stage_name=stage_names.get(stage_index, task.stage.value if hasattr(task.stage, "value") else str(task.stage)),
            stage_percent=stage_percent,
            step_hint=task.message,
        )
    
    while True:
        # Get current task status
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            yield f"event: error\ndata: {json.dumps({'message': 'Task not found'})}\n\n"
            break
        
        # Check if task is completed or error
        if task.status in ['completed', 'error']:
            # Send final update
            data = {
                "id": task.id,
                "status": task.status,
                "stage": task.stage,
                "progress": task.progress,
                "message": task.message,
                "stats": task.stats,
                "progress_detail": _stage_meta(task).model_dump(),
                "export_ready": bool(task.export_path)
            }
            yield f"data: {json.dumps(data)}\n\n"
            # Send completion event
            yield f"event: done\ndata: {json.dumps({'id': task.id, 'status': task.status})}\n\n"
            break
        
        # Check if any field has changed
        if (
            task.progress != last_progress or 
            task.stage != last_stage or 
            task.message != last_message or 
            task.status != last_status
        ):
            data = {
                "id": task.id,
                "status": task.status,
                "stage": task.stage,
                "progress": task.progress,
                "message": task.message,
                "stats": task.stats,
                "progress_detail": _stage_meta(task).model_dump(),
                "export_ready": bool(task.export_path)
            }
            yield f"data: {json.dumps(data)}\n\n"
            
            # Update last values
            last_progress = task.progress
            last_stage = task.stage
            last_message = task.message
            last_status = task.status
        
        # Wait before next check
        await asyncio.sleep(1)


@router.get("/tasks/{task_id}/events")
async def get_task_events(
    task_id: int,
    db = Depends(get_db)
):
    """Get real-time task progress via SSE"""
    # Check if task exists
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return StreamingResponse(
        event_generator(task_id, db),
        media_type="text/event-stream"
    )
