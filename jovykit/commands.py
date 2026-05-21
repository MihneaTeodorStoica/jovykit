"""High-level CLI commands."""

from __future__ import annotations

import json
import shutil
import subprocess
import webbrowser
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode

import yaml

from jovykit import docker_install, runtime
from jovykit.config import DEFAULT_JUPYTER_TOKEN, JovyKitError
from jovykit.images import (
    DEFAULT_PYTHON_VERSION,
    IMAGE_LEVELS,
    image_level_from_reference,
    python_version_from_image,
    resolve_image_level,
)
from jovykit.paths import (
    DEFAULT_JUPYTER_DIR,
    DEFAULT_WORK_DIR,
    SERVICE_NAME,
    compose_path,
    containerfile_path,
    devcontainer_path,
    ensure_compose_project,
    legacy_config_path,
    project_root,
    requirements_path,
)
from jovykit.templates import (
    render_compose,
    render_containerfile,
    render_devcontainer,
    render_gitignore,
    render_requirements,
)

Emitter = Callable[[str], None]
VALID_GPU = ("none", "all")


@dataclass(frozen=True)
class ProjectSettings:
    """Editable project settings."""

    level: str
    python_version: str
    gpu: str
    port: int
    token: str


def noop_emit(_: str) -> None:
    """Default sink for command messages."""


def init_git_repository(root: Path) -> bool:
    """Initialize a git repository if one is not already present."""
    if (root / ".git").exists():
        return False
    git = shutil.which("git")
    if git is None:
        raise JovyKitError("git not found in PATH.")
    result = subprocess.run(
        [git, "init"],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if result.returncode != 0:
        message = result.stdout.strip() or "git init failed."
        raise JovyKitError(message)
    return True


def init_project(
    root: Path | None = None,
    *,
    level: str = "base",
    python_version: str = DEFAULT_PYTHON_VERSION,
    gpu: str | None = None,
    port: int = 8888,
    token: str = DEFAULT_JUPYTER_TOKEN,
    force: bool = False,
    emit: Emitter = noop_emit,
) -> Path:
    """Create a Compose-first JovyKit project."""
    resolved = project_root(root)
    gpu = detect_gpu_mode() if gpu is None else gpu
    if gpu not in VALID_GPU:
        raise JovyKitError("GPU must be one of: none, all.")
    if legacy_config_path(resolved).exists():
        raise JovyKitError(
            "jovy.toml is no longer used. Move settings into compose.yaml, then remove jovy.toml."
        )

    compose_file = compose_path(resolved)
    containerfile = containerfile_path(resolved)
    requirements_file = requirements_path(resolved)
    devcontainer_file = devcontainer_path(resolved)
    gitignore_file = resolved / ".gitignore"
    if not force and (
        compose_file.exists()
        or containerfile.exists()
        or requirements_file.exists()
        or devcontainer_file.exists()
        or gitignore_file.exists()
    ):
        raise JovyKitError(
            "compose.yaml, Dockerfile, requirements.txt, .devcontainer/devcontainer.json, or .gitignore already exists. Use --force to overwrite."
        )

    resolved.mkdir(parents=True, exist_ok=True)
    (resolved / DEFAULT_WORK_DIR).mkdir(exist_ok=True)
    (resolved / DEFAULT_JUPYTER_DIR).mkdir(exist_ok=True)
    devcontainer_file.parent.mkdir(exist_ok=True)
    compose_file.write_text(
        render_compose(
            project_name=resolved.name,
            level=level,
            python_version=python_version,
            gpu=gpu,
            port=port,
            token=token,
        ),
        encoding="utf-8",
    )
    containerfile.write_text(
        render_containerfile(level=level, python_version=python_version),
        encoding="utf-8",
    )
    requirements_file.write_text(render_requirements(), encoding="utf-8")
    devcontainer_file.write_text(render_devcontainer(resolved.name), encoding="utf-8")
    gitignore_file.write_text(render_gitignore(), encoding="utf-8")
    initialized_git = init_git_repository(resolved)
    emit("Created compose.yaml")
    emit("Created Dockerfile")
    emit("Created requirements.txt")
    emit("Created .devcontainer/devcontainer.json")
    emit("Created .gitignore")
    emit("Created work/")
    emit("Created .jupyter/")
    if initialized_git:
        emit("Initialized git repository")
    return resolved


def compose_passthrough(
    args: Sequence[str],
    *,
    root: Path | None = None,
    log: runtime.LogCallback | None = None,
    attached: bool = True,
) -> int:
    """Forward a command to docker compose."""
    return runtime.compose(root, list(args), log=log, attached=attached)


def compose_alias(
    command: str,
    args: Sequence[str] = (),
    *,
    root: Path | None = None,
) -> int:
    """Run a named docker compose command."""
    return runtime.compose(root, [command, *args])


def up(args: Sequence[str] = (), *, root: Path | None = None) -> int:
    """Run docker compose up."""
    return compose_alias("up", args, root=root)


def down(args: Sequence[str] = (), *, root: Path | None = None) -> int:
    """Run docker compose down."""
    return compose_alias("down", args, root=root)


def start(args: Sequence[str] = (), *, root: Path | None = None) -> int:
    """Run docker compose start."""
    return compose_alias("start", args, root=root)


def stop(args: Sequence[str] = (), *, root: Path | None = None) -> int:
    """Run docker compose stop."""
    return compose_alias("stop", args, root=root)


def restart(args: Sequence[str] = (), *, root: Path | None = None) -> int:
    """Run docker compose restart."""
    return compose_alias("restart", args, root=root)


def config(args: Sequence[str] = (), *, root: Path | None = None) -> int:
    """Run docker compose config."""
    return compose_alias("config", args, root=root)


def logs(args: Sequence[str] = (), *, root: Path | None = None) -> int:
    """Run docker compose logs."""
    return compose_alias("logs", args, root=root)


def shell(args: Sequence[str] = (), *, root: Path | None = None) -> int:
    """Open a shell or run a command in the JovyKit service."""
    command = list(args) or ["bash"]
    return runtime.compose(root, ["exec", SERVICE_NAME, *command])


def run(args: Sequence[str], *, root: Path | None = None) -> int:
    """Run a one-off command in the JovyKit service."""
    if not args:
        raise JovyKitError("Command required.")
    return runtime.compose(root, ["run", "--rm", SERVICE_NAME, *args])


def build(args: Sequence[str] = (), *, root: Path | None = None) -> int:
    """Run docker compose build."""
    return compose_alias("build", args, root=root)


def watch(args: Sequence[str] = (), *, root: Path | None = None) -> int:
    """Run docker compose watch."""
    return compose_alias("watch", args, root=root)


def add_packages(
    packages: Sequence[str],
    *,
    root: Path | None = None,
    emit: Emitter = noop_emit,
) -> None:
    """Add dependencies to requirements.txt."""
    if not packages:
        raise JovyKitError("Package name required.")
    lines = _load_requirements(root)
    existing = {
        _dependency_name(spec)
        for line in lines
        if (spec := _requirement_spec(line)) is not None
    }
    added: list[str] = []
    for package in packages:
        spec = package.strip()
        if not spec:
            continue
        name = _dependency_name(spec)
        if name not in existing:
            lines.append(spec)
            existing.add(name)
            added.append(spec)
    _save_requirements(root, lines)
    for package in added:
        emit(f"Added {package}")
    emit("Saved requirements.txt")


def remove_packages(
    packages: Sequence[str],
    *,
    root: Path | None = None,
    emit: Emitter = noop_emit,
) -> None:
    """Remove dependencies from requirements.txt."""
    if not packages:
        raise JovyKitError("Package name required.")
    names = {
        _dependency_name(package.strip()) for package in packages if package.strip()
    }
    kept: list[str] = []
    removed: list[str] = []
    for line in _load_requirements(root):
        spec = _requirement_spec(line)
        if spec is None:
            kept.append(line)
            continue
        name = _dependency_name(spec)
        if name not in names:
            kept.append(line)
            continue
        removed.append(spec)
    _save_requirements(root, kept)
    for package in removed:
        emit(f"Removed {package}")
    emit("Saved requirements.txt")


def load_project_settings(root: Path | None = None) -> ProjectSettings:
    """Load editable settings from compose.yaml."""
    resolved = ensure_compose_project(root)
    data = yaml.safe_load(compose_path(resolved).read_text(encoding="utf-8")) or {}
    service: dict[str, Any] = data.get("services", {}).get(SERVICE_NAME, {})
    build: dict[str, Any] = service.get("build") or {}
    args = build.get("args") or {}
    base_image = _read_build_arg(args, "JOVY_BASE_IMAGE") or resolve_image_level("base")
    level = image_level_from_reference(base_image) or "base"
    python_version = _read_build_arg(
        args, "PYTHON_VERSION"
    ) or python_version_from_image(base_image)
    gpu = _read_gpu_mode(service)
    port = _read_port(service)
    token = _read_environment_value(service, "JUPYTER_TOKEN") or DEFAULT_JUPYTER_TOKEN
    return ProjectSettings(
        level=level,
        python_version=python_version,
        gpu=gpu,
        port=port,
        token=token,
    )


def save_project_settings(
    root: Path | None = None,
    *,
    level: str,
    python_version: str,
    gpu: str,
    port: int,
    token: str,
    emit: Emitter = noop_emit,
) -> None:
    """Save editable settings to compose.yaml and Dockerfile."""
    resolved = ensure_compose_project(root)
    if level not in IMAGE_LEVELS:
        levels = ", ".join(IMAGE_LEVELS)
        raise JovyKitError(f"Image level must be one of: {levels}.")
    if gpu not in VALID_GPU:
        raise JovyKitError("GPU must be one of: none, all.")
    if port < 1 or port > 65535:
        raise JovyKitError("Port must be between 1 and 65535.")
    if not python_version:
        raise JovyKitError("Python version is required.")
    token = token.strip()
    if not token:
        raise JovyKitError("Jupyter token is required.")
    compose_path(resolved).write_text(
        render_compose(
            project_name=resolved.name,
            level=level,
            python_version=python_version,
            gpu=gpu,
            port=port,
            token=token,
        ),
        encoding="utf-8",
    )
    containerfile_path(resolved).write_text(
        render_containerfile(level=level, python_version=python_version),
        encoding="utf-8",
    )
    emit("Saved compose.yaml")
    emit("Saved Dockerfile")
    if not requirements_path(resolved).exists():
        requirements_path(resolved).write_text(render_requirements(), encoding="utf-8")
        emit("Created requirements.txt")


def _load_requirements(root: Path | None = None) -> list[str]:
    resolved = ensure_compose_project(root)
    path = requirements_path(resolved)
    if not path.exists():
        raise JovyKitError("requirements.txt not found. Run: jovy init")
    return path.read_text(encoding="utf-8").splitlines()


def _save_requirements(root: Path | None, lines: list[str]) -> None:
    resolved = ensure_compose_project(root)
    content = "\n".join(lines)
    if content:
        content += "\n"
    requirements_path(resolved).write_text(content, encoding="utf-8")


def _requirement_spec(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith(("#", "-")):
        return None
    return stripped.split(" #", 1)[0].strip()


def _dependency_name(spec: str) -> str:
    spec = spec.split(" #", 1)[0].strip()
    for separator in ("==", ">=", "<=", "!=", "~=", "=", ">", "<"):
        if separator in spec:
            spec = spec.split(separator, 1)[0]
            break
    return spec.split("[", 1)[0].strip().lower()


def _read_build_arg(args: object, name: str) -> str | None:
    if isinstance(args, dict):
        value = args.get(name)
        return None if value is None else str(value)
    if isinstance(args, list):
        prefix = f"{name}="
        for item in args:
            text = str(item)
            if text.startswith(prefix):
                return text[len(prefix) :]
    return None


def _read_gpu_mode(service: dict[str, Any]) -> str:
    if service.get("gpus") == "all":
        return "all"
    return "none"


def _read_port(service: dict[str, Any]) -> int:
    for port in service.get("ports", []) or []:
        parts = str(port).split(":")
        if len(parts) >= 3 and parts[-1] == "8888":
            return int(parts[-2])
        if len(parts) == 2 and parts[-1] == "8888":
            return int(parts[0])
    return 8888


def _read_environment_value(service: dict[str, Any], name: str) -> str | None:
    environment = service.get("environment") or {}
    if isinstance(environment, dict):
        value = environment.get(name)
        return None if value is None else str(value)
    if isinstance(environment, list):
        prefix = f"{name}="
        for item in environment:
            text = str(item)
            if text.startswith(prefix):
                return text[len(prefix) :]
    return None


def jupyter_url(root: Path | None = None) -> str:
    """Return the local Lab URL from compose.yaml."""
    resolved = ensure_compose_project(root)
    data = yaml.safe_load(compose_path(resolved).read_text(encoding="utf-8")) or {}
    service: dict[str, Any] = data.get("services", {}).get(SERVICE_NAME, {})
    token = _read_environment_value(service, "JUPYTER_TOKEN") or DEFAULT_JUPYTER_TOKEN
    query = urlencode({"token": token})
    for port in service.get("ports", []) or []:
        parts = str(port).split(":")
        if len(parts) >= 3 and parts[-1] == "8888":
            return f"http://127.0.0.1:{parts[-2]}/lab?{query}"
        if len(parts) == 2 and parts[-1] == "8888":
            return f"http://127.0.0.1:{parts[0]}/lab?{query}"
    return f"http://127.0.0.1:8888/lab?{query}"


def open_browser(root: Path | None = None) -> str:
    """Open the Jupyter Lab URL."""
    url = jupyter_url(root)
    webbrowser.open(url)
    return url


def install_docker(
    *,
    yes: bool = False,
    skip_hello_world: bool = False,
    emit: Emitter = noop_emit,
) -> None:
    """Print or run the Docker install plan."""
    docker_install.install_docker(
        yes=yes,
        skip_hello_world=skip_hello_world,
        emit=emit,
    )


def doctor(root: Path | None = None, *, emit: Emitter = noop_emit) -> None:
    """Print basic host and project diagnostics."""
    setup_needed = False
    if shutil.which("docker") is None:
        emit("docker: missing")
        emit("compose: missing")
        emit("daemon: unavailable")
        setup_needed = True
    else:
        code, version = runtime.docker_capture("--version")
        emit(f"docker: {version if code == 0 else 'unavailable'}")
        setup_needed = setup_needed or code != 0
        code, compose_version = runtime.docker_capture("compose", "version")
        emit(f"compose: {compose_version if code == 0 else 'unavailable'}")
        setup_needed = setup_needed or code != 0
        code, _ = runtime.docker_capture("info")
        emit(f"daemon: {'reachable' if code == 0 else 'unavailable'}")
        setup_needed = setup_needed or code != 0
    if setup_needed:
        emit("setup: run jovy install-docker --dry-run")

    emit(f"gpu: {'detected' if detect_gpu_mode() == 'all' else 'not detected'}")
    try:
        resolved = ensure_compose_project(root)
    except JovyKitError as exc:
        emit(f"project: {exc}")
    else:
        emit(f"project: {compose_path(resolved)}")


def status(root: Path | None = None) -> str:
    """Return a short Compose status string."""
    raw = runtime.compose_ps(root)
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        return "stopped"
    if isinstance(items, dict):
        items = [items]
    states = [
        str(item.get("State") or item.get("Status") or "unknown") for item in items
    ]
    return ", ".join(states) if states else "stopped"


def detect_gpu_mode() -> str:
    """Return all when the host appears to expose a GPU."""
    if shutil.which("nvidia-smi") is not None:
        return "all"
    if any(Path("/dev").glob("nvidia*")):
        return "all"
    if any(Path("/dev/dri").glob("renderD*")):
        return "all"
    return "none"
