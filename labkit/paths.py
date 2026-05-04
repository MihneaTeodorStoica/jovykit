"""Path discovery for LabKit environments."""

from __future__ import annotations

from pathlib import Path

DEFAULT_ENV_DIR = ".lab"
CONFIG_FILE = "lab.toml"


def find_environment(start: Path | None = None) -> Path:
    """Find the nearest LabKit environment directory from start upward."""
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        candidate = directory / DEFAULT_ENV_DIR / CONFIG_FILE
        if candidate.exists():
            return candidate.parent
    raise FileNotFoundError(
        "No LabKit environment found. Run 'lab init .lab' from your project root."
    )
