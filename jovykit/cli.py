"""Typer command-line interface for JovyKit."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from jovykit import __version__
from jovykit import commands as command_ops
from jovykit.config import DEFAULT_JUPYTER_TOKEN, JovyKitError
from jovykit.paths import DEFAULT_ENV_DIR

app = typer.Typer(help="Manage project-local JovyKit Jupyter container environments.")
console = Console()


def launch_dashboard() -> None:
    """Launch the default interactive dashboard."""
    from jovykit.tui import run_dashboard

    run_dashboard()


def _version_callback(show_version: bool) -> None:
    if show_version:
        console.print(f"jovykit {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the installed JovyKit version and exit.",
    ),
) -> None:
    """Manage project-local JovyKit Jupyter container environments."""
    if ctx.invoked_subcommand is None:
        launch_dashboard()
        raise typer.Exit()


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
        DEFAULT_JUPYTER_TOKEN,
        "--token",
        help="Jupyter access token. Defaults to jovykit.",
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
        "work", "--workdir", help="Project path mounted into the container."
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Refresh an existing JovyKit environment in this directory.",
    ),
) -> None:
    """Create a project-local JovyKit environment."""
    command_ops.init_environment(
        path=path,
        image=image,
        gpus=gpus,
        port=port,
        token=token,
        log_level=log_level,
        project_name=project_name,
        image_name=image_name,
        image_tag=image_tag,
        workdir=workdir,
        force=force,
        emit=console.print,
    )


@app.command()
def add(
    packages: list[str] | None = typer.Argument(
        None, help="Packages to add to jovy.toml."
    ),
    requirement_files: list[Path] | None = typer.Option(
        None,
        "-r",
        "--requirement",
        help="Import packages from a requirements file. May be repeated.",
    ),
    env: Path | None = typer.Option(
        None, "--env", help="JovyKit environment directory."
    ),
) -> None:
    """Add packages to the project environment manifest."""
    package_list = packages or []
    requirement_list = requirement_files or []
    if not package_list and not requirement_list:
        raise typer.BadParameter("Pass packages or at least one -r/--requirement file.")
    command_ops.add(
        package_list,
        requirement_files=requirement_list,
        env=env,
        emit=console.print,
    )


@app.command()
def remove(
    packages: list[str] = typer.Argument(
        ..., help="Packages to remove from jovy.toml."
    ),
    env: Path | None = typer.Option(
        None, "--env", help="JovyKit environment directory."
    ),
) -> None:
    """Remove packages from the project environment manifest."""
    command_ops.remove(packages, env=env, emit=console.print)


@app.command()
def install(
    env: Path | None = typer.Option(
        None, "--env", help="JovyKit environment directory."
    ),
    no_build: bool = typer.Option(False, "--no-build", help="Only regenerate files."),
    upgrade: bool = typer.Option(
        False, "--upgrade", help="Refresh pinned package versions in the lockfile."
    ),
) -> None:
    """Regenerate files and build the overlay image when stale."""
    command_ops.install(
        command_ops.load_env(env, emit=console.print),
        no_build=no_build,
        upgrade=upgrade,
        emit=console.print,
    )


@app.command()
def build(
    env: Path | None = typer.Option(
        None, "--env", help="JovyKit environment directory."
    ),
    no_cache: bool = typer.Option(False, "--no-cache", help="Build without cache."),
    pull: bool = typer.Option(
        False, "--pull", help="Always attempt to pull base image."
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show subprocess output."
    ),
) -> None:
    """Build the project overlay image."""
    command_ops.build(
        env=env, no_cache=no_cache, pull=pull, emit=console.print, verbose=verbose
    )


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
    command_ops.run(env=env, no_build=no_build, watch=watch, emit=console.print)


@app.command()
def up(
    env: Path | None = typer.Option(
        None, "--env", help="JovyKit environment directory."
    ),
    no_build: bool = typer.Option(False, "--no-build", help="Skip stale build check."),
) -> None:
    """Build if needed and start Jupyter in the background."""
    command_ops.up(env=env, no_build=no_build, emit=console.print)


@app.command("start")
def start(
    env: Path | None = typer.Option(
        None, "--env", help="JovyKit environment directory."
    ),
    no_build: bool = typer.Option(False, "--no-build", help="Skip stale build check."),
) -> None:
    """Alias for up."""
    command_ops.up(env=env, no_build=no_build, emit=console.print)


@app.command()
def down(
    env: Path | None = typer.Option(
        None, "--env", help="JovyKit environment directory."
    ),
    timeout: int | None = typer.Option(
        None, "--timeout", help="Seconds to wait before killing containers."
    ),
) -> None:
    """Stop the JovyKit environment."""
    command_ops.down(env=env, timeout=timeout, emit=console.print)


@app.command("stop")
def stop(
    env: Path | None = typer.Option(
        None, "--env", help="JovyKit environment directory."
    ),
    timeout: int | None = typer.Option(
        None, "--timeout", help="Seconds to wait before killing containers."
    ),
) -> None:
    """Alias for down."""
    command_ops.down(env=env, timeout=timeout, emit=console.print)


@app.command()
def restart(
    env: Path | None = typer.Option(
        None, "--env", help="JovyKit environment directory."
    ),
    no_build: bool = typer.Option(False, "--no-build", help="Skip stale build check."),
    timeout: int | None = typer.Option(
        None, "--timeout", help="Seconds to wait before killing containers."
    ),
) -> None:
    """Build if needed and restart Jupyter in the background."""
    command_ops.restart(
        env=env,
        no_build=no_build,
        timeout=timeout,
        emit=console.print,
    )


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
    command_ops.logs(
        env=env,
        follow=follow,
        tail=tail,
        since=since,
        timestamps=timestamps,
        emit=console.print,
    )


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
    command_ops.shell(env=env, command=command)


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
    command_ops.exec_in_container(ctx.args, env=env, emit=console.print)


@app.command()
def destroy(
    env: Path | None = typer.Option(
        None, "--env", help="JovyKit environment directory."
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip the confirmation prompt."
    ),
    purge: bool = typer.Option(
        False, "--purge", help="Also delete persisted home data."
    ),
    remove_dir: bool = typer.Option(
        False,
        "--remove-dir",
        help="Deprecated. With --purge, also delete the environment directory.",
    ),
    keep_image: bool = typer.Option(
        False, "--keep-image", help="Keep the project overlay image."
    ),
) -> None:
    """Remove runtime resources while preserving home data by default."""
    config = command_ops.load_env(env, emit=console.print)
    if not yes:
        if purge:
            prompt = (
                f"Destroy this JovyKit environment and permanently delete "
                f"home data at {config.home_path}?"
            )
        else:
            prompt = (
                f"Destroy this JovyKit environment? "
                f"Home data at {config.home_path} will be preserved."
            )
        confirmed = typer.confirm(prompt)
        if not confirmed:
            console.print("Destroy cancelled.")
            raise typer.Exit()
    command_ops.destroy(
        env=config.env_dir,
        purge=purge,
        remove_dir=remove_dir,
        keep_image=keep_image,
        emit=console.print,
    )


@app.command()
def clean(
    env: Path | None = typer.Option(
        None, "--env", help="JovyKit environment directory."
    ),
) -> None:
    """Remove generated files and local build state."""
    command_ops.clean(env=env, emit=console.print)


@app.command()
def config(
    env: Path | None = typer.Option(
        None, "--env", help="JovyKit environment directory."
    ),
) -> None:
    """Edit core jovy.toml settings interactively."""
    from jovykit.config_editor import run_config_editor

    run_config_editor(env=env)


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
    command_ops.status(env=env, json_output=json_output, emit=console.print)


def main() -> None:
    """Console script entrypoint."""
    try:
        app()
    except JovyKitError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1) from None
