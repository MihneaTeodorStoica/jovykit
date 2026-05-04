"""Typer command-line interface for LabKit."""

from __future__ import annotations

import shutil
from pathlib import Path

import typer
from rich.console import Console

from labkit.config import initial_config_text, load_config, read_state, write_state
from labkit.deps import add_packages
from labkit.generate import ensure_empty_or_lab_env, write_generated_files
from labkit.paths import DEFAULT_ENV_DIR, find_environment
from labkit.runtime import DockerError, build as build_image
from labkit.runtime import compose, destroy as destroy_environment
from labkit.runtime import is_build_stale

app = typer.Typer(help="Manage project-local LabKit Jupyter container environments.")
console = Console()


def _load_env(env: Path | None = None):
    env_dir = env.resolve() if env else find_environment()
    return load_config(env_dir)


def _ensure_built(config) -> None:
    if is_build_stale(config):
        console.print("[bold]Building LabKit overlay image...[/bold]")
        build_image(config)


@app.command()
def init(
    path: Path = typer.Argument(Path(DEFAULT_ENV_DIR), help="Environment directory to create."),
    image: str = typer.Option("base", "--image", help="Image level or full image reference."),
    gpus: str = typer.Option("auto", "--gpus", help="GPU mode: auto, none, or all."),
    port: int = typer.Option(8888, "--port", help="Local Jupyter port."),
) -> None:
    """Create a project-local LabKit environment."""
    env_dir = path.resolve()
    ensure_empty_or_lab_env(env_dir)
    env_dir.mkdir(parents=True, exist_ok=True)

    project_root = env_dir.parent
    (env_dir / "lab.toml").write_text(
        initial_config_text(
            project_name=project_root.name,
            env_name=env_dir.name,
            image=image,
            gpus=gpus,
            port=port,
        ),
        encoding="utf-8",
    )

    config = load_config(env_dir)
    write_generated_files(config)
    write_state(env_dir, {})

    console.print(f"LabKit environment: [bold]{env_dir.relative_to(Path.cwd()) if env_dir.is_relative_to(Path.cwd()) else env_dir}[/bold]")
    console.print(f"Base image: {config.base_image}")
    console.print(f"Project image: {config.image_ref}")
    console.print(f"GPU: {config.gpus}")
    console.print(f"Jupyter: http://127.0.0.1:{config.port}/lab")


@app.command()
def add(packages: list[str] = typer.Argument(..., help="Packages to add to .lab/requirements.txt.")) -> None:
    """Add packages to the project environment manifest."""
    config = _load_env()
    added = add_packages(config.env_dir / "requirements.txt", packages)
    state = read_state(config.env_dir)
    state.pop("build_signature", None)
    write_state(config.env_dir, state)
    if added:
        console.print(f"Added: {', '.join(added)}")
        console.print("Run [bold]lab sync[/bold] or [bold]lab run[/bold] to rebuild the overlay.")
    else:
        console.print("No new packages added.")


@app.command()
def build(no_cache: bool = typer.Option(False, "--no-cache", help="Build without cache.")) -> None:
    """Build the project overlay image."""
    config = _load_env()
    build_image(config, no_cache=no_cache)


@app.command()
def sync() -> None:
    """Regenerate files and build the overlay image when stale."""
    config = _load_env()
    write_generated_files(config)
    _ensure_built(config)


@app.command()
def run() -> None:
    """Build if needed and start Jupyter in the foreground."""
    config = _load_env()
    write_generated_files(config)
    _ensure_built(config)
    console.print(f"Jupyter: http://127.0.0.1:{config.port}/lab")
    compose(config, "up", attached=True)


@app.command()
def start() -> None:
    """Build if needed and start Jupyter in the background."""
    config = _load_env()
    write_generated_files(config)
    _ensure_built(config)
    compose(config, "up", "-d", attached=True)
    console.print(f"Jupyter: http://127.0.0.1:{config.port}/lab")


@app.command()
def stop() -> None:
    """Stop the LabKit environment."""
    compose(_load_env(), "stop", attached=True)


@app.command()
def logs() -> None:
    """Follow LabKit container logs."""
    compose(_load_env(), "logs", "-f", attached=True)


@app.command()
def shell() -> None:
    """Open a bash shell in the running LabKit container."""
    compose(_load_env(), "exec", "lab", "bash", attached=True)


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def exec(ctx: typer.Context) -> None:
    """Run a command inside the running LabKit container."""
    if not ctx.args:
        raise typer.BadParameter("Pass a command to run, for example: lab exec python --version")
    compose(_load_env(), "exec", "lab", *ctx.args, attached=True)


@app.command()
def destroy(remove_dir: bool = typer.Option(False, "--remove-dir", help="Also delete the environment directory.")) -> None:
    """Remove the container, volume, and project overlay image."""
    config = _load_env()
    destroy_environment(config)
    if remove_dir:
        shutil.rmtree(config.env_dir)
        console.print(f"Removed {config.env_dir}")


@app.command()
def status() -> None:
    """Show basic LabKit environment state."""
    config = _load_env()
    stale = is_build_stale(config)
    console.print(f"Environment: {config.env_dir}")
    console.print(f"Base image: {config.base_image}")
    console.print(f"Project image: {config.image_ref}")
    console.print(f"Port: {config.port}")
    console.print(f"GPU: {config.gpus}")
    console.print(f"Build stale: {'yes' if stale else 'no'}")


def main() -> None:
    """Console script entrypoint."""
    try:
        app()
    except (DockerError, FileNotFoundError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
