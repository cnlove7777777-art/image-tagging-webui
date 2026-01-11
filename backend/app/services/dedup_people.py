from __future__ import annotations

import argparse
import math
import os
import threading
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageOps

_THREAD_LOCAL = threading.local()


@dataclass
class ImageMeta:
    path: str
    face_bbox_norm: Optional[Tuple[float, float, float, float]]
    face_conf: float
    face_emb: Optional[np.ndarray]
    pose_vec: Optional[np.ndarray]
    pose_conf: float
    sharpness: float
    small_gray: Optional[np.ndarray]
    errors: List[str]
    # 添加人物比例相关字段
    body_height_ratio: Optional[float] = None  # 人物高度占画面高度的比例
    is_full_body: bool = False  # 是否为全身照
    shot_type: str = "unknown"  # 拍摄类型：closeup, medium, long


def _get_face_app():
    if getattr(_THREAD_LOCAL, "face_app", None) is None:
        from insightface.app import FaceAnalysis

        app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=0, det_size=(640, 640))
        _THREAD_LOCAL.face_app = app
    return _THREAD_LOCAL.face_app


def _get_pose_model():
    if getattr(_THREAD_LOCAL, "pose_model", None) is None:
        import mediapipe as mp

        _THREAD_LOCAL.pose_model = mp.solutions.pose.Pose(
            static_image_mode=True,
            model_complexity=1,
            enable_segmentation=False,
            min_detection_confidence=0.5,
        )
    return _THREAD_LOCAL.pose_model


def _resize_max_side(img: Image.Image, max_side: int) -> Image.Image:
    w, h = img.size
    scale = min(1.0, max_side / max(w, h))
    if scale >= 1.0:
        return img.copy()
    return img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)


def _laplacian_sharpness(gray: np.ndarray) -> float:
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    return float(lap.var())


def _normalize_vec(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    if norm == 0:
        return vec
    return vec / norm


def _select_best_face(faces):
    if not faces:
        return None
    best = None
    best_score = -1.0
    for face in faces:
        bbox = face.bbox
        area = float(max(0.0, (bbox[2] - bbox[0])) * max(0.0, (bbox[3] - bbox[1])))
        score = float(getattr(face, "det_score", 0.0))
        key = score * 10000.0 + area
        if key > best_score:
            best_score = key
            best = face
    return best


def _face_bbox_norm(face, width: int, height: int) -> Optional[Tuple[float, float, float, float]]:
    if face is None:
        return None
    x1, y1, x2, y2 = face.bbox
    x1 = max(0.0, min(float(x1), float(width)))
    y1 = max(0.0, min(float(y1), float(height)))
    x2 = max(0.0, min(float(x2), float(width)))
    y2 = max(0.0, min(float(y2), float(height)))
    w = max(0.0, x2 - x1)
    h = max(0.0, y2 - y1)
    if w == 0 or h == 0:
        return None
    cx = x1 + w / 2.0
    cy = y1 + h / 2.0
    return (cx / width, cy / height, w / width, h / height)


def _extract_pose_vec(img_rgb: np.ndarray, min_pose_conf: float) -> Tuple[Optional[np.ndarray], float, Optional[float]]:
    pose = _get_pose_model()
    results = pose.process(img_rgb)
    if not results.pose_landmarks:
        return None, 0.0, None

    landmarks = results.pose_landmarks.landmark
    if len(landmarks) < 33:
        return None, 0.0, None

    left = landmarks[11]
    right = landmarks[12]
    if left.visibility <= 0.5 or right.visibility <= 0.5:
        return None, 0.0, None

    cx = (left.x + right.x) / 2.0
    cy = (left.y + right.y) / 2.0
    shoulder_w = math.hypot(left.x - right.x, left.y - right.y)
    if shoulder_w <= 1e-6:
        return None, 0.0, None

    coords = []
    valid = 0
    
    # 计算人物高度比例
    body_height_ratio = None
    
    # 尝试获取头部和脚部关键点的y坐标
    # 头部使用鼻子(0)，脚部使用左右脚踝(27, 28)
    nose = landmarks[0]
    left_ankle = landmarks[27]
    right_ankle = landmarks[28]
    
    # 检查关键点可见性
    if nose.visibility > 0.5 and (left_ankle.visibility > 0.5 or right_ankle.visibility > 0.5):
        # 使用可见的脚踝
        if left_ankle.visibility > right_ankle.visibility:
            ankle_y = left_ankle.y
        else:
            ankle_y = right_ankle.y
        
        # 计算人物高度（从鼻子到脚踝的y距离）
        height_pixels = ankle_y - nose.y
        # 确保height_pixels是标量
        if isinstance(height_pixels, (np.ndarray, list)):
            height_pixels = float(np.mean(height_pixels))
        if height_pixels > 0:
            # 人物高度占画面高度的比例
            body_height_ratio = height_pixels
    
    # 如果没有脚踝关键点，尝试使用膝盖(25, 26)
    elif nose.visibility > 0.5:
        left_knee = landmarks[25]
        right_knee = landmarks[26]
        
        if left_knee.visibility > 0.5 or right_knee.visibility > 0.5:
            # 使用可见的膝盖
            if left_knee.visibility > right_knee.visibility:
                knee_y = left_knee.y
            else:
                knee_y = right_knee.y
            
            # 计算人物高度（从鼻子到膝盖的y距离）
            # 假设膝盖到脚踝占全身的1/3，所以乘以1.5来估算全身高度
            height_pixels = (knee_y - nose.y) * 1.5
            # 确保height_pixels是标量
            if isinstance(height_pixels, (np.ndarray, list)):
                height_pixels = float(np.mean(height_pixels))
            if height_pixels > 0:
                body_height_ratio = height_pixels
    
    # 归一化关键点坐标
    for lm in landmarks:
        if lm.visibility > 0.5:
            coords.append((lm.x - cx) / shoulder_w)
            coords.append((lm.y - cy) / shoulder_w)
            valid += 1

    pose_conf = valid / float(len(landmarks))
    if valid == 0 or pose_conf < min_pose_conf:
        return None, 0.0, body_height_ratio

    vec = np.array(coords, dtype=np.float32)
    return _normalize_vec(vec), pose_conf, body_height_ratio


def extract_features(
    paths: List[str],
    max_side_analysis: int = 1024,
    max_side_small: int = 512,
    min_pose_conf: float = 0.35,
    max_workers: int = 4,
) -> List[ImageMeta]:
    def _process_one(path: str) -> ImageMeta:
        errors: List[str] = []
        face_bbox_norm = None
        face_conf = 0.0
        face_emb = None
        pose_vec = None
        pose_conf = 0.0
        sharpness = 0.0
        small_gray = None
        body_height_ratio = None

        try:
            # 尝试打开图片，使用更可靠的错误处理
            img = ImageOps.exif_transpose(Image.open(path))
        except Exception as exc:
            return ImageMeta(
                path=path,
                face_bbox_norm=None,
                face_conf=0.0,
                face_emb=None,
                pose_vec=None,
                pose_conf=0.0,
                sharpness=0.0,
                small_gray=None,
                errors=[f"open_failed:{exc}"],
                body_height_ratio=body_height_ratio,
                is_full_body=False,
                shot_type="unknown",
            )

        try:
            # 调整图片大小
            analysis_img = _resize_max_side(img, max_side_analysis)
            small_img = _resize_max_side(img, max_side_small)

            # 生成small_gray用于全局SSIM计算，确保即使其他特征提取失败，也能进行基本去重
            try:
                small_rgb = np.asarray(small_img.convert("RGB"))
                small_gray = cv2.cvtColor(small_rgb, cv2.COLOR_RGB2GRAY)
                sharpness = _laplacian_sharpness(small_gray)
            except Exception as exc:
                errors.append(f"small_gray_failed:{exc}")
                # 即使失败，也创建一个默认的small_gray，确保后续去重能进行
                small_gray = np.zeros((100, 100), dtype=np.uint8)
                sharpness = 0.0

            # 特征提取部分，使用单独的try-except，确保即使失败也能返回部分结果
            try:
                analysis_rgb = np.asarray(analysis_img.convert("RGB"))
                analysis_bgr = cv2.cvtColor(analysis_rgb, cv2.COLOR_RGB2BGR)

                # 人脸特征提取
                try:
                    face_app = _get_face_app()
                    faces = face_app.get(analysis_bgr)
                    face = _select_best_face(faces)

                    if face is not None:
                        face_conf = float(getattr(face, "det_score", 0.0))
                        face_bbox_norm = _face_bbox_norm(face, analysis_img.size[0], analysis_img.size[1])
                        emb = getattr(face, "embedding", None)
                        if emb is not None:
                            face_emb = _normalize_vec(np.asarray(emb, dtype=np.float32))
                        else:
                            errors.append("face_no_embedding")
                    else:
                        errors.append("no_face")
                except Exception as exc:
                    errors.append(f"face_extract_failed:{exc}")

                # 姿势特征提取
                try:
                    pose_vec, pose_conf, body_height_ratio = _extract_pose_vec(analysis_rgb, min_pose_conf=min_pose_conf)
                    if pose_vec is None:
                        errors.append("no_pose")
                except Exception as exc:
                    errors.append(f"pose_extract_failed:{exc}")
            except Exception as exc:
                errors.append(f"feature_extract_failed:{exc}")
            
            # 确定拍摄类型和是否为全身照
            shot_type = "unknown"
            is_full_body = False
            
            if body_height_ratio is not None:
                # 判断拍摄类型
                # body_height_ratio是人物头部到脚踝的归一化距离（范围0-1）
                # 完整站立的人物这个值应该接近1.0
                if body_height_ratio < 0.3:
                    shot_type = "closeup"  # 特写：人物高度占画面30%以下（只显示头部/上半身）
                elif body_height_ratio < 0.6:
                    shot_type = "medium"   # 中景：人物高度占画面30%-60%（显示上半身/半身）
                else:
                    shot_type = "long"      # 远景：人物高度占画面60%以上（显示完整身体）
                    is_full_body = True     # 人物高度占比高，通常包含完整身体
        except Exception as exc:
            errors.append(f"process_failed:{exc}")
        finally:
            try:
                img.close()
            except Exception:
                pass

        return ImageMeta(
            path=path,
            face_bbox_norm=face_bbox_norm,
            face_conf=face_conf,
            face_emb=face_emb,
            pose_vec=pose_vec,
            pose_conf=pose_conf,
            sharpness=sharpness,
            small_gray=small_gray,
            errors=errors,
            body_height_ratio=body_height_ratio,
            is_full_body=is_full_body,
            shot_type=shot_type,
        )

    if max_workers <= 1:
        return [_process_one(p) for p in paths]

    from concurrent.futures import ThreadPoolExecutor

    metas: List[ImageMeta] = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for meta in ex.map(_process_one, paths):
            metas.append(meta)
    return metas


def _cosine_sim(a: Optional[np.ndarray], b: Optional[np.ndarray]) -> float:
    if a is None or b is None:
        return 0.0
    # Check if arrays have the same shape
    if a.shape != b.shape:
        return 0.0
    result = np.dot(a, b)
    # Ensure result is a scalar
    if isinstance(result, np.ndarray):
        result = result.item()
    return float(result)


def _bbox_close(
    a: Optional[Tuple[float, float, float, float]],
    b: Optional[Tuple[float, float, float, float]],
    tol_c: float,
    tol_wh: float,
) -> bool:
    if a is None or b is None:
        return False
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return (
        abs(ax - bx) <= tol_c
        and abs(ay - by) <= tol_c
        and abs(aw - bw) <= tol_wh
        and abs(ah - bh) <= tol_wh
    )


def _expand_bbox_norm(
    bbox: Tuple[float, float, float, float], expand: float
) -> Tuple[float, float, float, float]:
    cx, cy, w, h = bbox
    w *= expand
    h *= expand
    return cx, cy, min(1.0, w), min(1.0, h)


def _crop_face(gray: np.ndarray, bbox: Tuple[float, float, float, float]) -> Optional[np.ndarray]:
    h, w = gray.shape[:2]
    cx, cy, bw, bh = bbox
    bw = max(0.001, min(1.0, bw))
    bh = max(0.001, min(1.0, bh))
    x1 = int((cx - bw / 2.0) * w)
    y1 = int((cy - bh / 2.0) * h)
    x2 = int((cx + bw / 2.0) * w)
    y2 = int((cy + bh / 2.0) * h)
    x1 = max(0, min(x1, w - 1))
    y1 = max(0, min(y1, h - 1))
    x2 = max(1, min(x2, w))
    y2 = max(1, min(y2, h))
    if x2 <= x1 or y2 <= y1:
        return None
    crop = gray[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    return crop


def _ssim(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape != b.shape:
        return 0.0
    a = a.astype(np.float32)
    b = b.astype(np.float32)
    mu_a = a.mean()
    mu_b = b.mean()
    var_a = a.var()
    var_b = b.var()
    cov = ((a - mu_a) * (b - mu_b)).mean()
    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2
    num = (2 * mu_a * mu_b + c1) * (2 * cov + c2)
    den = (mu_a ** 2 + mu_b ** 2 + c1) * (var_a + var_b + c2)
    # Ensure num and den are scalars
    if isinstance(num, np.ndarray):
        num = num.item()
    if isinstance(den, np.ndarray):
        den = den.item()
    if den == 0:
        return 0.0
    return float(num / den)


def _face_ssim(
    a: ImageMeta,
    b: ImageMeta,
    face_crop_expand: float,
    target_size: int = 256,
) -> float:
    if a.small_gray is None or b.small_gray is None:
        return 0.0
    if a.face_bbox_norm is None or b.face_bbox_norm is None:
        return 0.0

    bbox_a = _expand_bbox_norm(a.face_bbox_norm, face_crop_expand)
    bbox_b = _expand_bbox_norm(b.face_bbox_norm, face_crop_expand)
    crop_a = _crop_face(a.small_gray, bbox_a)
    crop_b = _crop_face(b.small_gray, bbox_b)
    if crop_a is None or crop_b is None:
        return 0.0

    crop_a = cv2.resize(crop_a, (target_size, target_size), interpolation=cv2.INTER_AREA)
    crop_b = cv2.resize(crop_b, (target_size, target_size), interpolation=cv2.INTER_AREA)
    return _ssim(crop_a, crop_b)


def is_duplicate(
    meta_i: ImageMeta,
    meta_j: ImageMeta,
    face_sim_th1: float = 0.58,
    face_sim_th2: float = 0.64,
    pose_sim_th: float = 0.85,
    face_ssim_th1: float = 0.88,
    face_ssim_th2: float = 0.90,
    bbox_tol_c: float = 0.10,
    bbox_tol_wh: float = 0.18,
    face_crop_expand: float = 1.2,
) -> bool:
    """判断两张图片是否重复
    
    Args:
        meta_i: 第一张图片的元数据
        meta_j: 第二张图片的元数据
        face_sim_th1: 人脸特征相似度阈值1
        face_sim_th2: 人脸特征相似度阈值2
        pose_sim_th: 姿势相似度阈值
        face_ssim_th1: 人脸结构相似度阈值1
        face_ssim_th2: 人脸结构相似度阈值2
        bbox_tol_c: 边界框中心位置容差
        bbox_tol_wh: 边界框大小容差
        face_crop_expand: 人脸裁剪扩展系数
    
    Returns:
        bool: 两张图片是否重复
    """
    # 计算人脸相似度
    face_sim = _cosine_sim(meta_i.face_emb, meta_j.face_emb)
    
    # 计算姿势相似度
    pose_sim = _cosine_sim(meta_i.pose_vec, meta_j.pose_vec) if meta_i.pose_vec is not None and meta_j.pose_vec is not None else None
    
    # 计算人脸SSIM
    face_ssim = _face_ssim(meta_i, meta_j, face_crop_expand=face_crop_expand)
    
    # Case 1：人脸特征可用
    if meta_i.face_emb is not None and meta_j.face_emb is not None:
        # 强一致：人脸相似度很高，直接视为重复
        if face_sim >= face_sim_th2:
            return True
        
        # 中一致：人脸相似度较高，结合其他条件
        if face_sim >= face_sim_th1:
            # 条件1：人脸SSIM高
            if face_ssim >= face_ssim_th1:
                return True
            
            # 条件2：姿势相似度高
            if pose_sim is not None and pose_sim >= pose_sim_th:
                return True
    
    # Case 2：使用全局SSIM进行降级去重
    try:
        if meta_i.small_gray is not None and meta_j.small_gray is not None:
            # 计算全局SSIM
            global_ssim = _ssim(meta_i.small_gray, meta_j.small_gray)
            if global_ssim >= 0.90:
                return True
    except Exception:
        pass
    
    return False


class _DSU:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x: int, y: int) -> None:
        rx = self.find(x)
        ry = self.find(y)
        if rx == ry:
            return
        if self.rank[rx] < self.rank[ry]:
            self.parent[rx] = ry
        elif self.rank[rx] > self.rank[ry]:
            self.parent[ry] = rx
        else:
            self.parent[ry] = rx
            self.rank[rx] += 1


def cluster(
    metas: List[ImageMeta],
    face_sim_th1: float = 0.58,
    face_sim_th2: float = 0.64,
    pose_sim_th: float = 0.85,
    face_ssim_th1: float = 0.88,
    face_ssim_th2: float = 0.90,
    bbox_tol_c: float = 0.10,
    bbox_tol_wh: float = 0.18,
    face_crop_expand: float = 1.2,
) -> List[List[int]]:
    n = len(metas)
    dsu = _DSU(n)
    for i in range(n):
        for j in range(i + 1, n):
            if is_duplicate(
                metas[i],
                metas[j],
                face_sim_th1=face_sim_th1,
                face_sim_th2=face_sim_th2,
                pose_sim_th=pose_sim_th,
                face_ssim_th1=face_ssim_th1,
                face_ssim_th2=face_ssim_th2,
                bbox_tol_c=bbox_tol_c,
                bbox_tol_wh=bbox_tol_wh,
                face_crop_expand=face_crop_expand,
            ):
                dsu.union(i, j)

    clusters: dict[int, List[int]] = {}
    for i in range(n):
        root = dsu.find(i)
        clusters.setdefault(root, []).append(i)
    return list(clusters.values())


def pick_kept(
    clusters: List[List[int]],
    metas: List[ImageMeta],
    keep_per_cluster: int = 2,  # 同一姿势最多保留两张照片
) -> List[int]:
    # 第一步：从每个集群中选择指定数量的照片
    kept: List[int] = []
    for cluster in clusters:
        # 按清晰度和人脸置信度排序
        cluster_sorted = sorted(
            cluster,
            key=lambda idx: metas[idx].sharpness * 0.7 + metas[idx].face_conf * 0.3,
            reverse=True,
        )
        kept.extend(cluster_sorted[:keep_per_cluster])
    
    # 第二步：统计远景/全身照的数量
    long_shot_count = sum(1 for idx in kept if metas[idx].shot_type == "long" or metas[idx].is_full_body)
    total_count = len(kept)
    
    # 计算需要的远景/全身照数量（至少30%）
    required_long_shot_count = max(1, int(total_count * 0.3))
    
    # 如果远景/全身照数量不足，进行调整
    if long_shot_count < required_long_shot_count:
        # 找出所有远景/全身照（包括未被选中的）
        all_long_shots = []
        all_non_long_shots = []
        
        for idx in range(len(metas)):
            if metas[idx].shot_type == "long" or metas[idx].is_full_body:
                all_long_shots.append(idx)
            else:
                all_non_long_shots.append(idx)
        
        # 对远景/全身照进行排序
        all_long_shots_sorted = sorted(
            all_long_shots,
            key=lambda idx: metas[idx].sharpness * 0.7 + metas[idx].face_conf * 0.3,
            reverse=True,
        )
        
        # 对非远景/全身照进行排序
        all_non_long_shots_sorted = sorted(
            all_non_long_shots,
            key=lambda idx: metas[idx].sharpness * 0.7 + metas[idx].face_conf * 0.3,
            reverse=True,
        )
        
        # 重新构建保留列表，确保至少有required_long_shot_count张远景/全身照
        kept = []
        # 添加最佳的远景/全身照
        kept.extend(all_long_shots_sorted[:required_long_shot_count])
        # 填充剩余的位置
        remaining = total_count - required_long_shot_count
        kept.extend(all_non_long_shots_sorted[:remaining])
    
    # 第三步：再次检查远景/全身照比例
    long_shot_count = sum(1 for idx in kept if metas[idx].shot_type == "long" or metas[idx].is_full_body)
    total_count = len(kept)
    
    # 如果仍然全身照比例不足，从特写照片中移除部分照片
    if long_shot_count < required_long_shot_count:
        # 计算需要移除的特写照片数量
        need_remove = total_count - (required_long_shot_count + (total_count - long_shot_count)) + (required_long_shot_count - long_shot_count)
        need_remove = max(0, need_remove)
        
        if need_remove > 0:
            # 找出所有特写照片（面部占比大的照片）
            closeup_photos = []
            non_closeup_photos = []
            
            for idx in kept:
                meta = metas[idx]
                # 计算面部占比
                if meta.face_bbox_norm is not None:
                    # 面部占画面高度的比例
                    face_height_ratio = meta.face_bbox_norm[3]  # 归一化的面部高度
                    # 特写照片：面部占画面高度 > 0.3，或者shot_type为closeup
                    if face_height_ratio > 0.3 or meta.shot_type == "closeup":
                        # 计算面部占比权重
                        # 面部占画面高度的比例 + 清晰度 + 人脸置信度
                        weight = face_height_ratio + meta.sharpness * 0.001 + meta.face_conf * 0.1
                        closeup_photos.append((idx, weight))
                    else:
                        non_closeup_photos.append(idx)
                else:
                    non_closeup_photos.append(idx)
            
            # 按面部占比权重排序特写照片，优先移除面部占比最大的照片
            closeup_photos.sort(key=lambda x: x[1], reverse=True)
            
            # 移除部分特写照片
            num_to_remove = min(need_remove, len(closeup_photos))
            kept = non_closeup_photos + [idx for idx, _ in closeup_photos[num_to_remove:]]
    
    return kept


def _iter_images(input_dir: str) -> List[str]:
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    paths = []
    for root, _, files in os.walk(input_dir):
        for name in files:
            if os.path.splitext(name.lower())[1] in exts:
                paths.append(os.path.join(root, name))
    return sorted(paths)


def main() -> int:
    parser = argparse.ArgumentParser(description="Strict portrait dedup demo")
    parser.add_argument("--dir", required=True, help="Directory containing images")
    parser.add_argument("--keep-per-cluster", type=int, default=1)
    parser.add_argument("--max-side-analysis", type=int, default=1024)
    parser.add_argument("--max-side-small", type=int, default=512)
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--output", default="kept_list.txt")
    args = parser.parse_args()

    paths = _iter_images(args.dir)
    if not paths:
        print("No images found.")
        return 1

    metas = extract_features(
        paths,
        max_side_analysis=args.max_side_analysis,
        max_side_small=args.max_side_small,
        max_workers=args.max_workers,
    )
    clusters = cluster(metas)
    kept_indices = pick_kept(clusters, metas, keep_per_cluster=args.keep_per_cluster)
    kept_paths = [paths[i] for i in kept_indices]

    with open(args.output, "w", encoding="utf-8") as f:
        for p in kept_paths:
            f.write(f"{p}\n")

    print(f"Images: {len(paths)}")
    print(f"Clusters: {len(clusters)}")
    print(f"Kept: {len(kept_paths)}")
    print(f"Output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
