"""High-level CLI commands."""

from __future__ import annotations

import json
import socket
import re
import shutil
import subprocess
import webbrowser
from contextlib import closing
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import yaml

from jovykit import docker_install, runtime
from jovykit.config import (
    JovyKitError,
    generate_default_jupyter_token,
)
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
_DEFAULT_PORT = 8888
_MAX_PORT = 65535
_REQUIREMENT_NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9._-]*(?:[A-Za-z0-9])?")
_DOCKERFILE_BASE_IMAGE_RE = re.compile(r"^\s*ARG\s+JOVY_BASE_IMAGE=(.+?)\s*$")


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
    run_git(root, "init")
    return True


def run_git(root: Path, *args: str) -> str:
    """Run a git command in the project root."""
    git = shutil.which("git")
    if git is None:
        raise JovyKitError("git not found in PATH.")
    result = subprocess.run(
        [git, *args],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if result.returncode != 0:
        command = " ".join(("git", *args))
        message = result.stdout.strip() or f"{command} failed."
        raise JovyKitError(message)
    return result.stdout


def commit_initial_project(root: Path, files: Sequence[Path]) -> None:
    """Commit the files created by initialization."""
    relative_files = [path.relative_to(root).as_posix() for path in files]
    run_git(root, "add", "--", *relative_files)
    run_git(
        root,
        "-c",
        "user.name=JovyKit",
        "-c",
        "user.email=jovykit@users.noreply.github.com",
        "commit",
        "-m",
        "Initialize JovyKit project",
    )


def init_project(
    root: Path | None = None,
    *,
    level: str = "base",
    python_version: str = DEFAULT_PYTHON_VERSION,
    gpu: str | None = None,
    port: int | str = _DEFAULT_PORT,
    token: str | None = None,
    force: bool = False,
    emit: Emitter = noop_emit,
) -> Path:
    """Create a Compose-first JovyKit project."""
    resolved = project_root(root)
    gpu = detect_gpu_mode() if gpu is None else gpu
    token = generate_default_jupyter_token() if token is None else token
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

    resolved_port = _resolve_port(port)
    if (
        resolved_port != _DEFAULT_PORT
        and isinstance(port, str)
        and port.strip().lower() == "auto"
    ):
        emit(
            f"Warning: selected port {resolved_port} instead of default {_DEFAULT_PORT}."
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
            port=resolved_port,
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
    if initialized_git:
        commit_initial_project(
            resolved,
            [
                compose_file,
                containerfile,
                requirements_file,
                devcontainer_file,
                gitignore_file,
            ],
        )
    emit("Created compose.yaml")
    emit("Created Dockerfile")
    emit("Created requirements.txt")
    emit("Created .devcontainer/devcontainer.json")
    emit("Created .gitignore")
    emit("Created work/")
    emit("Created .jupyter/")
    if initialized_git:
        emit("Initialized git repository")
        emit("Committed initial project files")
    return resolved


def _is_free_port(port: int, host: str = "127.0.0.1") -> bool:
    """Return True when a TCP port is available on localhost."""
    if port <= 0 or port > _MAX_PORT:
        return False
    try:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.bind((host, port))
            return True
    except OSError:
        return False


def _resolve_auto_port() -> int:
    """Find the first free host port in the default search range."""
    for port in range(_DEFAULT_PORT, _MAX_PORT + 1):
        if _is_free_port(port):
            return port
    raise JovyKitError("No free port available in the 8888-65535 range.")


def _normalize_port(value: int | str) -> int:
    """Validate and coerce a value to a concrete port."""
    try:
        port = int(value)
    except (TypeError, ValueError):
        raise JovyKitError("Port must be one of: auto or 1-65535.") from None
    if port < 1 or port > _MAX_PORT:
        raise JovyKitError("Port must be between 1 and 65535.")
    return port


def _resolve_port(value: int | str) -> int:
    """Resolve requested port input to a concrete TCP port."""
    if isinstance(value, str) and value.strip().lower() == "auto":
        return _resolve_auto_port()
    return _normalize_port(value)


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
    allow_unsafe_requirement: bool = False,
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
        name = _validate_requirement_spec(
            spec, allow_unsafe_requirement=allow_unsafe_requirement
        )
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
    if not isinstance(data, dict):
        raise JovyKitError("Invalid compose.yaml shape: expected top-level mapping.")
    services = data.get("services")
    if not isinstance(services, dict):
        raise JovyKitError("Invalid compose.yaml shape: expected services mapping.")
    service = services.get(SERVICE_NAME)
    if not isinstance(service, dict):
        raise JovyKitError(
            "Invalid compose.yaml shape: expected services.jovy mapping."
        )
    build: dict[str, Any] = service.get("build") or {}
    args = build.get("args") or {}
    base_image = _read_build_arg(args, "JOVY_BASE_IMAGE") or resolve_image_level("base")
    level = image_level_from_reference(base_image) or "base"
    python_version = _read_build_arg(
        args, "PYTHON_VERSION"
    ) or python_version_from_image(base_image)
    gpu = _read_gpu_mode(service)
    port = _read_port(service)
    token, _ = _read_jupyter_token(service)
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


def upgrade_project(
    root: Path | None = None,
    *,
    level: str | None = None,
    python_version: str | None = None,
    gpu: str | None = None,
    port: int | str | None = None,
    token: str | None = None,
    dry_run: bool = False,
    emit: Emitter = noop_emit,
) -> None:
    """Upgrade editable project settings in compose.yaml and Dockerfile."""
    current = load_project_settings(root)
    target_level = level or current.level
    target_python_version = python_version or current.python_version
    target_gpu = gpu or current.gpu
    target_port = _resolve_port(port) if port is not None else current.port
    target_token = token if token is not None else current.token

    resolve_image_level(target_level, target_python_version)

    if dry_run:
        emit(
            f"Dry-run: image {current.level}:{current.python_version} -> "
            f"{target_level}:{target_python_version}"
        )
        emit(f"Dry-run: gpu {current.gpu} -> {target_gpu}")
        emit(f"Dry-run: port {current.port} -> {target_port}")
        emit(f"Dry-run: token {current.token} -> {target_token}")
        emit("Dry-run: no files were changed.")
        return

    save_project_settings(
        root,
        level=target_level,
        python_version=target_python_version,
        gpu=target_gpu,
        port=target_port,
        token=target_token,
        emit=emit,
    )
    emit(f"Upgraded to {resolve_image_level(target_level, target_python_version)}")


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
    if not stripped or stripped.startswith("#"):
        return None
    return stripped.split(" #", 1)[0].strip()


def _dependency_name(spec: str) -> str:
    spec = spec.split(" #", 1)[0].strip()
    if "@" in spec:
        spec = spec.split("@", 1)[0].strip()
    for separator in ("==", ">=", "<=", "!=", "~=", "=", ">", "<"):
        if separator in spec:
            spec = spec.split(separator, 1)[0]
            break
    return spec.split("[", 1)[0].strip().lower()


def _looks_like_url(spec: str) -> bool:
    parsed = urlparse(spec)
    return bool(parsed.scheme and parsed.netloc)


def _looks_like_local_path(spec: str) -> bool:
    return bool(
        spec.startswith(("/", "./", "../", "~"))
        or re.search(r"[\\/]", spec)
        or spec.startswith("-")
    )


def _is_unsafe_requirement(spec: str) -> bool:
    if spec.startswith("-"):
        return True
    if _looks_like_url(spec):
        return True
    if "@" in spec:
        _, _, reference = spec.partition("@")
        if _looks_like_url(reference.strip()) or _looks_like_local_path(
            reference.strip()
        ):
            return True
    if _looks_like_local_path(spec):
        return True
    return False


def _validate_requirement_spec(spec: str, *, allow_unsafe_requirement: bool) -> str:
    if _is_unsafe_requirement(spec):
        if not allow_unsafe_requirement:
            raise JovyKitError(
                "Unsafe requirements are disabled by default. "
                "Use --allow-unsafe-requirement or --raw."
            )
        return _dependency_name(spec)
    name = _dependency_name(spec)
    if not _REQUIREMENT_NAME_RE.fullmatch(name):
        raise JovyKitError(f"Invalid requirement name: {name!r}")
    return name


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


def _read_dockerfile_base_image(path: Path) -> str | None:
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _DOCKERFILE_BASE_IMAGE_RE.match(line)
        if match is not None:
            value = match.group(1).strip()
            return None if not value else value
    return None


def _read_compose_base_image(resolved: Path) -> str | None:
    try:
        compose_data = (
            yaml.safe_load(compose_path(resolved).read_text(encoding="utf-8")) or {}
        )
    except yaml.YAMLError as exc:
        raise JovyKitError(f"compose.yaml is invalid: {exc}")
    if not isinstance(compose_data, dict):
        raise JovyKitError("compose.yaml must be a mapping.")
    service = compose_data.get("services", {}).get(SERVICE_NAME)
    if not isinstance(service, dict):
        return None
    build = service.get("build") or {}
    if not isinstance(build, dict):
        return None
    return _read_build_arg(build.get("args"), "JOVY_BASE_IMAGE")


def _set_dockerfile_base_image(resolved: Path, base_image: str) -> None:
    level = image_level_from_reference(base_image) or "base"
    python_version = python_version_from_image(base_image) or DEFAULT_PYTHON_VERSION
    containerfile_path(resolved).write_text(
        render_containerfile(level=level, python_version=python_version),
        encoding="utf-8",
    )


def _set_compose_base_image(resolved: Path, base_image: str) -> None:
    compose_file = compose_path(resolved)
    try:
        compose_data = yaml.safe_load(compose_file.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise JovyKitError(f"compose.yaml is invalid: {exc}")
    if not isinstance(compose_data, dict):
        raise JovyKitError("compose.yaml must be a mapping.")
    services = compose_data.get("services")
    if not isinstance(services, dict):
        services = {}
    service = services.get(SERVICE_NAME)
    if not isinstance(service, dict):
        service = {}
    build = service.get("build")
    if not isinstance(build, dict):
        build = {}
    args = build.get("args")
    if isinstance(args, list):
        filtered_args = [
            item for item in args if not str(item).startswith("JOVY_BASE_IMAGE=")
        ]
        filtered_args.append(f"JOVY_BASE_IMAGE={base_image}")
        args = filtered_args
    else:
        args = {}
        if isinstance(service.get("build"), dict):
            args = (
                dict(args)
                if isinstance(service.get("build", {}).get("args"), dict)
                else {}
            )
        args["JOVY_BASE_IMAGE"] = base_image
    build["args"] = args
    service["build"] = build
    services[SERVICE_NAME] = service
    compose_data["services"] = services
    compose_file.write_text(
        yaml.safe_dump(compose_data, sort_keys=False), encoding="utf-8"
    )


def _read_gpu_mode(service: dict[str, Any]) -> str:
    if service.get("gpus") == "all":
        return "all"
    return "none"


def _read_port(service: dict[str, Any]) -> int:
    ports = service.get("ports", [])
    if ports is None:
        return 8888
    if not isinstance(ports, list):
        raise JovyKitError(
            f"Malformed compose.yaml: {ports!r} for service.{SERVICE_NAME}.ports."
        )
    for port in ports or []:
        host_port, container_port = _parse_compose_port_mapping(port)
        if container_port == 8888:
            return host_port
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


def _read_jupyter_token(service: dict[str, Any]) -> tuple[str, bool]:
    token = _read_environment_value(service, "JUPYTER_TOKEN")
    if token is not None:
        token = token.strip()
    if token:
        return token, False
    return generate_default_jupyter_token(), True


def _read_jupyter_service(
    root: Path | None,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    resolved = ensure_compose_project(root)
    data = yaml.safe_load(compose_path(resolved).read_text(encoding="utf-8")) or {}
    services = data.get("services")
    if not isinstance(services, dict):
        raise JovyKitError("compose.yaml is invalid: missing services.")
    service = services.get(SERVICE_NAME)
    if not isinstance(service, dict):
        raise JovyKitError(f"compose.yaml is invalid: missing {SERVICE_NAME} service.")
    return resolved, data, service


def _build_jupyter_url(service: dict[str, Any], token: str) -> str:
    query = urlencode({"token": token})
    port = _read_port(service)
    return f"http://127.0.0.1:{port}/lab?{query}"


def _parse_compose_port_mapping(port: object) -> tuple[int, int]:
    """Parse a compose port mapping into host/container integers."""

    mapping = str(port)
    if not mapping:
        raise JovyKitError("Malformed compose.yaml port mapping: value is empty.")
    if not isinstance(port, (str, int)):
        raise JovyKitError(f"Malformed compose.yaml port mapping: {mapping!r}.")

    if isinstance(port, int):
        value = _read_port_value(mapping, "host", port)
        return value, value

    mapping = mapping.split("/", 1)[0]
    if ":" not in mapping:
        return _read_port_value(mapping, "host", mapping), _read_port_value(
            mapping, "container", mapping
        )

    if mapping.startswith("["):
        _, _, remaining = mapping.partition("]:")
        if not remaining:
            raise JovyKitError(
                f"Malformed compose.yaml port mapping: {mapping!r} (missing host and container ports)."
            )
        parts = remaining.split(":")
    else:
        parts = mapping.split(":")

    if len(parts) == 2:
        host_port_text, container_port_text = parts
        host_port = _read_port_value(host_port_text, "host", mapping)
        container_port = _read_port_value(container_port_text, "container", mapping)
        return host_port, container_port
    if len(parts) == 3:
        host_port = _read_port_value(parts[1], "host", mapping)
        container_port = _read_port_value(parts[2], "container", mapping)
        return host_port, container_port
    raise JovyKitError(f"Malformed compose.yaml port mapping: {mapping!r}.")


def _read_port_value(text: str, name: str, mapping: str | int | float | object) -> int:
    try:
        value = int(text)
    except (TypeError, ValueError) as exc:
        raise JovyKitError(
            f"Malformed compose.yaml port mapping: {mapping!r} has invalid {name} port {text!r}."
        ) from exc
    if value < 1 or value > 65535:
        raise JovyKitError(
            f"Malformed compose.yaml port mapping: {mapping!r} has out-of-range {name} port {value}."
        )
    return value


def token_show(root: Path | None = None) -> str:
    """Return local lab URL and token with a warning if ephemeral."""
    _, data, service = _read_jupyter_service(root)
    token, generated = _read_jupyter_token(service)
    _ = data
    url = _build_jupyter_url(service, token)
    message = f"URL: {url}\nToken: {token}"
    if generated:
        message += (
            "\nWarning: JUPYTER_TOKEN is missing from compose.yaml. "
            "Run `jovy token rotate` to persist a real token."
        )
    return message


def token_rotate(root: Path | None = None, *, emit: Emitter = noop_emit) -> str:
    """Rotate the Jupyter token in compose.yaml and return the new value."""
    resolved, data, service = _read_jupyter_service(root)
    token = generate_default_jupyter_token()
    environment = service.get("environment")
    if isinstance(environment, dict):
        environment["JUPYTER_TOKEN"] = token
    elif isinstance(environment, list):
        replaced = False
        for index, item in enumerate(environment):
            text = str(item)
            if text.startswith("JUPYTER_TOKEN="):
                environment[index] = f"JUPYTER_TOKEN={token}"
                replaced = True
                break
        if not replaced:
            environment.append(f"JUPYTER_TOKEN={token}")
        service["environment"] = environment
    else:
        service["environment"] = {"JUPYTER_TOKEN": token}
    compose_path(resolved).write_text(
        yaml.safe_dump(data, sort_keys=False),
        encoding="utf-8",
    )
    emit("Rotated token in compose.yaml")
    return token


def jupyter_url(root: Path | None = None) -> str:
    """Return the local Lab URL from compose.yaml."""
    _, _, service = _read_jupyter_service(root)
    token, _ = _read_jupyter_token(service)
    return _build_jupyter_url(service, token)


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


def doctor(
    root: Path | None = None,
    *,
    fix: bool = False,
    yes: bool = False,
    emit: Emitter = noop_emit,
) -> None:
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
        return

    emit(f"project: {compose_path(resolved)}")

    if not fix:
        return

    work_dir = resolved / DEFAULT_WORK_DIR
    jupyter_dir = resolved / DEFAULT_JUPYTER_DIR
    devcontainer_file = devcontainer_path(resolved)

    if work_dir.exists():
        pass
    elif yes:
        work_dir.mkdir(parents=True, exist_ok=True)
        emit("project.work: created")
    else:
        emit("project.work: missing")

    if jupyter_dir.exists():
        pass
    elif yes:
        jupyter_dir.mkdir(parents=True, exist_ok=True)
        emit("project.jupyter: created")
    else:
        emit("project.jupyter: missing")

    if devcontainer_file.exists():
        pass
    elif yes:
        devcontainer_file.parent.mkdir(parents=True, exist_ok=True)
        devcontainer_file.write_text(
            render_devcontainer(resolved.name), encoding="utf-8"
        )
        emit("project.devcontainer: created")
    else:
        emit("project.devcontainer: missing")

    try:
        compose_base = _read_compose_base_image(resolved)
    except JovyKitError as exc:
        emit(f"project.base_image: {exc}")
        return
    dockerfile_base = _read_dockerfile_base_image(containerfile_path(resolved))

    if compose_base is None:
        if dockerfile_base is not None:
            if yes:
                _set_compose_base_image(resolved, dockerfile_base)
                emit("project.base_image: compose base image restored from Dockerfile")
                compose_base = dockerfile_base
            else:
                emit("project.base_image: compose value missing")
        else:
            emit("project.base_image: compose value missing")
            return
    if compose_base is None:
        return

    if dockerfile_base is None:
        if yes:
            _set_dockerfile_base_image(resolved, compose_base)
            emit("project.base_image: dockerfile base image restored from compose.yaml")
        else:
            emit("project.base_image: dockerfile value missing")
        return

    if compose_base == dockerfile_base:
        return

    if yes:
        _set_dockerfile_base_image(resolved, compose_base)
        emit("project.base_image: dockerfile aligned to compose")
    else:
        emit(
            "project.base_image: mismatch between compose.yaml and Dockerfile"
            f" (compose={compose_base}, dockerfile={dockerfile_base})"
        )


def status(root: Path | None = None, *, json_output: bool = False) -> str:
    """Return Compose status as machine-readable JSON or verbose text."""
    payload = _load_status_payload(root)
    if json_output:
        return json.dumps(payload, sort_keys=True)
    return _format_status_payload(payload)


def _load_status_payload(root: Path | None = None) -> dict[str, str | int | None]:
    """Collect a stable status payload for CLI output and automation."""
    payload: dict[str, str | int | None] = {
        "container_state": "error",
        "url": None,
        "image": None,
        "python_version": None,
        "level": None,
        "gpu": None,
        "port": None,
        "token": "***",
        "token_source": None,
        "compose_file": None,
        "error": None,
    }
    resolved = ensure_compose_project(root)
    compose_file = str(compose_path(resolved))
    payload["compose_file"] = compose_file

    compose_data = (
        yaml.safe_load(compose_path(resolved).read_text(encoding="utf-8")) or {}
    )
    service: dict[str, Any] = compose_data.get("services", {}).get(SERVICE_NAME, {})
    token = _read_environment_value(service, "JUPYTER_TOKEN")
    payload["token_source"] = "compose" if token is not None else "generated"

    settings = load_project_settings(resolved)
    payload["python_version"] = settings.python_version
    payload["level"] = settings.level
    payload["gpu"] = settings.gpu
    payload["port"] = settings.port

    payload["url"] = _redact_jupyter_token(jupyter_url(resolved))
    build_args = service.get("build", {}).get("args") or {}
    payload["image"] = _read_build_arg(build_args, "JOVY_BASE_IMAGE") or "unknown"

    state, image, error = _compose_service_state(resolved)
    payload["container_state"] = state
    if image is not None:
        payload["image"] = image
    if error is not None:
        payload["error"] = error
    return payload


def _compose_service_state(
    resolved: Path,
) -> tuple[str, str | None, str | None]:
    """Return container state, image, and optional error from compose ps."""
    try:
        raw = runtime.compose_ps(resolved)
    except JovyKitError as exc:
        return "error", None, str(exc)
    raw = raw.strip()
    if not raw:
        return "stopped", None, None
    try:
        raw_items = json.loads(raw)
    except json.JSONDecodeError:
        try:
            raw_items = [json.loads(line) for line in raw.splitlines() if line.strip()]
        except json.JSONDecodeError:
            return "error", None, "compose ps output is not valid JSON"
    if isinstance(raw_items, dict):
        items = [raw_items]
    elif isinstance(raw_items, list):
        if not all(isinstance(item, dict) for item in raw_items):
            return "error", None, "compose ps output has unexpected format"
        items = raw_items
    else:
        return "error", None, "compose ps output has unexpected format"

    if not items:
        return "stopped", None, None

    item = _find_jovy_service(items)
    state = str(item.get("State") or item.get("Status") or "stopped").strip().lower()
    image = item.get("Image")
    return state, None if image is None else str(image), None


def _find_jovy_service(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Select the Jovy service record from compose ps output."""
    if not items:
        return {}
    for item in items:
        name = str(item.get("Name", "")).lower()
        service = str(item.get("Service", "")).lower()
        if SERVICE_NAME in name or SERVICE_NAME in service:
            return item
    return items[0]


def _format_status_payload(payload: dict[str, str | int | None]) -> str:
    """Render a verbose status block for human use."""
    fields = (
        "compose_file",
        "container_state",
        "url",
        "image",
        "python_version",
        "level",
        "gpu",
        "port",
        "token_source",
        "token",
    )
    return "\n".join(f"{field}: {payload.get(field)}" for field in fields)


def _redact_jupyter_token(url: str) -> str:
    """Hide sensitive token query values in URLs."""
    parsed = urlparse(url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    if not query:
        return url
    cleaned = [(name, "***" if name == "token" else value) for name, value in query]
    redacted = parsed._replace(query=urlencode(cleaned))
    return urlunparse(redacted)


def detect_gpu_mode() -> str:
    """Return all when the host appears to expose a GPU."""
    if shutil.which("nvidia-smi") is not None:
        return "all"
    if any(Path("/dev").glob("nvidia*")):
        return "all"
    if any(Path("/dev/dri").glob("renderD*")):
        return "all"
    return "none"
