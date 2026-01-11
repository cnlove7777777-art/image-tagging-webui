import os
import json
from pathlib import Path
import typer
from client.core.model_client import ModelClient
from dotenv import load_dotenv


def tag(
    prepared: str = typer.Option(..., help="准备好的文件夹路径，包含 scene_xxx 子文件夹"),
    tag_model: str = typer.Option("Qwen/Qwen3-VL-235B-A22B-Instruct", help="打标模型"),
    fallback_model: str = typer.Option("Qwen/Qwen3-VL-32B-Instruct", help="回退模型"),
):
    """调用 VL 模型生成标签"""
    load_dotenv()
    prepared_root = Path(prepared)
    
    # Create ModelClient
    try:
        model_client = ModelClient(model=tag_model)
        typer.echo(f"使用模型: {tag_model}")
    except Exception as e:
        typer.echo(f"无法初始化模型客户端: {e}")
        raise typer.Exit(code=1)
    
    # Process each scene
    scenes = [d for d in prepared_root.iterdir() if d.is_dir()]
    typer.echo(f"找到 {len(scenes)} 个场景")
    
    for i, scene_dir in enumerate(scenes):
        scene_name = scene_dir.name
        typer.echo(f"\n处理第 {i+1}/{len(scenes)}: {scene_name}")
        
        # Check required directories
        crops_dir = scene_dir / "crops"
        images_dir = crops_dir / "images"
        txt_dir = crops_dir / "txt"
        
        if not images_dir.exists():
            typer.echo(f"  跳过：未找到 images 目录")
            continue
        
        # Get list of images
        image_files = list(images_dir.glob("*.jpg"))
        if not image_files:
            typer.echo(f"  跳过：未找到图片文件")
            continue
        
        typer.echo(f"  找到 {len(image_files)} 张图片")
        
        # Process each image
        success_count = 0
        
        for j, image_path in enumerate(image_files):
            image_name = image_path.name
            typer.echo(f"  打标第 {j+1}/{len(image_files)}: {image_name}")
            
            try:
                # Generate tags
                tags = model_client.generate_tags(str(image_path))
                
                # Write tags to file
                txt_filename = os.path.splitext(image_name)[0] + ".txt"
                txt_path = txt_dir / txt_filename
                
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(tags)
                
                success_count += 1
                typer.echo(f"    成功：生成 {len(tags.split(','))} 个标签")
            except Exception as e:
                typer.echo(f"    错误：{e}")
                continue
        
        typer.echo(f"  打标完成，成功 {success_count}/{len(image_files)} 张")
    
    typer.echo(f"\n打标完成！")
