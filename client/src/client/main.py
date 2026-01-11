import typer
from client.commands import prepare_folder, focus, crop1024, tag, pack, run_all

app = typer.Typer(
    name="lora-dataset-builder",
    help="LoRA 写真数据集自动构建平台 - 本地 CLI",
    no_args_is_help=True,
)

# Add commands
app.command("prepare-folder")(prepare_folder.prepare_folder)
app.command("focus")(focus.focus)
app.command("crop1024")(crop1024.crop1024)
app.command("tag")(tag.tag)
app.command("pack")(pack.pack)
app.command("run-all")(run_all.run_all)

if __name__ == "__main__":
    app()
