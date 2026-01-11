import os
import json
from pathlib import Path
import typer
from client.core.image_processing import crop_1024_from_original


def crop1024(
    prepared: str = typer.Option(..., help="准备好的文件夹路径，包含 scene_xxx 子文件夹"),
    quality: int = typer.Option(95, help="裁剪后图片质量"),
):
    """使用焦点点在原图上裁剪 1024x1024"""
    prepared_root = Path(prepared)
    
    # Process each scene
    scenes = [d for d in prepared_root.iterdir() if d.is_dir()]
    typer.echo(f"找到 {len(scenes)} 个场景")
    
    for i, scene_dir in enumerate(scenes):
        scene_name = scene_dir.name
        typer.echo(f"\n处理第 {i+1}/{len(scenes)}: {scene_name}")
        
        # Check required files
        index_path = scene_dir / "index.json"
        focus_path = scene_dir / "focus.jsonl"
        
        if not index_path.exists():
            typer.echo(f"  跳过：未找到 index.json")
            continue
        
        if not focus_path.exists():
            typer.echo(f"  跳过：未找到 focus.jsonl")
            continue
        
        # Read index.json
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
        
        # Read focus.jsonl
        focus_results = []
        with open(focus_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    focus_results.append(json.loads(line))
        
        # Create crops directory
        crops_dir = scene_dir / "crops"
        images_dir = crops_dir / "images"
        txt_dir = crops_dir / "txt"
        crops_dir.mkdir(exist_ok=True)
        images_dir.mkdir(exist_ok=True)
        txt_dir.mkdir(exist_ok=True)
        
        # Create mapping: preview_name -> focus_result
        focus_map = {r["preview_name"]: r for r in focus_results}
        
        # Process each image
        manifest = []
        success_count = 0
        
        for j, item in enumerate(index):
            preview_name = item["preview_name"]
            original_path = item["original_path"]
            
            if preview_name not in focus_map:
                typer.echo(f"  跳过：未找到焦点结果 {preview_name}")
                continue
            
            focus_result = focus_map[preview_name]
            focus_point = focus_result["focus_point"]
            
            typer.echo(f"  裁剪第 {j+1}/{len(index)}: {item['filename']}")
            
            try:
                # Crop 1024x1024
                crop_path = crop_1024_from_original(
                    original_path,
                    focus_point["x"],
                    focus_point["y"],
                    str(images_dir),
                    quality=quality
                )
                
                # Add to manifest
                manifest_item = {
                    "orig_name": item["filename"],
                    "md5": item.get("md5", ""),
                    "focus_point": focus_point,
                    "crop_path": os.path.basename(crop_path),
                    "focus_result": focus_result,
                }
                manifest.append(manifest_item)
                
                success_count += 1
                typer.echo(f"    成功：{os.path.basename(crop_path)}")
            except Exception as e:
                typer.echo(f"    错误：{e}")
                continue
        
        # Write manifest.json
        manifest_path = crops_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        
        typer.echo(f"  裁剪完成，成功 {success_count}/{len(index)} 张")
        typer.echo(f"  保存 manifest.json 到 {manifest_path}")
    
    typer.echo(f"\n裁剪完成！")
