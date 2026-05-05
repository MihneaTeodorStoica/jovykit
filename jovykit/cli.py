"""Typer command-line interface for JovyKit."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import typer
from rich.console import Console

from jovykit import __version__
from jovykit.config import (
    JovyKitError,
    initial_config_text,
    load_config,
    read_state,
    write_state,
)
from jovykit.deps import add_packages
from jovykit.generate import ensure_empty_or_jovy_env, write_generated_files
from jovykit.paths import DEFAULT_ENV_DIR, find_environment
from jovykit.runtime import build as build_image
from jovykit.runtime import compose, destroy as destroy_environment
from jovykit.runtime import is_build_stale

app = typer.Typer(help="Manage project-local JovyKit Jupyter container environments.")
console = Console()


def _version_callback(show_version: bool) -> None:
    if show_version:
        console.print(f"jovykit {__version__}")
        raise typer.Exit()


@app.callback()
def callback(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the installed JovyKit version and exit.",
    ),
) -> None:
    """Manage project-local JovyKit Jupyter container environments."""


def _load_env(env: Path | None = None):
    env_dir = env.resolve() if env else find_environment()
    return load_config(env_dir)


def _display_path(path: Path) -> Path:
    cwd = Path.cwd()
    return path.relative_to(cwd) if path.is_relative_to(cwd) else path


def _ensure_built(config, *, no_build: bool = False) -> None:
    if no_build:
        if is_build_stale(config):
            console.print(
                "[yellow]Build is stale; continuing because --no-build was used.[/yellow]"
            )
        return
    if is_build_stale(config):
        console.print("[bold]Building JovyKit overlay image...[/bold]")
        build_image(config)


@app.command()
def init(
    path: Path = typer.Argument(
        Path(DEFAULT_ENV_DIR), help="Environment directory to create."
    ),
    image: str = typer.Option(
        "base", "--image", help="Image level or full image reference."
    ),
    gpus: str = typer.Option("auto", "--gpus", help="GPU mode: auto, none, or all."),
    port: int = typer.Option(8888, "--port", help="Local Jupyter port."),
    token: str = typer.Option(
        "auto",
        "--token",
        help="Jupyter access token, or auto for Jupyter's generated token.",
    ),
    log_level: str = typer.Option(
        "ERROR",
        "--log-level",
        help="Jupyter server log level.",
    ),
    project_name: str | None = typer.Option(
        None, "--name", help="Project name to store in jovy.toml."
    ),
    image_name: str | None = typer.Option(
        None, "--image-name", help="Project overlay image name."
    ),
    image_tag: str = typer.Option("local", "--tag", help="Project overlay image tag."),
    workdir: str = typer.Option(
        "..", "--workdir", help="Project path mounted into the container."
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Refresh an existing JovyKit environment in this directory.",
    ),
) -> None:
    """Create a project-local JovyKit environment."""
    env_dir = path.resolve()
    if not force:
        ensure_empty_or_jovy_env(env_dir)
    elif (
        env_dir.exists()
        and any(env_dir.iterdir())
        and not (env_dir / "jovy.toml").exists()
    ):
        raise JovyKitError(
            f"Refusing to force initialize non-JovyKit directory: {env_dir}"
        )
    env_dir.mkdir(parents=True, exist_ok=True)

    project_root = env_dir.parent
    (env_dir / "jovy.toml").write_text(
        initial_config_text(
            project_name=project_name or project_root.name,
            env_name=env_dir.name,
            image=image,
            gpus=gpus,
            port=port,
            token=token,
            log_level=log_level,
            image_name=image_name,
            image_tag=image_tag,
            workdir=workdir,
        ),
        encoding="utf-8",
    )

    config = load_config(env_dir)
    write_generated_files(config)
    write_state(env_dir, {})

    console.print(f"JovyKit environment: [bold]{_display_path(env_dir)}[/bold]")
    console.print(f"Base image: {config.base_image}")
    console.print(f"Project image: {config.image_ref}")
    console.print(f"GPU: {config.gpus}")
    console.print(f"Jupyter: http://127.0.0.1:{config.port}/lab")


@app.command()
def add(
    packages: list[str] = typer.Argument(
        ..., help="Packages to add to .jovy/requirements.txt."
    ),
    env: Path | None = typer.Option(
        None, "--env", help="JovyKit environment directory."
    ),
    sync_after: bool = typer.Option(
        False, "--sync", help="Regenerate files and build after adding packages."
    ),
) -> None:
    """Add packages to the project environment manifest."""
    config = _load_env(env)
    added = add_packages(config.env_dir / "requirements.txt", packages)
    state = read_state(config.env_dir)
    state.pop("build_signature", None)
    write_state(config.env_dir, state)
    if added:
        console.print(f"Added: {', '.join(added)}")
        if sync_after:
            console.print("Regenerating files and rebuilding the overlay...")
            write_generated_files(config)
            _ensure_built(config)
        else:
            console.print(
                "Run [bold]jovy sync[/bold] or [bold]jovy run[/bold] to rebuild the overlay."
            )
    else:
        console.print("No new packages added.")


@app.command()
def build(
    env: Path | None = typer.Option(
        None, "--env", help="JovyKit environment directory."
    ),
    no_cache: bool = typer.Option(False, "--no-cache", help="Build without cache."),
    pull: bool = typer.Option(
        False, "--pull", help="Always attempt to pull base image."
    ),
) -> None:
    """Build the project overlay image."""
    config = _load_env(env)
    build_image(config, no_cache=no_cache, pull=pull)


@app.command()
def sync(
    env: Path | None = typer.Option(
        None, "--env", help="JovyKit environment directory."
    ),
    no_build: bool = typer.Option(False, "--no-build", help="Only regenerate files."),
) -> None:
    """Regenerate files and build the overlay image when stale."""
    config = _load_env(env)
    write_generated_files(config)
    _ensure_built(config, no_build=no_build)


@app.command()
def run(
    env: Path | None = typer.Option(
        None, "--env", help="JovyKit environment directory."
    ),
    no_build: bool = typer.Option(False, "--no-build", help="Skip stale build check."),
    watch: bool = typer.Option(
        True,
        "--watch/--no-watch",
        help="Use Docker Compose watch while Jupyter runs.",
    ),
) -> None:
    """Build if needed and start Jupyter in the foreground."""
    config = _load_env(env)
    write_generated_files(config)
    _ensure_built(config, no_build=no_build)
    console.print(f"Jupyter: http://127.0.0.1:{config.port}/lab")
    args = ["up"]
    if watch:
        args.append("--watch")
    compose(config, *args, attached=True)


@app.command()
def start(
    env: Path | None = typer.Option(
        None, "--env", help="JovyKit environment directory."
    ),
    no_build: bool = typer.Option(False, "--no-build", help="Skip stale build check."),
) -> None:
    """Build if needed and start Jupyter in the background."""
    config = _load_env(env)
    write_generated_files(config)
    _ensure_built(config, no_build=no_build)
    compose(config, "up", "-d", attached=True)
    console.print(f"Jupyter: http://127.0.0.1:{config.port}/lab")


@app.command()
def stop(
    env: Path | None = typer.Option(
        None, "--env", help="JovyKit environment directory."
    ),
    timeout: int | None = typer.Option(
        None, "--timeout", help="Seconds to wait before killing containers."
    ),
) -> None:
    """Stop the JovyKit environment."""
    args = ["stop"]
    if timeout is not None:
        args.extend(["--timeout", str(timeout)])
    compose(_load_env(env), *args, attached=True)


@app.command()
def logs(
    env: Path | None = typer.Option(
        None, "--env", help="JovyKit environment directory."
    ),
    follow: bool = typer.Option(True, "--follow/--no-follow", help="Follow logs."),
    tail: str = typer.Option("all", "--tail", help="Number of lines to show."),
    since: str | None = typer.Option(
        None, "--since", help="Show logs since a relative time or timestamp."
    ),
    timestamps: bool = typer.Option(
        False, "--timestamps", "-t", help="Show timestamps in log output."
    ),
) -> None:
    """Follow JovyKit container logs."""
    args = ["logs", "--tail", tail]
    if since:
        args.extend(["--since", since])
    if timestamps:
        args.append("--timestamps")
    if follow:
        args.append("-f")
    compose(_load_env(env), *args, attached=True)


@app.command()
def shell(
    env: Path | None = typer.Option(
        None, "--env", help="JovyKit environment directory."
    ),
    command: str | None = typer.Option(
        None, "--command", "-c", help="Run a shell command instead of opening bash."
    ),
) -> None:
    """Open a bash shell in the running JovyKit container."""
    args = ["exec", "jovy", "bash"]
    if command:
        args.extend(["-lc", command])
    compose(_load_env(env), *args, attached=True)


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def exec(
    ctx: typer.Context,
    env: Path | None = typer.Option(
        None, "--env", help="JovyKit environment directory."
    ),
) -> None:
    """Run a command inside the running JovyKit container."""
    if not ctx.args:
        raise typer.BadParameter(
            "Pass a command to run, for example: jovy exec python --version"
        )
    compose(_load_env(env), "exec", "jovy", *ctx.args, attached=True)


@app.command()
def destroy(
    env: Path | None = typer.Option(
        None, "--env", help="JovyKit environment directory."
    ),
    remove_dir: bool = typer.Option(
        False, "--remove-dir", help="Also delete the environment directory."
    ),
    keep_image: bool = typer.Option(
        False, "--keep-image", help="Keep the project overlay image."
    ),
) -> None:
    """Remove the container, volume, and project overlay image."""
    config = _load_env(env)
    destroy_environment(config, remove_image=not keep_image)
    if remove_dir:
        shutil.rmtree(config.env_dir)
        console.print(f"Removed {config.env_dir}")


@app.command()
def status(
    env: Path | None = typer.Option(
        None, "--env", help="JovyKit environment directory."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Print machine-readable JSON."
    ),
) -> None:
    """Show basic JovyKit environment state."""
    config = _load_env(env)
    stale = is_build_stale(config)
    data = {
        "environment": str(config.env_dir),
        "base_image": config.base_image,
        "project_image": config.image_ref,
        "port": config.port,
        "gpus": config.gpus,
        "build_stale": stale,
    }
    if json_output:
        console.print(json.dumps(data, indent=2, sort_keys=True))
        return
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
    except JovyKitError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1) from None
