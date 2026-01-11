import os
import json
from pathlib import Path
import typer
from client.core.model_client import ModelClient
from dotenv import load_dotenv


def focus(
    prepared: str = typer.Option(..., help="准备好的文件夹路径，包含 scene_xxx 子文件夹"),
    focus_model: str = typer.Option("Qwen/Qwen3-VL-30B-A3B-Instruct", help="焦点检测模型"),
    fallback_model: str = typer.Option("Qwen/Qwen3-VL-32B-Instruct", help="回退模型"),
):
    """调用 VL 模型获取核心点"""
    load_dotenv()
    prepared_root = Path(prepared)
    
    # Create ModelClient
    try:
        model_client = ModelClient(model=focus_model)
        typer.echo(f"使用模型: {focus_model}")
    except Exception as e:
        typer.echo(f"无法初始化模型客户端: {e}")
        raise typer.Exit(code=1)
    
    # Process each scene
    scenes = [d for d in prepared_root.iterdir() if d.is_dir()]
    typer.echo(f"找到 {len(scenes)} 个场景")
    
    for i, scene_dir in enumerate(scenes):
        scene_name = scene_dir.name
        typer.echo(f"\n处理第 {i+1}/{len(scenes)}: {scene_name}")
        
        # Read index.json
        index_path = scene_dir / "index.json"
        if not index_path.exists():
            typer.echo(f"  跳过：未找到 index.json")
            continue
        
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
        
        # Process each preview
        focus_results = []
        previews_dir = scene_dir / "previews"
        
        for j, item in enumerate(index):
            preview_name = item["preview_name"]
            preview_path = previews_dir / preview_name
            
            if not preview_path.exists():
                typer.echo(f"  跳过：预览图不存在 {preview_name}")
                continue
            
            typer.echo(f"  处理预览图 {j+1}/{len(index)}: {preview_name}")
            
            try:
                # Get focus point
                focus_result = model_client.get_focus_point(str(preview_path))
                
                # Add preview name to result
                focus_result["preview_name"] = preview_name
                focus_results.append(focus_result)
                
                typer.echo(f"    焦点：({focus_result['focus_point']['x']:.2f}, {focus_result['focus_point']['y']:.2f})，置信度：{focus_result['confidence']:.2f}")
            except Exception as e:
                typer.echo(f"    错误：{e}")
                # Fallback result
                fallback_result = {
                    "preview_name": preview_name,
                    "focus_point": {"x": 0.5, "y": 0.5},
                    "bbox": None,
                    "shot_type": None,
                    "confidence": 0.0,
                    "reason": f"error: {str(e)}"
                }
                focus_results.append(fallback_result)
        
        # Write focus.jsonl
        focus_path = scene_dir / "focus.jsonl"
        with open(focus_path, "w", encoding="utf-8") as f:
            for result in focus_results:
                f.write(json.dumps(result) + "\n")
        
        typer.echo(f"  保存焦点结果到 {focus_path}")
    
    typer.echo(f"\n焦点检测完成！")
