"""Docker runtime helpers for LabKit."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from labkit.config import LabConfig, read_state, write_state


class DockerError(RuntimeError):
    """Raised when Docker or Docker Compose fails."""


def require_docker() -> None:
    """Ensure Docker is available on PATH."""
    if shutil.which("docker") is None:
        raise DockerError("Docker was not found on PATH.")


def run_command(args: list[str], *, cwd: Path, attached: bool = False, check: bool = True) -> None:
    """Run a Docker command and raise a useful error on failure."""
    require_docker()
    if attached:
        result = subprocess.run(args, cwd=cwd, check=False)
    else:
        result = subprocess.run(args, cwd=cwd, check=False, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="")
    if check and result.returncode != 0:
        raise DockerError(f"Command failed with exit code {result.returncode}: {' '.join(args)}")


def build_signature(config: LabConfig) -> str:
    """Hash the inputs that affect the overlay image."""
    hasher = hashlib.sha256()
    for path in (config.env_dir / "lab.toml", config.env_dir / "requirements.txt"):
        hasher.update(path.name.encode("utf-8"))
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


def is_build_stale(config: LabConfig) -> bool:
    """Return whether the overlay image should be rebuilt."""
    state = read_state(config.env_dir)
    return state.get("build_signature") != build_signature(config)


def build(config: LabConfig, *, no_cache: bool = False) -> None:
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
    if no_cache:
        args.append("--no-cache")
    args.append(".")
    run_command(args, cwd=config.env_dir, attached=True)
    state = read_state(config.env_dir)
    state.update(
        {
            "build_signature": build_signature(config),
            "image": config.image_ref,
            "built_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    write_state(config.env_dir, state)


def compose(config: LabConfig, *args: str, attached: bool = False) -> None:
    """Run docker compose for this environment."""
    run_command(["docker", "compose", "-f", "compose.yaml", *args], cwd=config.env_dir, attached=attached)


def destroy(config: LabConfig, *, remove_image: bool = True) -> None:
    """Remove compose resources and optionally the project image."""
    compose(config, "down", "--volumes", "--remove-orphans", attached=True)
    if remove_image:
        run_command(
            ["docker", "image", "rm", "-f", config.image_ref],
            cwd=config.env_dir,
            attached=False,
            check=False,
        )
