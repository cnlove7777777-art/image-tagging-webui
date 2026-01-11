import json
import logging
import os
import zipfile
import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional

from PIL import Image as PILImage
from PIL import ImageFile, ImageOps
import imagehash
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.image import Image
from app.models.log import Log, LogLevel
from app.models.task import Task, TaskStage, TaskStatus
from app.services.app_settings import get_app_settings
from app.services.image_processing import (
    calculate_sharpness,
    cluster_keep_topk,
    crop_1024_from_original,
    generate_preview,
)
 
from app.services.model_client import ModelClient
from .celery_app import celery_app

logger = logging.getLogger(__name__)

# Create database engine
connect_args = {}
if "sqlite" in settings.DATABASE_URL:
    connect_args = {"check_same_thread": False, "timeout": 30}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Set PIL settings
ImageFile.LOAD_TRUNCATED_IMAGES = True
PILImage.MAX_IMAGE_PIXELS = settings.MAX_IMAGE_PIXELS


def _ensure_task_dirs(task_id: int) -> Dict[str, str]:
    base = f"./data/tasks/{task_id}"
    dirs = {
        "task": base,
        "unpack": os.path.join(base, "unpack"),
        "previews": os.path.join(base, "previews"),
        "crops": os.path.join(base, "crops"),
        "images": os.path.join(base, "crops", "images"),
        "txt": os.path.join(base, "crops", "txt"),
        "export": os.path.join(base, "export"),
    }
    for path in dirs.values():
        os.makedirs(path, exist_ok=True)
    return dirs


def _add_log(db, task_id: Optional[int], level: LogLevel, message: str) -> None:
    log = Log(task_id=task_id, level=level, message=message)
    db.add(log)
    db.commit()


def _mark_error(db, task: Task, message: str) -> None:
    task.status = TaskStatus.ERROR
    task.stage = TaskStage.FINISHED
    task.progress = 0
    task.message = f"Error: {message}"
    db.commit()
    _add_log(db, task.id, LogLevel.CRITICAL, message)


def _load_images(db, task_id: int) -> List[Image]:
    return db.query(Image).filter(Image.task_id == task_id).all()


def prepare_task(task_id: int) -> None:
    """Unpack zip and create image records + previews. Stop before heavy steps."""
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return

        dirs = _ensure_task_dirs(task_id)
        task.status = TaskStatus.PROCESSING
        task.stage = TaskStage.UNPACKING
        task.progress = 5
        task.message = "Unpacking archive..."
        db.commit()

        unpacked_files: List[str] = []
        # Reuse existing unpack dir to avoid repeated extraction on rerun
        for root, _, files in os.walk(dirs["unpack"]):
            for fname in files:
                unpacked_files.append(os.path.join(root, fname))

        if not unpacked_files:
            with zipfile.ZipFile(task.upload_path, "r") as zip_ref:
                for member in zip_ref.infolist():
                    if member.filename.startswith("../") or "..\\" in member.filename:
                        continue
                    if member.is_dir():
                        continue
                    zip_ref.extract(member, dirs["unpack"])
                    unpacked_files.append(os.path.join(dirs["unpack"], member.filename))
            _add_log(db, task_id, LogLevel.INFO, f"已解压 {len(unpacked_files)} 个文件")
        else:
            _add_log(db, task_id, LogLevel.INFO, f"复用已解压文件 {len(unpacked_files)} 个（未重新解压）")

        image_exts = [".jpg", ".jpeg", ".png", ".webp"]
        image_files = [f for f in unpacked_files if os.path.splitext(f.lower())[1] in image_exts]

        task.stats = {
            "total_files": len(unpacked_files),
            "image_files": len(image_files),
            "kept_files": len(image_files),
            "processed_files": 0,
        }
        task.stage = TaskStage.PREVIEW_GENERATION
        task.progress = 20
        task.message = "Generating previews..."
        db.commit()

        existing = {img.orig_path: img for img in _load_images(db, task_id)}

        for idx, img_path in enumerate(image_files):
            try:
                preview_path = generate_preview(
                    img_path,
                    dirs["previews"],
                    max_side=settings.PREVIEW_MAX_SIDE,
                    quality=settings.PREVIEW_JPEG_QUALITY,
                )
                image = existing.get(img_path)
                meta = image.meta_json if image and image.meta_json else {}
                meta.update({"prepared": True})
                if image:
                    image.preview_path = preview_path
                    image.selected = True
                    image.crop_path = None
                    image.prompt_txt_path = None
                    image.meta_json = meta
                else:
                    image = Image(
                        task_id=task_id,
                        orig_name=os.path.basename(img_path),
                        orig_path=img_path,
                        preview_path=preview_path,
                        selected=True,
                        meta_json=meta,
                    )
                    db.add(image)

                task.progress = 20 + int(((idx + 1) / max(1, len(image_files))) * 10)
                db.commit()
            except Exception as exc:
                _add_log(db, task_id, LogLevel.ERROR, f"处理图片失败 {img_path}: {exc}")
            
            # 获取图片尺寸信息
            try:
                with PILImage.open(img_path) as pil_meta:
                    w, h = pil_meta.size
                _add_log(db, task_id, LogLevel.INFO, f"预览生成 {os.path.basename(img_path)} ({idx+1}/{len(image_files)}) 尺寸:{w}x{h}")
            except Exception as exc:
                w, h = (0, 0)
                _add_log(db, task_id, LogLevel.ERROR, f"获取图片尺寸失败 {img_path}: {exc}")

        task.status = TaskStatus.PENDING
        task.stage = TaskStage.PREVIEW_GENERATION
        task.progress = max(task.progress, 30)
        task.message = "准备完成，等待去重开始"
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Prepare task failed")
        if "task" in locals():
            _mark_error(db, task, str(exc))
    finally:
        db.close()


def _collect_image_features(images: List[Image]) -> List[Dict]:
    image_data: List[Dict] = []
    for img in images:
        try:
            with PILImage.open(img.orig_path) as pil:
                pil = ImageOps.exif_transpose(pil)
                thumb = pil.copy()
                thumb.thumbnail((512, 512))
                phash = str(imagehash.phash(thumb))
                sharpness = calculate_sharpness(thumb)
                width, height = pil.size

                with open(img.orig_path, "rb") as f:
                    md5 = hashlib.md5(f.read()).hexdigest()

                image_data.append(
                    {
                        "record": img,
                        "path": img.orig_path,
                        "phash": phash,
                        "sharpness": sharpness,
                        "md5": md5,
                        "width": width,
                        "height": height,
                    }
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Feature extraction failed for %s: %s", img.orig_path, exc)
    return image_data


def dedup_task(task_id: int, auto_continue: bool = False, dedup_params: dict = None) -> None:
    """Run de-duplication and mark selections."""
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return

        task.status = TaskStatus.PROCESSING
        task.stage = TaskStage.DE_DUPLICATION
        task.progress = max(task.progress, 35)
        task.message = "去重中..."
        db.commit()

        images = _load_images(db, task_id)
        image_paths = [img.orig_path for img in images if img.orig_path]
        
        if not image_paths:
            raise ValueError("No images found for deduplication")
        
        # Import dedup_people here to avoid circular imports
        from app.services.dedup_people import extract_features, cluster, pick_kept, _cosine_sim, _face_ssim
        
        # Extract features using dedup_people
        metas = extract_features(
            image_paths,
            max_side_analysis=1024,
            max_side_small=512,
            min_pose_conf=0.35,
            max_workers=4,
        )
        
        # Set default params if not provided
        if dedup_params is None:
            dedup_params = {}
    
        # Cluster using dedup_people with provided params
        clusters = cluster(
            metas,
            face_sim_th1=dedup_params.get("face_sim_th1", 0.80),
            face_sim_th2=dedup_params.get("face_sim_th2", 0.85),
            pose_sim_th=dedup_params.get("pose_sim_th", 0.98),
            face_ssim_th1=dedup_params.get("face_ssim_th1", 0.95),
            face_ssim_th2=dedup_params.get("face_ssim_th2", 0.90),
            bbox_tol_c=dedup_params.get("bbox_tol_c", 0.04),
            bbox_tol_wh=dedup_params.get("bbox_tol_wh", 0.06),
            face_crop_expand=1.2,
        )
    
        # Pick kept images
        kept_indices = pick_kept(
            clusters,
            metas,
            keep_per_cluster=dedup_params.get("keep_per_cluster", settings.KEEP_PER_CLUSTER),
        )
        
        # Create mapping from path to keep status
        kept_paths = {image_paths[i] for i in kept_indices}

        task.stats = task.stats or {}
        task.stats["kept_files"] = len(kept_paths)
        
        # Debug: Log feature extraction statistics
        face_ok = sum(1 for m in metas if m.face_emb is not None)
        pose_ok = sum(1 for m in metas if m.pose_vec is not None)
        logger.info(f"Dedup Task {task_id}: Face OK: {face_ok}/{len(metas)}, Pose OK: {pose_ok}/{len(metas)}")
        
        # Debug: Log similarity metrics for adjacent frames
        if len(metas) > 1:
            for i in range(min(5, len(metas)-1)):  # Log first 5 pairs
                m1, m2 = metas[i], metas[i+1]
                # Check if face_emb is not None, not using 'and' on arrays
                face_sim = _cosine_sim(m1.face_emb, m2.face_emb) if m1.face_emb is not None and m2.face_emb is not None else None
                pose_sim = _cosine_sim(m1.pose_vec, m2.pose_vec) if m1.pose_vec is not None and m2.pose_vec is not None else None
                try:
                    face_ssim = _face_ssim(m1, m2, face_crop_expand=1.2) if m1.small_gray is not None and m2.small_gray is not None else None
                except Exception:
                    face_ssim = None
                # Format values safely, handling None values
                face_sim_str = f"{face_sim:.4f}" if face_sim is not None else "None"
                pose_sim_str = f"{pose_sim:.4f}" if pose_sim is not None else "None"
                face_ssim_str = f"{face_ssim:.4f}" if face_ssim is not None else "None"
                logger.info(f"Dedup Task {task_id}: Frame {i+1} vs {i+2} - Face Sim: {face_sim_str}, Pose Sim: {pose_sim_str}, Face SSIM: {face_ssim_str}")
        
        # Debug: Log cluster statistics
        logger.info(f"Dedup Task {task_id}: Clusters: {len(clusters)}, Kept images: {len(kept_indices)}, Total images: {len(metas)}")

        for idx, img in enumerate(images):
            if not img.orig_path:
                continue
                
            keep = img.orig_path in kept_paths
            img.selected = keep
            
            # Update image width and height if not set
            if not img.width or not img.height:
                try:
                    from PIL import Image as PILImage
                    with PILImage.open(img.orig_path) as pil_img:
                        img.width, img.height = pil_img.size
                except Exception:
                    # If we can't get the size, set a default
                    img.width = 1024
                    img.height = 1024
            
            # Update image metadata
            meta = img.meta_json or {}
            meta["dedup"] = {
                "kept": keep,
            }
            
            # Add pose and face info to metadata
            for i, path in enumerate(image_paths):
                if path == img.orig_path:
                    meta["has_face"] = metas[i].face_emb is not None
                    meta["face_conf"] = metas[i].face_conf
                    meta["has_pose"] = metas[i].pose_vec is not None
                    meta["pose_conf"] = metas[i].pose_conf
                    # subject area: prefer pose-derived body height, fallback to face bbox area
                    sar = metas[i].body_height_ratio
                    if sar is None and metas[i].face_bbox_norm:
                        _, _, bw, bh = metas[i].face_bbox_norm
                        sar = max(0.0, min(1.0, bw * bh))
                    meta["subject_area_ratio"] = sar
                    meta["shot_type"] = metas[i].shot_type
                    meta["is_full_body"] = metas[i].is_full_body
                    
                    # Add cluster ID to metadata
                    cluster_id = None
                    for j, cluster in enumerate(clusters):
                        if i in cluster:
                            cluster_id = j
                            break
                    meta["dedup"]["cluster_id"] = cluster_id
                    break
            
            img.meta_json = meta
            task.progress = 40 + int(((idx + 1) / max(1, len(images))) * 5)
            _add_log(
                db,
                task_id,
                LogLevel.INFO,
                f"鍘婚噸{'淇濈暀' if keep else '涓㈠純'} {img.orig_name} "
                f"face_conf={meta.get('face_conf', 0):.2f} "
                f"pose_conf={meta.get('pose_conf', 0):.2f} "
                f"鍗犳瘮={meta.get('subject_area_ratio') if meta.get('subject_area_ratio') is not None else '-'} "
                f"cluster={meta.get('dedup', {}).get('cluster_id')}"
            )
            db.commit()

        task.progress = max(task.progress, 50)
        if auto_continue:
            db.commit()
            db.close()
            crop_task(task_id, auto_continue=True)
            return

        task.status = TaskStatus.PENDING
        task.message = "去重完成，请在弹窗中确认要保留的图片"
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Dedup failed")
        if "task" in locals():
            _mark_error(db, task, str(exc))
    finally:
        try:
            db.close()
        except Exception:
            pass


def crop_task(task_id: int, auto_continue: bool = False) -> None:
    """Run focus detection + cropping for selected images."""
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return

        dirs = _ensure_task_dirs(task_id)
        task.status = TaskStatus.PROCESSING
        task.stage = TaskStage.FOCUS_DETECTION
        task.progress = max(task.progress, 55)
        task.message = "检测主体并计算裁切框..."
        db.commit()

        model_client = ModelClient(
            api_key=task.api_key or settings.MODELSCOPE_TOKEN,
            base_url=task.base_url or settings.BASE_URL,
            model=task.focus_model,
        )

        images = db.query(Image).filter(Image.task_id == task_id, Image.selected == True).all()  # noqa: E712
        total = max(1, len(images))

        for idx, image in enumerate(images):
            try:
                focus_result = model_client.get_focus_point(image.preview_path or image.orig_path)
                meta = image.meta_json or {}
                meta["focus"] = focus_result
                usable = focus_result.get("usable", True)
                reject_reason = focus_result.get("reject_reason")
                bbox = focus_result.get("bbox") or {}
                meta["quality"] = {"usable": usable, "reject_reason": reject_reason}
                if bbox:
                    meta["subject_area_ratio"] = max(
                        0.0,
                        min(1.0, (bbox.get("x2", 0) - bbox.get("x1", 0)) * (bbox.get("y2", 0) - bbox.get("y1", 0))),
                    )
                if meta.get("focus") and meta.get("subject_area_ratio") is not None:
                    if not meta["focus"].get("shot_type"):
                        ratio = meta["subject_area_ratio"]
                        if ratio >= 0.4:
                            meta["focus"]["shot_type"] = "closeup"
                        elif ratio >= 0.2:
                            meta["focus"]["shot_type"] = "medium"
                        else:
                            meta["focus"]["shot_type"] = "long"
                    if "confidence" not in meta["focus"]:
                        meta["focus"]["confidence"] = 0.0

                image.meta_json = meta

                if not usable:
                    image.selected = False
                    meta["decision"] = {"keep": False, "reason": reject_reason}
                    image.meta_json = meta
                    db.commit()
                    continue

                cx = focus_result.get("focus_point", {}).get("x", 0.5)
                cy = focus_result.get("focus_point", {}).get("y", 0.5)
                side = focus_result.get("focus_point", {}).get("side")
                if side is None and bbox:
                    bw = bbox.get("x2", 0) - bbox.get("x1", 0)
                    bh = bbox.get("y2", 0) - bbox.get("y1", 0)
                    iw, ih = image.width or 0, image.height or 0
                    if (not iw or not ih) and image.orig_path:
                        try:
                            with PILImage.open(image.orig_path) as pil_img:
                                iw, ih = pil_img.size
                                image.width, image.height = iw, ih
                        except Exception:
                            iw, ih = 0, 0
                    if bw > 0 and bh > 0 and iw > 0 and ih > 0:
                        side = max(bw * iw, bh * ih) / max(1, min(iw, ih))
                    else:
                        side = max(bw, bh)
                if side is None:
                    side = 1.0
                side = max(0.05, min(1.0, side))
                crop_path = crop_1024_from_original(
                    image.orig_path,
                    cx,
                    cy,
                    dirs["images"],
                    quality=95,
                    side=side,
                )
                image.crop_path = crop_path
                meta["crop_square_model"] = {"cx": cx, "cy": cy, "side": side, "source": "model"}
                image.meta_json = meta
                _add_log(
                    db,
                    task_id,
                    LogLevel.INFO,
                    f"裁切完成 {image.orig_name} cx={cx:.3f}, cy={cy:.3f}, side={side:.3f}, usable={usable}"
                )
                db.commit()
            except Exception as exc:  # noqa: BLE001
                _add_log(db, task_id, LogLevel.ERROR, f"裁切失败 {image.orig_name}: {exc}")

            task.progress = 60 + int(((idx + 1) / total) * 10)
            task.message = f"裁切进度 {idx+1}/{total}"
            db.commit()

        task.stats = task.stats or {}
        task.stats["processed_files"] = len([img for img in images if img.crop_path and img.selected])

        if auto_continue:
            db.commit()
            db.close()
            caption_task(task_id)
            return

        task.status = TaskStatus.PENDING
        task.stage = TaskStage.CROPPING
        task.message = "裁切完成，请查看预览"
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Crop failed")
        if "task" in locals():
            _mark_error(db, task, str(exc))
    finally:
        try:
            db.close()
        except Exception:
            pass


def caption_task(task_id: int) -> None:
    """Generate training captions and package dataset."""
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return

        dirs = _ensure_task_dirs(task_id)
        task.status = TaskStatus.PROCESSING
        task.stage = TaskStage.TAGGING
        task.progress = max(task.progress, 75)
        task.message = "生成训练提示词..."
        db.commit()

        caption_prompt = get_app_settings(db)["caption_prompt"]
        model_client = ModelClient(
            api_key=task.api_key or settings.MODELSCOPE_TOKEN,
            base_url=task.base_url or settings.BASE_URL,
            model=task.tag_model,
        )

        images = db.query(Image).filter(Image.task_id == task_id, Image.selected == True).all()  # noqa: E712
        total = max(1, len(images))

        for idx, image in enumerate(images):
            if not image.crop_path:
                continue
            try:
                caption = model_client.generate_caption(image.crop_path, prompt=caption_prompt)
                txt_filename = os.path.splitext(os.path.basename(image.crop_path))[0] + ".txt"
                txt_path = os.path.join(dirs["txt"], txt_filename)
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(caption)
                image.prompt_txt_path = txt_path
                meta = image.meta_json or {}
                meta["caption"] = caption
                image.meta_json = meta
                _add_log(db, task_id, LogLevel.INFO, f"提示词生成 {image.orig_name} -> {os.path.basename(txt_path)}")
                db.commit()
            except Exception as exc:  # noqa: BLE001
                _add_log(db, task_id, LogLevel.ERROR, f"提示词生成失败 {image.orig_name}: {exc}")
            task.progress = 80 + int(((idx + 1) / total) * 10)
            task.message = f"提示词进度 {idx+1}/{total}"
            db.commit()
        task.stage = TaskStage.PACKAGING
        task.message = "打包训练集..."
        db.commit()

        manifest = {
            "version": "1.1",
            "task_id": task_id,
            "task_name": task.name,
            "created_at": datetime.utcnow().isoformat(),
            "focus_model": task.focus_model,
            "tag_model": task.tag_model,
            "images": [],
        }

        kept_images = db.query(Image).filter(
            Image.task_id == task_id, Image.selected == True, Image.crop_path.isnot(None)
        ).all()  # noqa: E712

        for img in kept_images:
            manifest["images"].append(
                {
                    "orig_name": img.orig_name,
                    "md5": img.md5,
                    "focus_point": (img.meta_json or {}).get("focus", {}).get("focus_point"),
                    "crop_path": os.path.basename(img.crop_path) if img.crop_path else None,
                    "prompt": (img.meta_json or {}).get("caption", ""),
                }
            )

        manifest_path = os.path.join(dirs["export"], "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        train_package_path = os.path.join(dirs["export"], "train_package.zip")
        with zipfile.ZipFile(train_package_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for img in kept_images:
                if img.crop_path:
                    zipf.write(img.crop_path, f"images/{os.path.basename(img.crop_path)}")
                if img.prompt_txt_path:
                    zipf.write(img.prompt_txt_path, f"txt/{os.path.basename(img.prompt_txt_path)}")
            zipf.write(manifest_path, "manifest.json")

        task.stats = task.stats or {}
        task.stats["processed_files"] = len(kept_images)
        task.export_path = train_package_path
        task.status = TaskStatus.COMPLETED
        task.stage = TaskStage.FINISHED
        task.progress = 100
        task.message = "完成！可以下载或预览结果"
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Caption/package failed")
        if "task" in locals():
            _mark_error(db, task, str(exc))
    finally:
        try:
            db.close()
        except Exception:
            pass


def run_full_pipeline(task_id: int) -> None:
    """One-click flow from unpack -> dedup -> crop -> caption."""
    prepare_task(task_id)
    dedup_task(task_id, auto_continue=True)


@celery_app.task(name="process_task")
def process_task(task_id: int):
    run_full_pipeline(task_id)

