import os
import json
import zipfile
from pathlib import Path
import typer
from datetime import datetime


def pack(
    prepared: str = typer.Option(..., help="准备好的文件夹路径，包含 scene_xxx 子文件夹"),
    output: str = typer.Option(..., help="输出文件夹路径"),
):
    """生成最终的 train_package.zip"""
    prepared_root = Path(prepared)
    output_root = Path(output)
    output_root.mkdir(exist_ok=True)
    
    # Process each scene
    scenes = [d for d in prepared_root.iterdir() if d.is_dir()]
    typer.echo(f"找到 {len(scenes)} 个场景")
    
    for i, scene_dir in enumerate(scenes):
        scene_name = scene_dir.name
        typer.echo(f"\n处理第 {i+1}/{len(scenes)}: {scene_name}")
        
        # Check required directories and files
        crops_dir = scene_dir / "crops"
        images_dir = crops_dir / "images"
        txt_dir = crops_dir / "txt"
        manifest_path = crops_dir / "manifest.json"
        
        if not images_dir.exists():
            typer.echo(f"  跳过：未找到 images 目录")
            continue
        
        if not txt_dir.exists():
            typer.echo(f"  跳过：未找到 txt 目录")
            continue
        
        if not manifest_path.exists():
            typer.echo(f"  跳过：未找到 manifest.json")
            continue
        
        # Read manifest.json
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        
        # Check if we have all required files
        missing_files = []
        for item in manifest:
            crop_name = item["crop_path"]
            txt_name = os.path.splitext(crop_name)[0] + ".txt"
            
            crop_path = images_dir / crop_name
            txt_path = txt_dir / txt_name
            
            if not crop_path.exists():
                missing_files.append(f"images/{crop_name}")
            if not txt_path.exists():
                missing_files.append(f"txt/{txt_name}")
        
        if missing_files:
            typer.echo(f"  跳过：缺少 {len(missing_files)} 个文件")
            continue
        
        # Create export directory
        export_dir = scene_dir / "export"
        export_dir.mkdir(exist_ok=True)
        
        # Generate final manifest
        final_manifest = {
            "version": "1.0",
            "scene_name": scene_name,
            "created_at": datetime.utcnow().isoformat(),
            "focus_model": manifest[0]["focus_result"]["model_used"] if manifest else "",
            "tag_model": "",  # Will be filled if we have tag info
            "images": [],
        }
        
        # Add images to final manifest
        for item in manifest:
            crop_name = item["crop_path"]
            txt_name = os.path.splitext(crop_name)[0] + ".txt"
            
            # Read tag content
            txt_path = txt_dir / txt_name
            with open(txt_path, "r", encoding="utf-8") as f:
                tag_content = f.read().strip()
            
            final_manifest["images"].append({
                "orig_name": item["orig_name"],
                "md5": item.get("md5", ""),
                "focus_point": item["focus_point"],
                "crop_path": crop_name,
                "prompt": tag_content,
            })
        
        # Write final manifest
        final_manifest_path = export_dir / "manifest.json"
        with open(final_manifest_path, "w", encoding="utf-8") as f:
            json.dump(final_manifest, f, indent=2, ensure_ascii=False)
        
        # Create train_package.zip
        train_package_path = export_dir / "train_package.zip"
        
        with zipfile.ZipFile(train_package_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            # Add manifest.json
            zipf.write(final_manifest_path, "manifest.json")
            
            # Add images
            for item in manifest:
                crop_name = item["crop_path"]
                crop_path = images_dir / crop_name
                zipf.write(crop_path, f"images/{crop_name}")
            
            # Add txt files
            for item in manifest:
                crop_name = item["crop_path"]
                txt_name = os.path.splitext(crop_name)[0] + ".txt"
                txt_path = txt_dir / txt_name
                zipf.write(txt_path, f"txt/{txt_name}")
        
        # Copy to output directory
        output_path = output_root / f"{scene_name}_train_package.zip"
        with open(train_package_path, "rb") as src, open(output_path, "wb") as dst:
            dst.write(src.read())
        
        typer.echo(f"  成功生成：{output_path}")
        typer.echo(f"    包含 {len(manifest)} 张图片，总大小：{output_path.stat().st_size / (1024*1024):.2f} MB")
    
    typer.echo(f"\n打包完成！")
