"""Shared JovyKit command operations for the CLI and TUI."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from jovykit.config import (
    DEFAULT_JUPYTER_PASSWORD,
    JovyConfig,
    JovyKitError,
    initial_config_text,
    load_config,
    read_state,
    write_state,
)
from jovykit.deps import add_packages, remove_packages
from jovykit.generate import ensure_empty_or_jovy_env, write_generated_files
from jovykit.paths import (
    DEFAULT_ENV_DIR,
    environment_from_path,
    find_environment,
    has_stale_legacy_config,
)
from jovykit.runtime import (
    build as build_image,
    build_streaming,
    compose,
    destroy as destroy_environment,
    is_build_stale,
)
from jovykit.watcher import start_watcher, stop_watcher

Emitter = Callable[[str], None]


def noop_emit(_: str) -> None:
    """Ignore emitted command output."""


def display_path(path: Path) -> Path:
    """Return a path relative to cwd when possible."""
    cwd = Path.cwd()
    return path.relative_to(cwd) if path.is_relative_to(cwd) else path


def jupyter_url(config: JovyConfig) -> str:
    """Return the local JupyterLab URL for a config."""
    return f"http://127.0.0.1:{config.port}/lab"


def emit_jupyter_access(config: JovyConfig, emit: Emitter) -> None:
    """Emit Jupyter access details."""
    emit(f"Jupyter: {jupyter_url(config)}")
    if config.jupyter_password:
        emit(f"Password: {config.jupyter_password}")


def load_env(env: Path | None = None, *, emit: Emitter = noop_emit) -> JovyConfig:
    """Load the current or explicit JovyKit environment."""
    env_dir = environment_from_path(env) if env else find_environment()
    if has_stale_legacy_config(env_dir):
        emit(f"Ignoring stale legacy config at {env_dir / 'jovy.toml'}.")
    return load_config(env_dir)


def clear_build_state(env_dir: Path) -> None:
    """Clear stale build signature while preserving other state."""
    state = read_state(env_dir)
    state.pop("build_signature", None)
    write_state(env_dir, state)


def ensure_built(
    config: JovyConfig,
    *,
    no_build: bool = False,
    emit: Emitter = noop_emit,
    stream: bool = False,
) -> None:
    """Build the overlay image if it is stale."""
    if no_build:
        if is_build_stale(config):
            emit("Build is stale; continuing because --no-build was used.")
        return
    if is_build_stale(config):
        emit("Building JovyKit overlay image...")
        if stream:
            build_streaming(config, log=emit)
        else:
            build_image(config)


def install(
    config: JovyConfig,
    *,
    no_build: bool = False,
    emit: Emitter = noop_emit,
    stream: bool = False,
) -> None:
    """Regenerate files and build the overlay image when stale."""
    write_generated_files(config)
    ensure_built(config, no_build=no_build, emit=emit, stream=stream)


def init_environment(
    *,
    path: Path = Path(DEFAULT_ENV_DIR),
    image: str = "base",
    gpus: str = "auto",
    port: int = 8888,
    token: str = "",
    password: str = DEFAULT_JUPYTER_PASSWORD,
    log_level: str = "ERROR",
    project_name: str | None = None,
    image_name: str | None = None,
    image_tag: str = "local",
    workdir: str = "work",
    force: bool = False,
    emit: Emitter = noop_emit,
) -> JovyConfig:
    """Create a project-local JovyKit environment."""
    env_dir = path.resolve()
    if not force:
        ensure_empty_or_jovy_env(env_dir)
    elif (
        env_dir.exists()
        and any(env_dir.iterdir())
        and not (env_dir.parent / "jovy.toml").exists()
        and not (env_dir / "jovy.toml").exists()
    ):
        raise JovyKitError(
            f"Refusing to force initialize non-JovyKit directory: {env_dir}"
        )
    env_dir.mkdir(parents=True, exist_ok=True)

    project_root = env_dir.parent
    (env_dir.parent / "jovy.toml").write_text(
        initial_config_text(
            project_name=project_name or project_root.name,
            env_name=env_dir.name,
            image=image,
            gpus=gpus,
            port=port,
            token=token,
            password=password,
            log_level=log_level,
            image_name=image_name,
            image_tag=image_tag,
            workdir=workdir,
        ),
        encoding="utf-8",
    )

    config = load_config(env_dir)
    config.project_root.mkdir(parents=True, exist_ok=True)
    write_generated_files(config)
    write_state(env_dir, {})

    emit(f"JovyKit environment: {display_path(env_dir)}")
    emit(f"Base image: {config.base_image}")
    emit(f"Project image: {config.image_ref}")
    emit(f"GPU: {config.gpus}")
    emit_jupyter_access(config, emit)
    return config


def add(
    packages: list[str],
    *,
    env: Path | None = None,
    emit: Emitter = noop_emit,
) -> None:
    """Add packages to the project environment manifest."""
    config = load_env(env, emit=emit)
    added = add_packages(config.env_dir / "requirements.txt", packages)
    clear_build_state(config.env_dir)
    if added:
        emit(f"Added: {', '.join(added)}")
        emit("Run jovy install, jovy run, or jovy up to apply changes.")
    else:
        emit("No new packages added.")


def remove(
    packages: list[str],
    *,
    env: Path | None = None,
    emit: Emitter = noop_emit,
) -> None:
    """Remove packages from the project environment manifest."""
    config = load_env(env, emit=emit)
    removed = remove_packages(config.env_dir / "requirements.txt", packages)
    clear_build_state(config.env_dir)
    if removed:
        emit(f"Removed: {', '.join(removed)}")
        emit("Run jovy install, jovy run, or jovy up to apply changes.")
    else:
        emit("No matching packages removed.")


def build(
    *,
    env: Path | None = None,
    no_cache: bool = False,
    pull: bool = False,
    emit: Emitter = noop_emit,
    stream: bool = False,
) -> None:
    """Build the project overlay image."""
    config = load_env(env, emit=emit)
    if stream:
        build_streaming(config, log=emit, no_cache=no_cache, pull=pull)
    else:
        build_image(config, no_cache=no_cache, pull=pull)


def run(
    *,
    env: Path | None = None,
    no_build: bool = False,
    watch: bool = True,
    emit: Emitter = noop_emit,
    stream: bool = False,
) -> None:
    """Build if needed and start Jupyter in the foreground."""
    config = load_env(env, emit=emit)
    install(config, no_build=no_build, emit=emit, stream=stream)
    emit_jupyter_access(config, emit)
    args = ["up"]
    should_watch = watch and config.watch_enabled
    if should_watch:
        args.append("--watch")
        start_watcher(config.env_dir)
    try:
        compose(config, *args, attached=True)
    finally:
        if should_watch:
            stop_watcher(config.env_dir)


def up(
    *,
    env: Path | None = None,
    no_build: bool = False,
    emit: Emitter = noop_emit,
    stream: bool = False,
) -> None:
    """Build if needed and start Jupyter in the background."""
    config = load_env(env, emit=emit)
    install(config, no_build=no_build, emit=emit, stream=stream)
    compose(
        config,
        "up",
        "-d",
        attached=not stream,
        log=emit if stream else None,
    )
    if config.watch_enabled:
        start_watcher(config.env_dir)
    emit_jupyter_access(config, emit)


def down(
    *,
    env: Path | None = None,
    timeout: int | None = None,
    emit: Emitter = noop_emit,
    stream: bool = False,
) -> None:
    """Stop the JovyKit environment."""
    args = ["stop"]
    if timeout is not None:
        args.extend(["--timeout", str(timeout)])
    config = load_env(env, emit=emit)
    stop_watcher(config.env_dir)
    compose(
        config,
        *args,
        attached=not stream,
        log=emit if stream else None,
    )


def restart(
    *,
    env: Path | None = None,
    no_build: bool = False,
    timeout: int | None = None,
    emit: Emitter = noop_emit,
    stream: bool = False,
) -> None:
    """Build if needed and restart Jupyter in the background."""
    config = load_env(env, emit=emit)
    install(config, no_build=no_build, emit=emit, stream=stream)
    stop_watcher(config.env_dir)
    args = ["stop"]
    if timeout is not None:
        args.extend(["--timeout", str(timeout)])
    compose(
        config,
        *args,
        attached=not stream,
        log=emit if stream else None,
    )
    compose(
        config,
        "up",
        "-d",
        attached=not stream,
        log=emit if stream else None,
    )
    if config.watch_enabled:
        start_watcher(config.env_dir)
    emit_jupyter_access(config, emit)


def logs(
    *,
    env: Path | None = None,
    follow: bool = True,
    tail: str = "all",
    since: str | None = None,
    timestamps: bool = False,
    emit: Emitter = noop_emit,
    stream: bool = False,
) -> None:
    """Follow JovyKit container logs."""
    args = ["logs", "--tail", tail]
    if since:
        args.extend(["--since", since])
    if timestamps:
        args.append("--timestamps")
    if follow:
        args.append("-f")
    compose(
        load_env(env, emit=emit),
        *args,
        attached=not stream,
        log=emit if stream else None,
    )


def shell(
    *,
    env: Path | None = None,
    command: str | None = None,
) -> None:
    """Open a bash shell in the running JovyKit container."""
    args = ["exec", "jovy", "bash"]
    if command:
        args.extend(["-lc", command])
    compose(load_env(env), *args, attached=True)


def exec_in_container(
    args: list[str],
    *,
    env: Path | None = None,
    emit: Emitter = noop_emit,
    stream: bool = False,
) -> None:
    """Run a command inside the running JovyKit container."""
    if not args:
        raise JovyKitError(
            "Pass a command to run, for example: jovy exec python --version"
        )
    compose_args = ["exec", "jovy", *args]
    if stream:
        compose_args = ["exec", "-T", "jovy", *args]
    compose(
        load_env(env, emit=emit),
        *compose_args,
        attached=not stream,
        log=emit if stream else None,
    )


def destroy(
    *,
    env: Path | None = None,
    remove_dir: bool = False,
    keep_image: bool = False,
    emit: Emitter = noop_emit,
) -> None:
    """Remove the container, volume, and project overlay image."""
    config = load_env(env, emit=emit)
    stop_watcher(config.env_dir)
    destroy_environment(config, remove_image=not keep_image)
    if remove_dir:
        shutil.rmtree(config.env_dir)
        emit(f"Removed {config.env_dir}")


def clean(*, env: Path | None = None, emit: Emitter = noop_emit) -> None:
    """Remove generated files and local build state."""
    config = load_env(env, emit=emit)
    removed: list[Path] = []
    for name in (
        "Containerfile",
        "compose.yaml",
        ".gitignore",
        "state.json",
        "requirements.lock",
        "watcher.pid",
        "watcher.log",
    ):
        path = config.env_dir / name
        if path.exists():
            path.unlink()
            removed.append(path)
    if removed:
        emit("Removed generated artifacts:")
        for path in removed:
            emit(f"- {display_path(path)}")
    else:
        emit("No generated artifacts to remove.")


def status_data(
    *, env: Path | None = None, emit: Emitter = noop_emit
) -> dict[str, Any]:
    """Return basic JovyKit environment state for the CLI."""
    config = load_env(env, emit=emit)
    stale = is_build_stale(config)
    return {
        "environment": str(config.env_dir),
        "base_image": config.base_image,
        "project_image": config.image_ref,
        "port": config.port,
        "gpus": config.gpus,
        "build_stale": stale,
    }


def status(
    *, env: Path | None = None, json_output: bool = False, emit: Emitter
) -> None:
    """Show basic JovyKit environment state."""
    data = status_data(env=env, emit=emit)
    if json_output:
        emit(json.dumps(data, indent=2, sort_keys=True))
        return
    emit(f"Environment: {data['environment']}")
    emit(f"Base image: {data['base_image']}")
    emit(f"Project image: {data['project_image']}")
    emit(f"Port: {data['port']}")
    emit(f"GPU: {data['gpus']}")
    emit(f"Build stale: {'yes' if data['build_stale'] else 'no'}")
