import os
import zipfile
import json
from pathlib import Path
from typing import List, Dict
import typer
from client.core.image_processing import (
    calculate_sharpness,
    generate_preview,
    cluster_keep_topk,
)
from PIL import Image as PILImage
from PIL import ImageFile

# Set PIL settings
ImageFile.LOAD_TRUNCATED_IMAGES = True
PILImage.MAX_IMAGE_PIXELS = 1000000000


def prepare_folder(
    input: str = typer.Option(..., help="输入文件夹路径，包含多个 zip 文件"),
    output: str = typer.Option(..., help="输出文件夹路径"),
    phash_threshold: int = typer.Option(6, help="pHash 聚类阈值"),
    keep_per_cluster: int = typer.Option(2, help="每簇保留的图片数量"),
    preview_max_side: int = typer.Option(1200, help="预览图最大边长"),
    preview_quality: int = typer.Option(86, help="预览图质量"),
):
    """准备文件夹：解压、去重、生成预览"""
    input_root = Path(input)
    output_root = Path(output)
    output_root.mkdir(exist_ok=True)

    # Process each zip file
    zip_files = list(input_root.glob("*.zip"))
    typer.echo(f"找到 {len(zip_files)} 个 zip 文件")

    for i, zip_file in enumerate(zip_files):
        scene_name = zip_file.stem
        typer.echo(f"\n处理第 {i+1}/{len(zip_files)}: {scene_name}")

        # Create scene directory
        scene_dir = output_root / scene_name
        scene_dir.mkdir(exist_ok=True)

        # Create subdirectories
        originals_kept_dir = scene_dir / "originals_kept"
        previews_dir = scene_dir / "previews"
        originals_kept_dir.mkdir(exist_ok=True)
        previews_dir.mkdir(exist_ok=True)

        # Step 1: Unpack zip
        unpack_dir = scene_dir / "unpack"
        unpack_dir.mkdir(exist_ok=True)

        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            # Check for zip slip vulnerability
            for member in zip_ref.infolist():
                if member.filename.startswith("../") or "..\\" in member.filename:
                    continue
                if member.is_dir():
                    continue
                # Extract file
                zip_ref.extract(member, unpack_dir)

        # Step 2: Collect image files
        image_extensions = [".jpg", ".jpeg", ".png", ".webp"]
        image_files = []
        for ext in image_extensions:
            image_files.extend(unpack_dir.rglob(f"*{ext}"))
            image_files.extend(unpack_dir.rglob(f"*{ext.upper()}"))

        typer.echo(f"  找到 {len(image_files)} 张图片")

        # Step 3: Calculate pHash and sharpness
        image_data: List[Dict] = []
        for img_path in image_files:
            try:
                with PILImage.open(img_path) as img:
                    # Generate thumbnail for processing
                    img_thumb = img.copy()
                    img_thumb.thumbnail((512, 512))
                    
                    # Calculate pHash and sharpness
                    from imagehash import phash
                    img_phash = str(phash(img_thumb))
                    sharpness = calculate_sharpness(img_thumb)
                    width, height = img.size

                    image_data.append({
                        "path": str(img_path),
                        "filename": img_path.name,
                        "phash": img_phash,
                        "sharpness": sharpness,
                        "width": width,
                        "height": height,
                    })
            except Exception as e:
                typer.echo(f"  跳过损坏图片 {img_path}: {e}")
                continue

        # Step 4: Cluster and keep top K per cluster
        kept_images = cluster_keep_topk(
            image_data,
            threshold=phash_threshold,
            keep_k=keep_per_cluster
        )

        typer.echo(f"  去重后保留 {len(kept_images)} 张图片")

        # Step 5: Generate previews and create index
        index = []
        for img_data in kept_images:
            # Generate preview
            preview_path = generate_preview(
                img_data["path"],
                str(previews_dir),
                max_side=preview_max_side,
                quality=preview_quality
            )

            # Create hard link to original (optional, if needed)
            # original_link = originals_kept_dir / img_data["filename"]
            # original_link.unlink(missing_ok=True)
            # original_link.hardlink_to(img_data["path"])

            # Add to index
            index.append({
                "preview_name": os.path.basename(preview_path),
                "original_path": img_data["path"],
                "md5": "",  # Will calculate later if needed
                "phash": img_data["phash"],
                "sharpness": img_data["sharpness"],
                "width": img_data["width"],
                "height": img_data["height"],
            })

        # Write index.json
        index_path = scene_dir / "index.json"
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)

        typer.echo(f"  生成 {len(index)} 个预览图")
        typer.echo(f"  保存索引到 {index_path}")

    typer.echo(f"\n处理完成！输出目录：{output_root}")
