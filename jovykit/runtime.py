"""Docker Compose runtime helpers."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Callable

from jovykit.config import JovyKitError
from jovykit.paths import COMPOSE_FILE, ensure_compose_project

LogCallback = Callable[[str], None]


class DockerError(JovyKitError):
    """Raised when Docker or Compose cannot run."""


def require_docker() -> None:
    """Fail early when the Docker CLI is unavailable."""
    if shutil.which("docker") is None:
        raise DockerError(
            "docker not found in PATH. Install Docker and Compose, or run: jovy install-docker --dry-run"
        )


def compose_args(root: Path, args: Sequence[str]) -> list[str]:
    """Build the Docker Compose command line for a project."""
    return ["docker", "compose", "-f", str(root / COMPOSE_FILE), *args]


def run_command(
    args: Sequence[str],
    *,
    cwd: Path,
    attached: bool = True,
    check: bool = False,
    log: LogCallback | None = None,
) -> int:
    """Run a host command with optional line streaming."""
    require_docker()
    if log is None:
        result = subprocess.run(list(args), cwd=cwd, check=False)
        if check and result.returncode != 0:
            raise DockerError(f"Command failed with exit code {result.returncode}.")
        return result.returncode

    process = subprocess.Popen(
        list(args),
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
        raise DockerError(f"Command failed with exit code {return_code}.")
    return return_code


def compose(
    root: Path | None,
    args: Sequence[str],
    *,
    log: LogCallback | None = None,
    attached: bool = True,
    check: bool = False,
) -> int:
    """Run docker compose in a JovyKit project."""
    resolved = ensure_compose_project(root)
    return run_command(
        compose_args(resolved, args),
        cwd=resolved,
        attached=attached,
        check=check,
        log=log,
    )


def compose_capture(root: Path | None, *args: str, check: bool = False) -> str:
    """Run docker compose and return combined output."""
    require_docker()
    resolved = ensure_compose_project(root)
    result = subprocess.run(
        compose_args(resolved, args),
        cwd=resolved,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if check and result.returncode != 0:
        raise DockerError(
            result.stdout.strip()
            or f"Command failed with exit code {result.returncode}."
        )
    return result.stdout


def compose_ps(root: Path | None) -> str:
    """Return docker compose ps output as JSON."""
    return compose_capture(root, "ps", "--format", "json")


def compose_logs(root: Path | None, *, tail: str = "80") -> str:
    """Return recent Compose logs."""
    return compose_capture(root, "logs", "--tail", tail)


def docker_capture(*args: str) -> tuple[int, str]:
    """Run docker and return return code plus combined output."""
    require_docker()
    result = subprocess.run(
        ["docker", *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return result.returncode, result.stdout.strip()
