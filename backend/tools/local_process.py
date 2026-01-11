import argparse
import hashlib
import json
import os
import sys
import zipfile
from datetime import datetime

from PIL import Image, ImageFile

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.services.image_processing import generate_preview, crop_1024_from_original

try:
    from app.services import dedup_people
except Exception as exc:  # noqa: BLE001
    dedup_people = None
    _DEDUP_IMPORT_ERROR = exc


def safe_extract_zip(zip_path: str, extract_dir: str) -> list[str]:
    extracted = []
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        for member in zip_ref.infolist():
            if member.filename.startswith("../") or "..\\" in member.filename:
                continue
            if member.is_dir():
                continue
            zip_ref.extract(member, extract_dir)
            extracted.append(os.path.join(extract_dir, member.filename))
    return extracted


def _md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _ensure_dedup_available() -> None:
    if dedup_people is None:
        raise RuntimeError(
            "dedup_people import failed. Install insightface, mediapipe, opencv-python "
            f"and retry. Error: {_DEDUP_IMPORT_ERROR}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Local-only dataset processing")
    parser.add_argument("--zip", required=True, help="Path to input zip")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--keep-per-cluster", type=int, default=1)  # 同一姿势和位置最多保留一张照片
    parser.add_argument("--max-side-analysis", type=int, default=1024)
    parser.add_argument("--max-side-small", type=int, default=512)
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--face-sim-th1", type=float, default=0.58)
    parser.add_argument("--face-sim-th2", type=float, default=0.64)
    parser.add_argument("--pose-sim-th", type=float, default=0.85)
    parser.add_argument("--face-ssim-th1", type=float, default=0.88)
    parser.add_argument("--face-ssim-th2", type=float, default=0.90)
    parser.add_argument("--bbox-tol-c", type=float, default=0.10)
    parser.add_argument("--bbox-tol-wh", type=float, default=0.18)
    parser.add_argument("--face-crop-expand", type=float, default=1.2)
    parser.add_argument("--min-pose-conf", type=float, default=0.35)
    parser.add_argument("--preview-max-side", type=int, default=1200)
    parser.add_argument("--preview-quality", type=int, default=86)
    parser.add_argument("--max-image-pixels", type=int, default=1_000_000_000)
    parser.add_argument("--report", default="report.txt", help="Report filename in output dir")
    args = parser.parse_args()

    zip_path = os.path.abspath(args.zip)
    out_dir = os.path.abspath(args.out)

    if not os.path.exists(zip_path):
        raise FileNotFoundError(zip_path)

    os.makedirs(out_dir, exist_ok=True)
    unpack_dir = os.path.join(out_dir, "unpack")
    previews_dir = os.path.join(out_dir, "previews")

    for d in [unpack_dir, previews_dir]:
        os.makedirs(d, exist_ok=True)

    ImageFile.LOAD_TRUNCATED_IMAGES = True
    Image.MAX_IMAGE_PIXELS = args.max_image_pixels

    extracted_files = safe_extract_zip(zip_path, unpack_dir)
    image_exts = [".jpg", ".jpeg", ".png", ".webp"]
    image_files = [
        f for f in extracted_files if os.path.splitext(f.lower())[1] in image_exts
    ]

    if not image_files:
        print("No images found after extraction.")
        return 1

    _ensure_dedup_available()

    metas = dedup_people.extract_features(
        image_files,
        max_side_analysis=args.max_side_analysis,
        max_side_small=args.max_side_small,
        min_pose_conf=args.min_pose_conf,
        max_workers=args.max_workers,
    )
    clusters = dedup_people.cluster(
        metas,
        face_sim_th1=args.face_sim_th1,
        face_sim_th2=args.face_sim_th2,
        pose_sim_th=args.pose_sim_th,
        face_ssim_th1=args.face_ssim_th1,
        face_ssim_th2=args.face_ssim_th2,
        bbox_tol_c=args.bbox_tol_c,
        bbox_tol_wh=args.bbox_tol_wh,
        face_crop_expand=args.face_crop_expand,
    )
    kept_indices = dedup_people.pick_kept(
        clusters, metas, keep_per_cluster=args.keep_per_cluster
    )

    kept_set = set(kept_indices)
    kept_images = [image_files[i] for i in kept_indices]
    dropped_images = [image_files[i] for i in range(len(image_files)) if i not in kept_set]

    face_ok = sum(1 for m in metas if m.face_emb is not None)
    pose_ok = sum(1 for m in metas if m.pose_vec is not None)

    manifest = {
        "version": "local-only-people-1.0",
        "created_at": datetime.utcnow().isoformat(),
        "zip_path": zip_path,
        "total_files": len(extracted_files),
        "image_files": len(image_files),
        "kept_files": len(kept_images),
        "dropped_files": len(dropped_images),
        "clusters": len(clusters),
        "images": [],
    }

    for idx in kept_indices:
        path = image_files[idx]
        meta = metas[idx]
        preview_path = generate_preview(
            path,
            previews_dir,
            max_side=args.preview_max_side,
            quality=args.preview_quality,
        )
        manifest["images"].append(
            {
                "orig_path": path,
                "md5": _md5(path),
                "preview_path": preview_path,
                "crop_path": None,
                "meta": {
                    "face_bbox_norm": meta.face_bbox_norm,
                    "face_conf": meta.face_conf,
                    "pose_conf": meta.pose_conf,
                    "body_height_ratio": meta.body_height_ratio,
                    "is_full_body": meta.is_full_body,
                    "shot_type": meta.shot_type,
                    "has_pose": meta.pose_vec is not None,
                    "has_face": meta.face_emb is not None,
                    "sharpness": meta.sharpness,
                    "errors": meta.errors,
                },
            }
        )

    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    report_path = os.path.join(out_dir, args.report)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("Local-only processing report (people dedup)\n")
        f.write(f"Zip: {zip_path}\n")
        f.write(f"Total files: {len(extracted_files)}\n")
        f.write(f"Image files: {len(image_files)}\n")
        f.write(f"Kept images: {len(kept_images)}\n")
        f.write(f"Dropped images: {len(dropped_images)}\n")
        f.write(f"Clusters: {len(clusters)}\n")
        f.write(f"Face OK: {face_ok}/{len(metas)}\n")
        f.write(f"Pose OK: {pose_ok}/{len(metas)}\n")
        f.write(f"face_sim_th1: {args.face_sim_th1}\n")
        f.write(f"face_sim_th2: {args.face_sim_th2}\n")
        f.write(f"pose_sim_th: {args.pose_sim_th}\n")
        f.write(f"face_ssim_th1: {args.face_ssim_th1}\n")
        f.write(f"face_ssim_th2: {args.face_ssim_th2}\n")
        f.write(f"bbox_tol_c: {args.bbox_tol_c}\n")
        f.write(f"bbox_tol_wh: {args.bbox_tol_wh}\n")
        f.write(f"face_crop_expand: {args.face_crop_expand}\n")
        f.write(f"min_pose_conf: {args.min_pose_conf}\n")
        f.write("\nPer-image meta:\n")
        for idx, (path, meta) in enumerate(zip(image_files, metas)):
            f.write(f"[{idx}] {path}\n")
            f.write(f"  sharpness: {meta.sharpness:.3f}\n")
            f.write(f"  face_conf: {meta.face_conf:.4f}\n")
            f.write(f"  pose_conf: {meta.pose_conf:.4f}\n")
            f.write(f"  face_bbox_norm: {meta.face_bbox_norm}\n")
            f.write(f"  has_face: {meta.face_emb is not None}\n")
            f.write(f"  has_pose: {meta.pose_vec is not None}\n")
            if meta.errors:
                f.write(f"  errors: {', '.join(meta.errors)}\n")
            else:
                f.write("  errors: none\n")
        f.write("\nKept:\n")
        for p in kept_images:
            f.write(f"- {p}\n")
        if dropped_images:
            f.write("\nDropped:\n")
            for p in dropped_images:
                f.write(f"- {p}\n")

    print(f"Unpack dir: {unpack_dir}")
    print(f"Preview dir: {previews_dir}")
    print(f"Manifest: {manifest_path}")
    print(f"Report: {report_path}")
    print(f"Kept images: {len(kept_images)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
