"""Path discovery for JovyKit environments."""

from __future__ import annotations

from pathlib import Path

from jovykit.config import JovyKitError

DEFAULT_ENV_DIR = ".jovy"
CONFIG_FILE = "jovy.toml"


def environment_from_path(path: Path) -> Path:
    """Normalize a project root or environment directory to the env directory."""
    resolved = path.resolve()
    if resolved.name == DEFAULT_ENV_DIR:
        return resolved
    return resolved / DEFAULT_ENV_DIR


def legacy_config_path(env_dir: Path) -> Path:
    """Return the pre-1.0 config path for an environment directory."""
    return env_dir / CONFIG_FILE


def root_config_path(env_dir: Path) -> Path:
    """Return the root config path for an environment directory."""
    return env_dir.parent / CONFIG_FILE


def has_stale_legacy_config(env_dir: Path) -> bool:
    """Return whether both root and legacy config files exist."""
    return root_config_path(env_dir).exists() and legacy_config_path(env_dir).exists()


def find_environment(start: Path | None = None) -> Path:
    """Find the nearest JovyKit environment directory from start upward."""
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        candidate = directory / CONFIG_FILE
        if candidate.exists():
            return directory / DEFAULT_ENV_DIR
    for directory in (current, *current.parents):
        candidate = directory / DEFAULT_ENV_DIR / CONFIG_FILE
        if candidate.exists():
            return directory / DEFAULT_ENV_DIR
    raise JovyKitError(
        "No JovyKit environment found. Run 'jovy init .jovy' from your project root, "
        "or pass --env PATH."
    )
