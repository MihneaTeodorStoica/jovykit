"""Project path helpers."""

from __future__ import annotations

from pathlib import Path

from jovykit.config import JovyKitError

COMPOSE_FILE = "compose.yaml"
CONTAINERFILE = "Dockerfile"
REQUIREMENTS_FILE = "requirements.txt"
LEGACY_CONFIG_FILE = "jovy.toml"
SERVICE_NAME = "jovy"
DEFAULT_WORK_DIR = "work"
DEFAULT_JUPYTER_DIR = ".jupyter"
DEFAULT_ENV_DIR = ".jovy"
PROJECT_MARKERS = (COMPOSE_FILE, CONTAINERFILE, REQUIREMENTS_FILE)


def project_root(path: Path | None = None) -> Path:
    """Return the project root used for Compose commands."""
    return (path or Path.cwd()).resolve()


def compose_path(root: Path | None = None) -> Path:
    """Return the project Compose file path."""
    return project_root(root) / COMPOSE_FILE


def containerfile_path(root: Path | None = None) -> Path:
    """Return the project Dockerfile path."""
    return project_root(root) / CONTAINERFILE


def requirements_path(root: Path | None = None) -> Path:
    """Return the project requirements path."""
    return project_root(root) / REQUIREMENTS_FILE


def legacy_config_path(root: Path | None = None) -> Path:
    """Return the removed jovy.toml path."""
    return project_root(root) / LEGACY_CONFIG_FILE


def ensure_compose_project(root: Path | None = None) -> Path:
    """Return root or raise when no Compose file exists."""
    resolved = project_root(root)
    if legacy_config_path(resolved).exists():
        raise JovyKitError(
            "jovy.toml is no longer used. Move settings into compose.yaml, then remove jovy.toml."
        )
    if not compose_path(resolved).exists():
        raise JovyKitError("compose.yaml not found. Run: jovy init")
    return resolved


def has_project_markers(root: Path | None = None) -> bool:
    """Return true when any generated project file already exists."""
    resolved = project_root(root)
    return any((resolved / marker).exists() for marker in PROJECT_MARKERS)
