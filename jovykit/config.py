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

DEFAULT_JUPYTER_TOKEN = "jovykit"


class JovyKitError(RuntimeError):
    """Base class for errors that should be shown cleanly in the CLI."""


class ConfigError(JovyKitError):
    """Raised when an environment configuration cannot be loaded."""


@dataclass(frozen=True)
class JovyConfig:
    """Loaded JovyKit environment configuration."""

    env_dir: Path
    config_path: Path
    project_dir: Path
    project_root: Path
    project_name: str
    base_image: str
    image_name: str
    image_tag: str
    image_target: str | None
    image_platform: str | None
    image_pull: bool
    image_build_args: dict[str, str]
    apt_packages: list[str]
    python_packages: list[str]
    python_constraints: list[str]
    pip_args: list[str]
    uv_link_mode: str
    port: int
    gpus: str
    restart_policy: str
    runtime_user: str | None
    runtime_env: dict[str, str]
    runtime_volumes: dict[str, str]
    jupyter_token: str
    jupyter_log_level: str
    jupyter_lab: bool
    jupyter_command: str | None
    work_mount: str
    home_path: Path
    watch_enabled: bool
    watch_workspace_mode: str
    watch_ignore: list[str]
    watch_rebuild: list[str]
    watch_restart: list[str]
    watch_poll_interval: float

    @property
    def image_ref(self) -> str:
        """Return the project overlay image reference."""
        return f"{self.image_name}:{self.image_tag}"

    @property
    def compose_workdir(self) -> str:
        """Return the host workdir path relative to the Compose project."""
        return os.path.relpath(self.project_root, self.env_dir)

    @property
    def lockfile_path(self) -> Path:
        """Return the dependency lockfile location in the project root."""
        return self.project_dir / "jovy.lock"

    @property
    def compose_home_path(self) -> str:
        """Return the host home path relative to the Compose project."""
        return os.path.relpath(self.home_path, self.env_dir)

    def compose_project_path(self, path: str) -> str:
        """Return a project-root path relative to the Compose project."""
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.project_dir / candidate
        return os.path.relpath(candidate.resolve(), self.env_dir)


def slugify_name(value: str) -> str:
    """Create a Docker-image-friendly project slug."""
    slug = re.sub(r"[^a-z0-9_.-]+", "-", value.lower()).strip("-_.")
    return slug or "project"


def _str_dict(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def load_config(env_dir: Path) -> JovyConfig:
    """Load JovyKit configuration from an environment directory."""
    env_dir = env_dir.resolve()
    config_path = env_dir.parent / "jovy.toml"
    legacy_config_path = env_dir / "jovy.toml"
    if not config_path.exists() and legacy_config_path.exists():
        legacy_config_path.replace(config_path)
    if not config_path.exists():
        raise ConfigError(f"No JovyKit configuration found at {config_path}.")
    try:
        with config_path.open("rb") as handle:
            raw = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Could not parse {config_path}: {exc}") from exc

    project = raw.get("project", {})
    image = raw.get("image", {})
    python = raw.get("python", {})
    runtime = raw.get("runtime", {})
    jupyter = raw.get("jupyter", {})
    mounts = raw.get("mounts", {})
    watch = raw.get("watch", {})

    project_dir = env_dir.parent.resolve()
    project_root = (project_dir / str(project.get("workdir", "work"))).resolve()
    home_value = str(mounts.get("home", f"{env_dir.name}/home"))
    home_path = Path(home_value)
    if not home_path.is_absolute():
        home_path = project_dir / home_path
    try:
        return JovyConfig(
            env_dir=env_dir,
            config_path=config_path.resolve(),
            project_dir=project_dir,
            project_root=project_root,
            project_name=str(project.get("name", project_root.name)),
            base_image=str(image["base"]),
            image_name=str(image["name"]),
            image_tag=str(image.get("tag", "local")),
            image_target=(
                str(image["target"]) if image.get("target") is not None else None
            ),
            image_platform=(
                str(image["platform"]) if image.get("platform") is not None else None
            ),
            image_pull=bool(image.get("pull", False)),
            image_build_args=_str_dict(image.get("build_args", {})),
            apt_packages=_str_list(image.get("apt", {}).get("packages", [])),
            python_packages=_str_list(python.get("packages", [])),
            python_constraints=_str_list(python.get("constraints", [])),
            pip_args=_str_list(python.get("pip_args", [])),
            uv_link_mode=str(python.get("uv_link_mode", "copy")),
            port=int(runtime.get("port", 8888)),
            gpus=str(runtime.get("gpus", "auto")),
            restart_policy=str(runtime.get("restart", "unless-stopped")),
            runtime_user=(
                str(runtime["user"]) if runtime.get("user") is not None else None
            ),
            runtime_env=_str_dict(runtime.get("env", {})),
            runtime_volumes=_str_dict(runtime.get("volumes", {})),
            jupyter_token=str(jupyter.get("token", DEFAULT_JUPYTER_TOKEN) or ""),
            jupyter_log_level=str(jupyter.get("log_level", "ERROR")),
            jupyter_lab=bool(jupyter.get("lab", True)),
            jupyter_command=(
                str(jupyter["command"]) if jupyter.get("command") is not None else None
            ),
            work_mount=str(mounts.get("work", "/home/jovyan/work")),
            home_path=home_path.resolve(),
            watch_enabled=bool(watch.get("enabled", True)),
            watch_workspace_mode=str(watch.get("workspace_mode", "bind")),
            watch_ignore=_str_list(
                watch.get(
                    "ignore",
                    [
                        ".jovy/",
                        ".git/",
                        ".venv/",
                        "__pycache__/",
                        ".mypy_cache/",
                        ".pytest_cache/",
                        ".ruff_cache/",
                    ],
                )
            ),
            watch_rebuild=_str_list(
                watch.get("rebuild", ["../jovy.lock", "Containerfile"])
            ),
            watch_restart=_str_list(watch.get("restart", [])),
            watch_poll_interval=float(watch.get("poll_interval_seconds", 1.0)),
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
    token: str = DEFAULT_JUPYTER_TOKEN,
    log_level: str = "ERROR",
    image_name: str | None = None,
    image_tag: str = "local",
    workdir: str = "work",
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
pull = false

[image.build_args]

[image.apt]
packages = []

[runtime]
port = {port}
gpus = "{gpus}"
attach_mode = "stop-on-ctrl-c"
restart = "unless-stopped"

[runtime.env]

[runtime.volumes]

[jupyter]
lab = true
token = "{token}"
log_level = "{log_level}"

[mounts]
work = "/home/jovyan/work"
home = "{env_name}/home"

[watch]
enabled = true
workspace_mode = "bind"
ignore = [".jovy/", ".git/", ".venv/", "__pycache__/", ".mypy_cache/", ".pytest_cache/", ".ruff_cache/"]
rebuild = ["../jovy.lock", "Containerfile"]
restart = []
poll_interval_seconds = 1.0

[python]
packages = []
constraints = []
pip_args = []
uv_link_mode = "copy"
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
