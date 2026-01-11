import typer
from client.commands.prepare_folder import prepare_folder
from client.commands.focus import focus
from client.commands.crop1024 import crop1024
from client.commands.tag import tag
from client.commands.pack import pack


def run_all(
    input: str = typer.Option(..., help="输入文件夹路径，包含多个 zip 文件"),
    output: str = typer.Option(..., help="输出文件夹路径"),
    prepared: str = typer.Option(None, help="准备好的文件夹路径，跳过 prepare-folder 步骤"),
    phash_threshold: int = typer.Option(6, help="pHash 聚类阈值"),
    keep_per_cluster: int = typer.Option(2, help="每簇保留的图片数量"),
    preview_max_side: int = typer.Option(1200, help="预览图最大边长"),
    preview_quality: int = typer.Option(86, help="预览图质量"),
    focus_model: str = typer.Option("Qwen/Qwen3-VL-30B-A3B-Instruct", help="焦点检测模型"),
    tag_model: str = typer.Option("Qwen/Qwen3-VL-235B-A22B-Instruct", help="打标模型"),
    crop_quality: int = typer.Option(95, help="裁剪后图片质量"),
):
    """执行完整流程：prepare-folder -> focus -> crop1024 -> tag -> pack"""
    typer.echo("=== LoRA 写真数据集自动构建平台 ===")
    typer.echo(f"输入路径: {input}")
    typer.echo(f"输出路径: {output}")
    typer.echo("\n开始执行完整流程...")
    
    # Step 1: Prepare folder (if not provided)
    prepared_root = prepared
    if not prepared_root:
        typer.echo("\n--- Step 1: 准备文件夹 (prepare-folder) ---")
        prepare_folder(
            input=input,
            output=output,
            phash_threshold=phash_threshold,
            keep_per_cluster=keep_per_cluster,
            preview_max_side=preview_max_side,
            preview_quality=preview_quality,
        )
        prepared_root = output
    
    # Step 2: Focus detection
    typer.echo("\n--- Step 2: 焦点检测 (focus) ---")
    focus(
        prepared=prepared_root,
        focus_model=focus_model,
    )
    
    # Step 3: Crop 1024
    typer.echo("\n--- Step 3: 裁剪 1024 (crop1024) ---")
    crop1024(
        prepared=prepared_root,
        quality=crop_quality,
    )
    
    # Step 4: Tagging
    typer.echo("\n--- Step 4: 生成标签 (tag) ---")
    tag(
        prepared=prepared_root,
        tag_model=tag_model,
    )
    
    # Step 5: Packaging
    typer.echo("\n--- Step 5: 打包结果 (pack) ---")
    pack(
        prepared=prepared_root,
        output=output,
    )
    
    typer.echo("\n=== 流程执行完成！===\n")
    typer.echo("所有步骤已完成，最终结果已生成到输出目录。")
