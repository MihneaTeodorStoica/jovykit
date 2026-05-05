"""Configuration loading and generation for JovyKit environments."""

from __future__ import annotations

import json
import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jovykit.images import resolve_image


class JovyKitError(RuntimeError):
    """Base class for errors that should be shown cleanly in the CLI."""


class ConfigError(JovyKitError):
    """Raised when an environment configuration cannot be loaded."""


@dataclass(frozen=True)
class JovyConfig:
    """Loaded JovyKit environment configuration."""

    env_dir: Path
    project_root: Path
    project_name: str
    base_image: str
    image_name: str
    image_tag: str
    port: int
    gpus: str
    jupyter_token: str
    jupyter_log_level: str
    work_mount: str

    @property
    def image_ref(self) -> str:
        """Return the project overlay image reference."""
        return f"{self.image_name}:{self.image_tag}"

    @property
    def compose_workdir(self) -> str:
        """Return the host workdir path relative to the Compose project."""
        return os.path.relpath(self.project_root, self.env_dir)


def slugify_name(value: str) -> str:
    """Create a Docker-image-friendly project slug."""
    slug = re.sub(r"[^a-z0-9_.-]+", "-", value.lower()).strip("-_.")
    return slug or "project"


def load_config(env_dir: Path) -> JovyConfig:
    """Load JovyKit configuration from an environment directory."""
    config_path = env_dir / "jovy.toml"
    if not config_path.exists():
        raise ConfigError(f"No JovyKit configuration found at {config_path}.")
    try:
        with config_path.open("rb") as handle:
            raw = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Could not parse {config_path}: {exc}") from exc

    project = raw.get("project", {})
    image = raw.get("image", {})
    runtime = raw.get("runtime", {})
    jupyter = raw.get("jupyter", {})
    mounts = raw.get("mounts", {})

    project_root = (env_dir / str(project.get("workdir", ".."))).resolve()
    try:
        return JovyConfig(
            env_dir=env_dir.resolve(),
            project_root=project_root,
            project_name=str(project.get("name", project_root.name)),
            base_image=str(image["base"]),
            image_name=str(image["name"]),
            image_tag=str(image.get("tag", "local")),
            port=int(runtime.get("port", 8888)),
            gpus=str(runtime.get("gpus", "auto")),
            jupyter_token=str(jupyter.get("token", "auto")),
            jupyter_log_level=str(jupyter.get("log_level", "ERROR")),
            work_mount=str(mounts.get("work", "/home/jovyan/work")),
        )
    except KeyError as exc:
        raise ConfigError(f"Missing required setting in {config_path}: {exc}") from exc
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"Invalid setting in {config_path}: {exc}") from exc


def initial_config_text(
    *,
    project_name: str,
    env_name: str,
    image: str,
    gpus: str,
    port: int,
    token: str = "auto",
    log_level: str = "ERROR",
    image_name: str | None = None,
    image_tag: str = "local",
    workdir: str = "../work",
) -> str:
    """Render the initial jovy.toml content."""
    base_image = resolve_image(image)
    resolved_image_name = image_name or f"jovykit-{slugify_name(project_name)}"
    return f"""[project]
name = "{project_name}"
workdir = "{workdir}"
environment = "{env_name}"

[image]
base = "{base_image}"
name = "{resolved_image_name}"
tag = "{image_tag}"

[runtime]
port = {port}
gpus = "{gpus}"
attach_mode = "stop-on-ctrl-c"

[jupyter]
lab = true
token = "{token}"
log_level = "{log_level}"

[mounts]
work = "/home/jovyan/work"
"""


def read_state(env_dir: Path) -> dict[str, Any]:
    """Read runtime/build state, returning an empty state when absent."""
    state_path = env_dir / "state.json"
    if not state_path.exists():
        return {}
    return json.loads(state_path.read_text(encoding="utf-8"))


def write_state(env_dir: Path, state: dict[str, Any]) -> None:
    """Write runtime/build state."""
    (env_dir / "state.json").write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
