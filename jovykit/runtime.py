"""Docker runtime helpers for JovyKit."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from datetime import datetime, timezone
from collections.abc import Callable
from pathlib import Path
from typing import Any

from jovykit.config import JovyConfig, JovyKitError, read_state, write_state


class DockerError(JovyKitError):
    """Raised when Docker or Docker Compose fails."""


LogCallback = Callable[[str], None]


def require_docker() -> None:
    """Ensure Docker is available on PATH."""
    if shutil.which("docker") is None:
        raise DockerError("Docker was not found on PATH.")


def stream_command(
    args: list[str],
    *,
    cwd: Path,
    log: LogCallback,
    check: bool = True,
    require_docker_path: bool = True,
) -> int:
    """Run a command and stream combined output to a callback."""
    if require_docker_path:
        require_docker()
    process = subprocess.Popen(
        args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        log(line.rstrip("\n"))
    return_code = process.wait()
    if check and return_code != 0:
        raise DockerError(
            f"Command failed with exit code {return_code}: {' '.join(args)}"
        )
    return return_code


def run_command(
    args: list[str],
    *,
    cwd: Path,
    attached: bool = False,
    check: bool = True,
    log: LogCallback | None = None,
    require_docker_path: bool = True,
) -> None:
    """Run a Docker command and raise a useful error on failure."""
    if log is not None:
        stream_command(
            args,
            cwd=cwd,
            log=log,
            check=check,
            require_docker_path=require_docker_path,
        )
        return
    if require_docker_path:
        require_docker()
    result: subprocess.CompletedProcess[Any]
    if attached:
        result = subprocess.run(args, cwd=cwd, check=False)
    else:
        result = subprocess.run(
            args, cwd=cwd, check=False, capture_output=True, text=True
        )
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="")
    if check and result.returncode != 0:
        raise DockerError(
            f"Command failed with exit code {result.returncode}: {' '.join(args)}"
        )


def build_signature(config: JovyConfig) -> str:
    """Hash the inputs that affect the overlay image."""
    hasher = hashlib.sha256()
    for path in (config.config_path, config.env_dir / "jovy.lock"):
        hasher.update(path.name.encode("utf-8"))
        if path.exists():
            hasher.update(path.read_bytes())
        else:
            hasher.update(b"<missing>")
    for constraint in config.python_constraints:
        path = Path(constraint)
        if not path.is_absolute():
            path = config.project_dir / path
        hasher.update(f"constraint:{constraint}".encode("utf-8"))
        if path.exists():
            hasher.update(path.read_bytes())
        else:
            hasher.update(b"<missing>")
    return hasher.hexdigest()


def is_build_stale(config: JovyConfig) -> bool:
    """Return whether the overlay image should be rebuilt."""
    if not (config.env_dir / "jovy.lock").exists():
        return True
    state = read_state(config.env_dir)
    return state.get("build_signature") != build_signature(config)


def compile_requirements_lock(
    config: JovyConfig,
    *,
    input_file: Path,
    output_file: Path,
    constraints: list[Path],
    upgrade: bool = False,
    log: LogCallback | None = None,
) -> None:
    """Compile direct requirements to a pinned lockfile with uv."""
    args = [
        "uv",
        "pip",
        "compile",
        str(input_file),
        "--output-file",
        str(output_file),
        "--no-progress",
        "--no-annotate",
        "--custom-compile-command",
        "jovy install",
    ]
    for constraint in constraints:
        args.extend(["--constraints", str(constraint)])
    if upgrade:
        args.append("--upgrade")
    run_command(
        args,
        cwd=config.project_dir,
        attached=log is None,
        log=log,
        require_docker_path=False,
    )


def build(config: JovyConfig, *, no_cache: bool = False, pull: bool = False) -> None:
    """Build the project overlay image."""
    args = [
        "docker",
        "buildx",
        "build",
        "--load",
        "-f",
        "Containerfile",
        "-t",
        config.image_ref,
    ]
    if config.image_target:
        args.extend(["--target", config.image_target])
    if config.image_platform:
        args.extend(["--platform", config.image_platform])
    for key, value in config.image_build_args.items():
        args.extend(["--build-arg", f"{key}={value}"])
    if no_cache:
        args.append("--no-cache")
    if pull or config.image_pull:
        args.append("--pull")
    args.append(".")
    run_command(args, cwd=config.env_dir, attached=True)
    mark_built(config)


def build_streaming(
    config: JovyConfig,
    *,
    log: LogCallback,
    no_cache: bool = False,
    pull: bool = False,
) -> None:
    """Build the project overlay image and stream output to a callback."""
    args = [
        "docker",
        "buildx",
        "build",
        "--load",
        "-f",
        "Containerfile",
        "-t",
        config.image_ref,
    ]
    if config.image_target:
        args.extend(["--target", config.image_target])
    if config.image_platform:
        args.extend(["--platform", config.image_platform])
    for key, value in config.image_build_args.items():
        args.extend(["--build-arg", f"{key}={value}"])
    if no_cache:
        args.append("--no-cache")
    if pull or config.image_pull:
        args.append("--pull")
    args.append(".")
    run_command(args, cwd=config.env_dir, log=log)
    mark_built(config)


def mark_built(config: JovyConfig) -> None:
    """Persist the current build signature."""
    state = read_state(config.env_dir)
    state.update(
        {
            "build_signature": build_signature(config),
            "image": config.image_ref,
            "built_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    write_state(config.env_dir, state)


def compose(
    config: JovyConfig,
    *args: str,
    attached: bool = False,
    check: bool = True,
    log: LogCallback | None = None,
) -> None:
    """Run docker compose for this environment."""
    kwargs: dict[str, Any] = {
        "cwd": config.env_dir,
        "attached": attached,
        "check": check,
    }
    if log is not None:
        kwargs["log"] = log
    run_command(
        ["docker", "compose", "-f", "compose.yaml", *args],
        **kwargs,
    )


def compose_capture(config: JovyConfig, *args: str, check: bool = False) -> str:
    """Run docker compose and return combined output."""
    require_docker()
    result = subprocess.run(
        ["docker", "compose", "-f", "compose.yaml", *args],
        cwd=config.env_dir,
        check=False,
        capture_output=True,
        text=True,
    )
    output = f"{result.stdout}{result.stderr}"
    if check and result.returncode != 0:
        raise DockerError(
            f"Command failed with exit code {result.returncode}: docker compose -f compose.yaml {' '.join(args)}"
        )
    return output


def compose_ps(config: JovyConfig) -> str:
    """Return Docker Compose service status as JSON when possible."""
    return compose_capture(config, "ps", "--format", "json", check=False)


def compose_logs(config: JovyConfig, *, tail: str = "80") -> str:
    """Return recent Docker Compose logs."""
    return compose_capture(config, "logs", "--tail", tail, check=False)


def run_host_command(args: list[str], *, cwd: Path, log: LogCallback) -> int:
    """Run a host command and stream combined output to a callback."""
    return stream_command(
        args,
        cwd=cwd,
        log=log,
        check=False,
        require_docker_path=False,
    )


def destroy(
    config: JovyConfig,
    *,
    remove_image: bool = True,
    log: LogCallback | None = None,
) -> None:
    """Remove compose resources and optionally the project image."""
    compose(
        config,
        "down",
        "--volumes",
        "--remove-orphans",
        attached=log is None,
        log=log,
    )
    if remove_image:
        run_command(
            ["docker", "image", "rm", "-f", config.image_ref],
            cwd=config.env_dir,
            attached=False,
            check=False,
            log=log,
        )
        state = read_state(config.env_dir)
        for key in ("build_signature", "image", "built_at"):
            state.pop(key, None)
        write_state(config.env_dir, state)
