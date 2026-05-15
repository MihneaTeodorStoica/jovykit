"""Docker runtime helpers for JovyKit."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tqdm import tqdm

from jovykit.config import JovyConfig, JovyKitError, read_state, write_state


class DockerError(JovyKitError):
    """Raised when Docker or Docker Compose fails."""


LogCallback = Callable[[str], None]


def _extract_error_detail(output: str) -> str | None:
    """Return the most useful error detail from command output."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return None
    for line in reversed(lines):
        if "error" in line.lower():
            return line.removeprefix("Error response from daemon: ").strip()
    return lines[-1]


def _format_command_error(args: list[str], returncode: int, output: str) -> str:
    """Build a concise command failure message."""
    base = f"Command failed with exit code {returncode}: {' '.join(args)}"
    detail = _extract_error_detail(output)
    if detail:
        return f"{base}\n{detail}"
    return base


def _completed_output(result: subprocess.CompletedProcess[Any]) -> str:
    """Return completed process output as text."""
    stdout = (
        result.stdout.decode() if isinstance(result.stdout, bytes) else result.stdout
    )
    stderr = (
        result.stderr.decode() if isinstance(result.stderr, bytes) else result.stderr
    )
    return f"{stdout or ''}{stderr or ''}"


def _is_missing_image_error(output: str) -> bool:
    """Return True when Docker reports that an image does not exist."""
    detail = (_extract_error_detail(output) or "").lower()
    return "no such image" in detail


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
    captured: list[str] = []
    for line in process.stdout:
        text = line.rstrip("\n")
        captured.append(text)
        log(text)
    return_code = process.wait()
    if check and return_code != 0:
        raise DockerError(_format_command_error(args, return_code, "\n".join(captured)))
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
    if check and result.returncode != 0:
        output = _completed_output(result)
        raise DockerError(_format_command_error(args, result.returncode, output))


def build_signature(config: JovyConfig) -> str:
    """Hash the inputs that affect the overlay image."""
    hasher = hashlib.sha256()
    for path in (config.config_path, config.lockfile_path):
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
    if not config.lockfile_path.exists():
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


def _noop_log(line: str) -> None:
    """No-op log callback for suppressing output."""
    pass


def _supports_tqdm_progress() -> bool:
    """Return whether stderr is a plain terminal suitable for tqdm."""
    stderr = sys.stderr
    if stderr is None:
        return False
    real_stderr = sys.__stderr__
    if real_stderr is None or stderr is not real_stderr:
        return False
    try:
        return stderr.isatty() and stderr.fileno() >= 0
    except (AttributeError, OSError, ValueError):
        return False


def _run_command_with_progress(args: list[str], *, cwd: Path, description: str) -> None:
    """Run a streamed command and tick tqdm once per output line."""
    if not _supports_tqdm_progress():
        run_command(args, cwd=cwd)
        return
    with tqdm(
        total=None,
        desc=description,
        unit="line",
        dynamic_ncols=True,
        leave=False,
    ) as progress:

        def advance(_line: str) -> None:
            progress.update(1)

        try:
            run_command(args, cwd=cwd, log=advance)
        except ValueError as exc:
            if "fds_to_keep" not in str(exc):
                raise
            run_command(args, cwd=cwd)


def build(
    config: JovyConfig,
    *,
    no_cache: bool = False,
    pull: bool = False,
    verbose: bool = False,
) -> None:
    """Build the project overlay image."""
    args = [
        "docker",
        "buildx",
        "build",
        "--load",
        "-f",
        f"{config.env_dir.name}/Containerfile",
        "-t",
        config.image_ref,
    ]
    if config.image_target:
        args.extend(["--target", config.image_target])
    if config.image_platform:
        args.extend(["--platform", config.image_platform])
    for key, value in config.effective_image_build_args.items():
        args.extend(["--build-arg", f"{key}={value}"])
    for key, value in config.image_labels.items():
        args.extend(["--label", f"{key}={value}"])
    if no_cache:
        args.append("--no-cache")
    if pull or config.image_pull:
        args.append("--pull")
    args.append(".")
    if verbose:
        run_command(args, cwd=config.project_dir, attached=True)
    else:
        _run_command_with_progress(
            args,
            cwd=config.project_dir,
            description="Building JovyKit image",
        )
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
        f"{config.env_dir.name}/Containerfile",
        "-t",
        config.image_ref,
    ]
    if config.image_target:
        args.extend(["--target", config.image_target])
    if config.image_platform:
        args.extend(["--platform", config.image_platform])
    for key, value in config.effective_image_build_args.items():
        args.extend(["--build-arg", f"{key}={value}"])
    for key, value in config.image_labels.items():
        args.extend(["--label", f"{key}={value}"])
    if no_cache:
        args.append("--no-cache")
    if pull or config.image_pull:
        args.append("--pull")
    args.append(".")
    run_command(args, cwd=config.project_dir, log=log)
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
        command = ["docker", "compose", "-f", "compose.yaml", *args]
        raise DockerError(_format_command_error(command, result.returncode, output))
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
    remove_volumes: bool = False,
    log: LogCallback | None = None,
) -> None:
    """Remove compose resources and optionally the project image."""
    args = ["down", "--remove-orphans"]
    if remove_volumes:
        args.append("--volumes")
    compose(
        config,
        *args,
        log=log if log is not None else _noop_log,
    )
    if remove_image:
        image_rm_args = ["docker", "image", "rm", "-f", config.image_ref]
        result = subprocess.run(
            image_rm_args,
            cwd=config.env_dir,
            check=False,
            capture_output=True,
            text=True,
        )
        output = f"{result.stdout}{result.stderr}"
        if result.returncode != 0 and not _is_missing_image_error(output):
            raise DockerError(
                _format_command_error(image_rm_args, result.returncode, output)
            )
        if log is not None and _is_missing_image_error(output):
            log(f"Image already absent: {config.image_ref}")
        state = read_state(config.env_dir)
        for key in ("build_signature", "image", "built_at"):
            state.pop(key, None)
        write_state(config.env_dir, state)
