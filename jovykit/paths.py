"""Path discovery for JovyKit environments."""

from __future__ import annotations

from pathlib import Path

from jovykit.config import JovyKitError

DEFAULT_ENV_DIR = ".jovy"
CONFIG_FILE = "jovy.toml"


def find_environment(start: Path | None = None) -> Path:
    """Find the nearest JovyKit environment directory from start upward."""
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        candidate = directory / DEFAULT_ENV_DIR / CONFIG_FILE
        if candidate.exists():
            return candidate.parent
    raise JovyKitError(
        "No JovyKit environment found. Run 'jovy init .jovy' from your project root, "
        "or pass --env PATH."
    )
