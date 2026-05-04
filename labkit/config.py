"""Configuration loading and generation for LabKit environments."""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from labkit.images import resolve_image


@dataclass(frozen=True)
class LabConfig:
    """Loaded LabKit environment configuration."""

    env_dir: Path
    project_root: Path
    project_name: str
    base_image: str
    image_name: str
    image_tag: str
    port: int
    gpus: str
    work_mount: str

    @property
    def image_ref(self) -> str:
        """Return the project overlay image reference."""
        return f"{self.image_name}:{self.image_tag}"


def slugify_name(value: str) -> str:
    """Create a Docker-image-friendly project slug."""
    slug = re.sub(r"[^a-z0-9_.-]+", "-", value.lower()).strip("-_.")
    return slug or "project"


def load_config(env_dir: Path) -> LabConfig:
    """Load LabKit configuration from an environment directory."""
    config_path = env_dir / "lab.toml"
    with config_path.open("rb") as handle:
        raw = tomllib.load(handle)

    project = raw.get("project", {})
    image = raw.get("image", {})
    runtime = raw.get("runtime", {})
    mounts = raw.get("mounts", {})

    project_root = (env_dir / str(project.get("workdir", ".."))).resolve()
    return LabConfig(
        env_dir=env_dir.resolve(),
        project_root=project_root,
        project_name=str(project.get("name", project_root.name)),
        base_image=str(image["base"]),
        image_name=str(image["name"]),
        image_tag=str(image.get("tag", "local")),
        port=int(runtime.get("port", 8888)),
        gpus=str(runtime.get("gpus", "auto")),
        work_mount=str(mounts.get("work", "/home/jovyan/work")),
    )


def initial_config_text(
    *,
    project_name: str,
    env_name: str,
    image: str,
    gpus: str,
    port: int,
) -> str:
    """Render the initial lab.toml content."""
    base_image = resolve_image(image)
    image_name = f"labkit-{slugify_name(project_name)}"
    return f"""[project]
name = "{project_name}"
workdir = ".."
environment = "{env_name}"

[image]
base = "{base_image}"
name = "{image_name}"
tag = "local"

[runtime]
port = {port}
gpus = "{gpus}"
attach_mode = "stop-on-ctrl-c"

[jupyter]
lab = true
token = "auto"
log_level = "ERROR"

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
