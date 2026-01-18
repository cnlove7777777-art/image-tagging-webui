from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Request, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import os
import shutil
import threading
import json
from pathlib import Path
import sys
from typing import List, Optional, Dict, Union, Set
from pydantic import BaseModel

from app.core.config import settings
from app.models.task import Task, TaskStatus, TaskStage
from app.models.image import Image
from app.models.log import Log, LogLevel
from app.schemas.task import TaskResponse, TaskBatchResponse, ProgressInfo
from app.tasks import processing
from app.api.endpoints import events
from app.db.database import get_db, SessionLocal
from app.core.defaults import DEFAULT_DEDUP_PARAMS
from app.services.app_settings import get_app_settings as load_app_settings, update_app_settings
from sqlalchemy.exc import OperationalError
import time
import hashlib
import re

# FastAPI app
app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create data directories
os.makedirs("./data/tasks", exist_ok=True)
os.makedirs("./data/db", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="./data/tasks"), name="static")

# Include event routes
app.include_router(events.router, prefix="/api", tags=["events"])

# Include models routes
from app.api.endpoints.models import router as models_router
app.include_router(models_router, prefix="/api", tags=["models"])


def _load_ports_config() -> Dict[str, int | str]:
    ports_path = Path(__file__).resolve().parents[2] / "config" / "ports.json"
    if not ports_path.exists():
        raise RuntimeError("Missing config/ports.json")
    with ports_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _expected_backend_port() -> int:
    ports = _load_ports_config()
    return int(ports.get("backend_port", 8081))


def _expected_backend_host() -> str:
    ports = _load_ports_config()
    return str(ports.get("backend_host", "0.0.0.0"))


def _detect_cli_port() -> Optional[int]:
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            try:
                return int(sys.argv[idx + 1])
            except ValueError:
                return None
    if sys.argv and "uvicorn" in Path(sys.argv[0]).name.lower():
        return 8000
    return None


def _safe_rel_path(filename: str) -> Optional[str]:
    normalized = filename.replace("\\", "/").lstrip("/")
    if len(normalized) >= 2 and normalized[1] == ":":
        normalized = normalized[2:].lstrip("/")
    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        return None
    return os.path.join(*parts)


_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _is_image_file(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in _IMAGE_EXTS


def _sanitize_stem(stem: str) -> str:
    cleaned = _SAFE_NAME_RE.sub("_", stem).strip("._ ")
    return cleaned[:80]


def _build_safe_name(original_rel: str, used_names: Set[str]) -> str:
    base = os.path.basename(original_rel)
    stem, ext = os.path.splitext(base)
    ext = ext.lower()
    safe_stem = _sanitize_stem(stem)
    if not safe_stem:
        safe_stem = "image"
    suffix = hashlib.sha1(original_rel.encode("utf-8")).hexdigest()[:8]
    candidate = f"{safe_stem}__{suffix}{ext}"
    if candidate in used_names:
        idx = 1
        while True:
            alt = f"{safe_stem}__{suffix}_{idx}{ext}"
            if alt not in used_names:
                candidate = alt
                break
            idx += 1
    used_names.add(candidate)
    return candidate

def _guess_folder_name(files: List[UploadFile]) -> str:
    for upload in files:
        rel = upload.filename.replace("\\", "/")
        parts = [part for part in rel.split("/") if part]
        if len(parts) > 1:
            return parts[0]
    if files:
        base = files[0].filename.replace("\\", "/").split("/")[-1]
        return os.path.splitext(base)[0] or "folder_upload"
    return "folder_upload"


@app.on_event("startup")
def _validate_backend_port() -> None:
    expected = _expected_backend_port()
    env_port = os.getenv("BACKEND_PORT") or os.getenv("PORT") or os.getenv("UVICORN_PORT")
    cli_port = _detect_cli_port()
    actual = None
    if env_port:
        try:
            actual = int(env_port)
        except ValueError:
            actual = None
    if actual is None and cli_port is not None:
        actual = cli_port
    if actual is not None and actual != expected:
        raise RuntimeError(f"Backend port must be {expected} (config/ports.json), got {actual}")

class SelectionPayload(BaseModel):
    image_ids: List[int]
    selected: bool


class DecisionPayload(BaseModel):
    keep: bool


class CropUpdatePayload(BaseModel):
    crop_square: Dict
    source: str = "user"


class DedupParamsPayload(BaseModel):
    face_sim_th1: Optional[float] = DEFAULT_DEDUP_PARAMS["face_sim_th1"]
    face_sim_th2: Optional[float] = DEFAULT_DEDUP_PARAMS["face_sim_th2"]
    pose_sim_th: Optional[float] = DEFAULT_DEDUP_PARAMS["pose_sim_th"]
    face_ssim_th1: Optional[float] = DEFAULT_DEDUP_PARAMS["face_ssim_th1"]
    face_ssim_th2: Optional[float] = DEFAULT_DEDUP_PARAMS["face_ssim_th2"]
    bbox_tol_c: Optional[float] = DEFAULT_DEDUP_PARAMS["bbox_tol_c"]
    bbox_tol_wh: Optional[float] = DEFAULT_DEDUP_PARAMS["bbox_tol_wh"]
    keep_per_cluster: Optional[int] = DEFAULT_DEDUP_PARAMS["keep_per_cluster"]


class SettingsTestResponse(BaseModel):
    ok: bool
    message: str
    base_url: Optional[str] = None


class AppSettingsResponse(BaseModel):
    caption_prompt: str
    dedup_params: Dict[str, Union[float, int]]
    crop_output_size: int


class AppSettingsUpdate(BaseModel):
    caption_prompt: Optional[str] = None
    dedup_params: Optional[Dict[str, Union[float, int]]] = None
    crop_output_size: Optional[int] = None

def _get_task_or_404(db: Session, task_id: int) -> Task:
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        processing.clear_cancelled(task_id)
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def _assert_idle(task: Task):
    if task.status == TaskStatus.PROCESSING:
        raise HTTPException(status_code=400, detail="Task is already processing")


def _add_log(db: Session, message: str, level: LogLevel = LogLevel.INFO, task_id: Optional[int] = None):
    log = Log(task_id=task_id, level=level, message=message)
    db.add(log)
    db.commit()


def _delete_task_dirs(task_dirs: List[str], attempts: int = 6, delay: float = 0.5) -> None:
    remaining = [path for path in task_dirs if path]
    for _ in range(attempts):
        if not remaining:
            return
        next_remaining = []
        for path in remaining:
            try:
                shutil.rmtree(path)
            except Exception:
                next_remaining.append(path)
        remaining = next_remaining
        if remaining:
            time.sleep(delay)
    for path in remaining:
        try:
            shutil.rmtree(path, ignore_errors=True)
        except Exception:
            pass


def _clear_tasks_root() -> None:
    base = "./data/tasks"
    try:
        if os.path.isdir(base):
            task_dirs = [os.path.join(base, name) for name in os.listdir(base)]
            _delete_task_dirs(task_dirs)
    except Exception:
        pass


def _force_clear_db() -> None:
    db = SessionLocal()
    try:
        attempts = 0
        while attempts < 30:
            try:
                db.query(Image).delete(synchronize_session=False)
                db.query(Log).delete(synchronize_session=False)
                db.query(Task).delete(synchronize_session=False)
                db.commit()
                return
            except OperationalError as exc:
                db.rollback()
                attempts += 1
                if "locked" in str(exc).lower():
                    time.sleep(0.5)
                    continue
                return
            except Exception:
                db.rollback()
                return
    finally:
        db.close()


def _force_delete_all() -> None:
    try:
        _force_clear_db()
        _clear_tasks_root()
    finally:
        processing.clear_cancel_all()


def _force_delete_task(task_id: int) -> None:
    db = SessionLocal()
    try:
        attempts = 0
        while attempts < 30:
            try:
                db.query(Image).filter(Image.task_id == task_id).delete(synchronize_session=False)
                db.query(Log).filter(Log.task_id == task_id).delete(synchronize_session=False)
                db.query(Task).filter(Task.id == task_id).delete(synchronize_session=False)
                db.commit()
                break
            except OperationalError as exc:
                db.rollback()
                attempts += 1
                if "locked" in str(exc).lower():
                    time.sleep(0.5)
                    continue
                break
            except Exception:
                db.rollback()
                break
    finally:
        task_dir = os.path.join("./data/tasks", str(task_id))
        _delete_task_dirs([task_dir])
        processing.clear_cancelled(task_id)
        db.close()


def _reset_task_data(task: Task, db: Session):
    """Clear images/preview/crops/export for a task so it can be recomputed."""
    # delete image records
    db.query(Image).filter(Image.task_id == task.id).delete()
    db.commit()
    # remove generated dirs (keep upload/unpack)
    base = f"./data/tasks/{task.id}"
    for sub in ["previews", "crops", "export", "crops/images", "crops/txt"]:
        path = os.path.join(base, sub)
        shutil.rmtree(path, ignore_errors=True)
    # recreate base dirs needed
    os.makedirs(os.path.join(base, "previews"), exist_ok=True)
    os.makedirs(os.path.join(base, "crops", "images"), exist_ok=True)
    os.makedirs(os.path.join(base, "crops", "txt"), exist_ok=True)
    os.makedirs(os.path.join(base, "export"), exist_ok=True)

def _image_summary(img: Image, task_id: int) -> Dict:
    meta = img.meta_json or {}
    crop_meta = meta.get("focus", {}) if isinstance(meta, dict) else {}
    crop_square_user = meta.get("crop_square_user") if isinstance(meta, dict) else None
    crop_square_model = meta.get("crop_square_model") if isinstance(meta, dict) else None
    dedup_meta = meta.get("dedup", {}) if isinstance(meta, dict) else {}

    # Get subject ratio with enhanced fallback logic
    subject_ratio = meta.get("subject_area_ratio")
    
    # Fallback 1: Use focus bbox if available
    if subject_ratio is None and crop_meta.get("bbox"):
        bbox = crop_meta["bbox"]
        subject_ratio = max(0.0, min(1.0, (bbox.get("x2", 0) - bbox.get("x1", 0)) * (bbox.get("y2", 0) - bbox.get("y1", 0))))
    
    # Fallback 2: Use crop square if available
    if subject_ratio is None and crop_square_model:
        side = crop_square_model.get("side")
        if side:
            subject_ratio = max(0.0, min(1.0, float(side) * float(side)))
    
    # Ensure image dimensions are valid
    width = img.width if img.width is not None and img.width > 0 else 1024
    height = img.height if img.height is not None and img.height > 0 else 1024

    # Get face and pose info with proper defaults
    has_face = meta.get("has_face")
    if has_face is None:
        has_face = bool(dedup_meta.get("face_emb") or crop_meta.get("bbox"))
    
    face_conf = meta.get("face_conf") or crop_meta.get("confidence") or 0.0
    
    has_pose = meta.get("has_pose")
    if has_pose is None:
        has_pose = False

    pose_conf = meta.get("pose_conf") or 0.0

    summary = {
        "id": img.id,
        "orig_name": img.orig_name,
        "width": width,
        "height": height,
        "md5": img.md5,
        "preview_url": f"/static/{task_id}/previews/{os.path.basename(img.preview_path)}" if img.preview_path else None,
        "crop_url": f"/static/{task_id}/crops/images/{os.path.basename(img.crop_path)}" if img.crop_path else None,
        "keep": img.selected,
        "sharpness": img.sharpness if img.sharpness is not None and img.sharpness > 0 else 0.0,
        "subject_area_ratio": subject_ratio,
        "has_face": has_face,
        "face_conf": face_conf,
        "has_pose": has_pose,
        "pose_conf": pose_conf,
        "cluster_id": dedup_meta.get("cluster_id"),
        "shot_type": meta.get("focus", {}).get("shot_type") if meta.get("focus") else None,
        "confidence": meta.get("focus", {}).get("confidence") if meta.get("focus") else None,
        "reason": meta.get("focus", {}).get("reason") if meta.get("focus") else None,
        "quality": meta.get("quality"),
        "decision": meta.get("decision") if isinstance(meta, dict) else None,
        "crop_square_model": crop_square_model,
        "crop_square_user": crop_square_user,
    }
    return summary


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


@app.post("/api/tasks", response_model=TaskResponse)
async def create_task(
    file: UploadFile = File(...),
    focus_model: Optional[str] = Form(settings.FOCUS_MODEL),
    tag_model: Optional[str] = Form(settings.TAG_MODEL),
    api_key: Optional[str] = Form(None),
    base_url: Optional[str] = Form(None),
    request: Request = None,
    db: Session = Depends(get_db)
):
    # Allow overriding via headers
    header_base = request.headers.get("X-Ext-Base-Url")
    header_key = request.headers.get("X-Ext-Api-Key")
    header_models = request.headers.get("X-Ext-Models")
    use_custom = bool(header_base or header_key or header_models)

    if header_base:
        base_url = header_base
    if header_key:
        api_key = header_key

    # Create task directory
    task = Task(
        name=file.filename,
        status=TaskStatus.PROCESSING,
        focus_model=focus_model,
        tag_model=tag_model,
        api_key=api_key,
        base_url=base_url,
        config={
            "base_url_source": "custom" if use_custom else "default",
            "model_priority": header_models,
        },
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # Create task directories
    task_dir = f"./data/tasks/{task.id}"
    unpack_dir = os.path.join(task_dir, "unpack")
    previews_dir = os.path.join(task_dir, "previews")
    crops_dir = os.path.join(task_dir, "crops")
    images_dir = os.path.join(crops_dir, "images")
    txt_dir = os.path.join(crops_dir, "txt")
    export_dir = os.path.join(task_dir, "export")

    for dir_path in [task_dir, unpack_dir, previews_dir, crops_dir, images_dir, txt_dir, export_dir]:
        os.makedirs(dir_path, exist_ok=True)

    # Save uploaded file
    upload_path = os.path.join(task_dir, f"upload.zip")
    file_size = 0
    max_size = settings.MAX_UPLOAD_MB * 1024 * 1024

    with open(upload_path, "wb") as buffer:
        while True:
            chunk = await file.read(1024 * 1024)  # 1MB chunks
            if not chunk:
                break
            file_size += len(chunk)
            if file_size > max_size:
                raise HTTPException(status_code=413, detail="File too large")
            buffer.write(chunk)

    # Update task with upload path
    task.upload_path = upload_path
    task.status = TaskStatus.PROCESSING
    task.stage = TaskStage.UNPACKING
    task.progress = 0
    task.message = "Upload completed, preparing files..."
    db.commit()

    # Start initial prepare step only
    processing.submit_task(processing.prepare_task, task.id)

    task.progress_detail = _stage_meta(task)
    task.export_ready = False
    return task


@app.post("/api/tasks/folder", response_model=TaskResponse)
async def create_folder_task(
    files: List[UploadFile] = File(...),
    folder_name: Optional[str] = Form(None),
    focus_model: Optional[str] = Form(settings.FOCUS_MODEL),
    tag_model: Optional[str] = Form(settings.TAG_MODEL),
    api_key: Optional[str] = Form(None),
    base_url: Optional[str] = Form(None),
    request: Request = None,
    db: Session = Depends(get_db)
):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    header_base = request.headers.get("X-Ext-Base-Url")
    header_key = request.headers.get("X-Ext-Api-Key")
    header_models = request.headers.get("X-Ext-Models")
    use_custom = bool(header_base or header_key or header_models)

    if header_base:
        base_url = header_base
    if header_key:
        api_key = header_key

    task_name = folder_name or _guess_folder_name(files)

    task = Task(
        name=task_name,
        status=TaskStatus.PROCESSING,
        focus_model=focus_model,
        tag_model=tag_model,
        api_key=api_key,
        base_url=base_url,
        config={
            "base_url_source": "custom" if use_custom else "default",
            "model_priority": header_models,
            "input_type": "folder",
        },
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    task_dir = f"./data/tasks/{task.id}"
    unpack_dir = os.path.join(task_dir, "unpack")
    previews_dir = os.path.join(task_dir, "previews")
    crops_dir = os.path.join(task_dir, "crops")
    images_dir = os.path.join(crops_dir, "images")
    txt_dir = os.path.join(crops_dir, "txt")
    export_dir = os.path.join(task_dir, "export")

    for dir_path in [task_dir, unpack_dir, previews_dir, crops_dir, images_dir, txt_dir, export_dir]:
        os.makedirs(dir_path, exist_ok=True)

    file_size = 0
    max_size = settings.MAX_UPLOAD_MB * 1024 * 1024
    saved_files = 0
    used_names: Set[str] = set()

    for upload in files:
        safe_rel = _safe_rel_path(upload.filename)
        if not safe_rel:
            _add_log(db, f"跳过非法路径: {upload.filename}", LogLevel.WARNING, task.id)
            continue
        if not _is_image_file(safe_rel):
            try:
                await upload.close()
            except Exception:
                pass
            continue

        safe_name = _build_safe_name(safe_rel, used_names)
        target_path = os.path.join(unpack_dir, safe_name)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        with open(target_path, "wb") as buffer:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                file_size += len(chunk)
                if file_size > max_size:
                    _add_log(db, f"上传失败：{task_name} 超出大小限制 {settings.MAX_UPLOAD_MB}MB", LogLevel.ERROR, task.id)
                    raise HTTPException(status_code=413, detail="Folder upload too large")
                buffer.write(chunk)
        saved_files += 1

    if saved_files == 0:
        raise HTTPException(status_code=400, detail="No valid files to save")

    task.upload_path = None
    task.status = TaskStatus.PROCESSING
    task.stage = TaskStage.UNPACKING
    task.progress = 0
    task.message = "Upload completed, preparing files..."
    db.commit()

    processing.submit_task(processing.prepare_task, task.id)

    task.progress_detail = _stage_meta(task)
    task.export_ready = False
    return task


@app.post("/api/tasks/batch", response_model=List[TaskBatchResponse])
async def create_batch_tasks(
    files: List[UploadFile] = File(...),
    focus_model: Optional[str] = Form(settings.FOCUS_MODEL),
    tag_model: Optional[str] = Form(settings.TAG_MODEL),
    api_key: Optional[str] = Form(None),
    base_url: Optional[str] = Form(None),
    request: Request = None,
    db: Session = Depends(get_db)
):
    header_base = request.headers.get("X-Ext-Base-Url")
    header_key = request.headers.get("X-Ext-Api-Key")
    header_models = request.headers.get("X-Ext-Models")
    use_custom = bool(header_base or header_key or header_models)

    if header_base:
        base_url = header_base
    if header_key:
        api_key = header_key

    results = []
    for file in files:
        # Create task
        task = Task(
            name=file.filename,
            status=TaskStatus.PROCESSING,
            focus_model=focus_model,
            tag_model=tag_model,
            api_key=api_key,
            base_url=base_url,
            config={
                "base_url_source": "custom" if use_custom else "default",
                "model_priority": header_models,
            },
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        # Create task directories
        task_dir = f"./data/tasks/{task.id}"
        unpack_dir = os.path.join(task_dir, "unpack")
        previews_dir = os.path.join(task_dir, "previews")
        crops_dir = os.path.join(task_dir, "crops")
        images_dir = os.path.join(crops_dir, "images")
        txt_dir = os.path.join(crops_dir, "txt")
        export_dir = os.path.join(task_dir, "export")

        for dir_path in [task_dir, unpack_dir, previews_dir, crops_dir, images_dir, txt_dir, export_dir]:
            os.makedirs(dir_path, exist_ok=True)

        # Save uploaded file
        upload_path = os.path.join(task_dir, f"upload.zip")
        file_size = 0
        max_size = settings.MAX_UPLOAD_MB * 1024 * 1024

        with open(upload_path, "wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                file_size += len(chunk)
                if file_size > max_size:
                    _add_log(db, f"上传失败：{file.filename} 超出大小限制 {settings.MAX_UPLOAD_MB}MB", LogLevel.ERROR, task.id)
                    raise HTTPException(status_code=413, detail=f"File {file.filename} too large")
                buffer.write(chunk)

        # Update task
        task.upload_path = upload_path
        task.status = TaskStatus.PROCESSING
        task.stage = TaskStage.UNPACKING
        task.progress = 0
        task.message = "Upload completed, preparing files..."
        db.commit()

        # Kick off prepare step
        processing.submit_task(processing.prepare_task, task.id)

        results.append({"id": task.id, "zip_name": file.filename})

    return results


@app.get("/api/tasks", response_model=List[TaskResponse])
def get_tasks(include_items: bool = Query(False), db: Session = Depends(get_db)):
    tasks = db.query(Task).all()
    for task in tasks:
        task.progress_detail = _stage_meta(task)
        task.export_ready = bool(task.export_path and os.path.exists(task.export_path))
        if task.config is None:
            task.config = {}
        if include_items:
            imgs = db.query(Image).filter(Image.task_id == task.id).all()
            task.items = [_image_summary(img, task.id) for img in imgs]
    return tasks


@app.get("/api/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = _get_task_or_404(db, task_id)
    task.progress_detail = _stage_meta(task)
    task.export_ready = bool(task.export_path and os.path.exists(task.export_path))
    if task.config is None:
        task.config = {}
    imgs = db.query(Image).filter(Image.task_id == task_id).all()
    task.items = [_image_summary(img, task_id) for img in imgs]
    return task


@app.post("/api/tasks/{task_id}/images/select")
def update_image_selection(task_id: int, payload: SelectionPayload, db: Session = Depends(get_db)):
    _get_task_or_404(db, task_id)
    images = db.query(Image).filter(Image.task_id == task_id, Image.id.in_(payload.image_ids)).all()
    for img in images:
        img.selected = payload.selected
        meta = img.meta_json or {}
        meta["decision"] = {"keep": payload.selected}
        img.meta_json = meta
    db.commit()
    return {"updated": len(images)}


@app.post("/api/tasks/{task_id}/items/{item_id}/decision")
def update_decision(task_id: int, item_id: int, payload: DecisionPayload, db: Session = Depends(get_db)):
    _get_task_or_404(db, task_id)
    image = db.query(Image).filter(Image.task_id == task_id, Image.id == item_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    image.selected = payload.keep
    meta = image.meta_json or {}
    meta["decision"] = {"keep": payload.keep}
    image.meta_json = meta
    db.commit()
    return {"id": item_id, "keep": payload.keep}


@app.post("/api/tasks/{task_id}/items/{item_id}/crop")
def update_crop(task_id: int, item_id: int, payload: CropUpdatePayload, db: Session = Depends(get_db)):
    _get_task_or_404(db, task_id)
    image = db.query(Image).filter(Image.task_id == task_id, Image.id == item_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    if not image.orig_path:
        raise HTTPException(status_code=400, detail="Missing original image")
    dirs = {
        "images": os.path.join(f"./data/tasks/{task_id}", "crops", "images"),
    }
    os.makedirs(dirs["images"], exist_ok=True)
    crop_square = payload.crop_square or {}
    cx = crop_square.get("cx", 0.5)
    cy = crop_square.get("cy", 0.5)
    side = crop_square.get("side", 1.0)
    # Convert side to half-size scaling
    app_settings = load_app_settings(db)
    crop_output_size = int(app_settings.get("crop_output_size", 1024) or 1024)
    crop_path = processing.crop_1024_from_original(
        image.orig_path,
        cx,
        cy,
        dirs["images"],
        quality=95,
        side=side,
        output_size=crop_output_size,
    )
    meta = image.meta_json or {}
    meta["crop_square_user"] = {"cx": cx, "cy": cy, "side": side, "source": payload.source}
    image.meta_json = meta
    image.crop_path = crop_path
    db.commit()
    return {"id": item_id, "crop_path": f"/static/{task_id}/crops/images/{os.path.basename(crop_path)}", "crop_square": meta["crop_square_user"]}


@app.delete("/api/tasks/{task_id}")
def delete_task(
    task_id: int,
    force: bool = Query(True),
    db: Session = Depends(get_db)
):
    processing.cancel_task(task_id)
    if force:
        threading.Thread(target=_force_delete_task, args=(task_id,), daemon=True).start()
        return {"deleted": task_id, "force": True, "async": True}

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    attempts = 0
    while attempts < 3:
        try:
            db.query(Image).filter(Image.task_id == task_id).delete(synchronize_session=False)
            db.query(Log).filter(Log.task_id == task_id).delete(synchronize_session=False)
            db.delete(task)
            db.commit()
            break
        except OperationalError as exc:
            db.rollback()
            attempts += 1
            if "locked" in str(exc).lower():
                time.sleep(0.2)
                continue
            raise
    # Remove files on disk asynchronously
    task_dir = os.path.join("./data/tasks", str(task_id))
    threading.Thread(target=_delete_task_dirs, args=([task_dir],), daemon=True).start()
    db_removed = attempts < 3
    if db_removed:
        processing.clear_cancelled(task_id)
    return {"deleted": task_id, "db_removed": db_removed}


@app.delete("/api/tasks")
def delete_all_tasks(
    force: bool = Query(True),
    db: Session = Depends(get_db)
):
    if force:
        processing.cancel_all_tasks()
        threading.Thread(target=_force_delete_all, daemon=True).start()
        return {"deleted": "all", "force": True, "async": True}

    tasks = db.query(Task).all()
    ids = [t.id for t in tasks]
    if ids:
        attempts = 0
        while attempts < 3:
            try:
                db.query(Image).filter(Image.task_id.in_(ids)).delete(synchronize_session=False)
                db.query(Log).filter(Log.task_id.in_(ids)).delete(synchronize_session=False)
                db.query(Task).delete()
                db.commit()
                break
            except OperationalError as exc:
                db.rollback()
                attempts += 1
                if "locked" in str(exc).lower():
                    time.sleep(0.3)
                    continue
                raise
    # remove files asynchronously
    base = "./data/tasks"
    task_dirs = [os.path.join(base, str(tid)) for tid in ids]
    threading.Thread(target=_delete_task_dirs, args=(task_dirs,), daemon=True).start()
    return {"deleted": ids, "force": False}

@app.post("/api/tasks/{task_id}/dedup")
def start_dedup(task_id: int, payload: Optional[DedupParamsPayload] = None, db: Session = Depends(get_db)):
    task = _get_task_or_404(db, task_id)
    _assert_idle(task)

    settings = load_app_settings(db)
    global_dedup = settings["dedup_params"]
    if payload:
        dedup_params = payload.model_dump()
    else:
        dedup_params = global_dedup

    if task.config is None:
        task.config = {}
    if dedup_params == global_dedup:
        task.config.pop("dedup_params", None)
    else:
        task.config["dedup_params"] = dedup_params
    
    # reset previous outputs for this task
    _reset_task_data(task, db)
    db.commit()
    
    # Start dedup with params
    def _run():
        processing.prepare_task(task_id)
        processing.dedup_task(task_id, dedup_params=dedup_params)
    processing.submit_task(_run, task_id=task_id)
    return {"status": "started", "stage": "de_duplication", "params": dedup_params, "reset": True}


@app.post("/api/tasks/{task_id}/crop")
def start_crop(task_id: int, db: Session = Depends(get_db)):
    task = _get_task_or_404(db, task_id)
    _assert_idle(task)
    processing.submit_task(processing.crop_task, task_id)
    return {"status": "started", "stage": "cropping"}


@app.post("/api/tasks/{task_id}/caption")
def start_caption(task_id: int, db: Session = Depends(get_db)):
    task = _get_task_or_404(db, task_id)
    _assert_idle(task)
    processing.submit_task(processing.caption_task, task_id)
    return {"status": "started", "stage": "caption"}


@app.post("/api/tasks/{task_id}/run-all")
def run_all(task_id: int, payload: Optional[DedupParamsPayload] = None, db: Session = Depends(get_db)):
    task = _get_task_or_404(db, task_id)
    _assert_idle(task)

    if payload:
        settings = load_app_settings(db)
        global_dedup = settings["dedup_params"]
        dedup_params = payload.model_dump()
        if task.config is None:
            task.config = {}
        if dedup_params == global_dedup:
            task.config.pop("dedup_params", None)
        else:
            task.config["dedup_params"] = dedup_params
        db.commit()

    processing.submit_task(processing.run_full_pipeline, task_id)
    return {"status": "started", "stage": "full"}


@app.get("/api/tasks/{task_id}/download")
def download_task(task_id: int, db: Session = Depends(get_db)):
    from fastapi.responses import FileResponse
    
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    export_path = task.export_path or os.path.join(f"./data/tasks/{task_id}/export", "train_package.zip")
    if not os.path.exists(export_path):
        raise HTTPException(status_code=404, detail="Export file not found")
    
    return FileResponse(export_path, filename=f"{task.name}.train_package.zip")


@app.post("/api/settings/test", response_model=SettingsTestResponse)
async def test_settings(request: Request):
    header_base = request.headers.get("X-Ext-Base-Url")
    header_key = request.headers.get("X-Ext-Api-Key")
    if not header_base:
        return SettingsTestResponse(ok=False, message="缺少 X-Ext-Base-Url", base_url=None)
    # Minimal ping - here we only validate header existence to avoid heavy calls
    return SettingsTestResponse(ok=True, message="已收到自定义配置（未实际请求外部服务）", base_url=header_base)


@app.get("/api/settings", response_model=AppSettingsResponse)
def get_app_settings(db: Session = Depends(get_db)):
    return load_app_settings(db)


@app.post("/api/settings", response_model=AppSettingsResponse)
def save_app_settings(payload: AppSettingsUpdate, db: Session = Depends(get_db)):
    if payload.dedup_params is not None:
        validated = DedupParamsPayload(**payload.dedup_params).model_dump()
        parsed = {key: validated[key] for key in payload.dedup_params.keys()}
    else:
        parsed = None
    return update_app_settings(
        db,
        caption_prompt=payload.caption_prompt,
        dedup_params=parsed,
        crop_output_size=payload.crop_output_size,
    )


@app.get("/api/tasks/{task_id}/images")
def get_task_images(
    task_id: int,
    selected: Optional[bool] = None,
    include_prompt: bool = False,
    db: Session = Depends(get_db)
):
    _get_task_or_404(db, task_id)
    query = db.query(Image).filter(Image.task_id == task_id)
    if selected is not None:
        query = query.filter(Image.selected == selected)
    
    images = query.all()

    # Add URLs to images
    result = []
    for img in images:
        # Ensure width/height可用
        if not img.width or not img.height:
            try:
                from PIL import Image as PILImage, ImageOps
                with PILImage.open(img.orig_path) as pil_img:
                    pil_img = ImageOps.exif_transpose(pil_img)
                    img.width, img.height = pil_img.size
                db.commit()
            except Exception:
                img.width = img.width or 1024
                img.height = img.height or 1024

        summary = _image_summary(img, task_id)
        meta = img.meta_json or {}

        # 附加原始/裁切路径与提示词信息
        summary["orig_path"] = img.orig_path
        summary["crop_path"] = img.crop_path
        summary["selected"] = img.selected
        summary["keep"] = summary.get("keep", img.selected)
        summary["has_prompt"] = bool(img.prompt_txt_path)
        if include_prompt:
            if img.prompt_txt_path and os.path.exists(img.prompt_txt_path):
                try:
                    with open(img.prompt_txt_path, "r", encoding="utf-8") as f:
                        summary["prompt_text"] = f.read()
                except Exception:
                    summary["prompt_text"] = None
            else:
                summary["prompt_text"] = None
        summary["meta_json"] = meta

        result.append(summary)
    
    return result


@app.get("/api/logs")
def get_logs(
    limit: int = Query(100, ge=1, le=500),
    task_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Log)
    if task_id:
        query = query.filter(Log.task_id == task_id)
    logs = query.order_by(Log.created_at.desc()).limit(limit).all()
    return [
        {
            "id": log.id,
            "task_id": log.task_id,
            "level": log.level,
            "message": log.message,
            "created_at": log.created_at,
        }
        for log in logs
    ]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=_expected_backend_host(), port=_expected_backend_port())
