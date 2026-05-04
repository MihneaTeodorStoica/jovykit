"""Generate LabKit environment files."""

from __future__ import annotations

from pathlib import Path

from labkit.config import LabConfig
from labkit.templates import render_compose, render_containerfile


def write_generated_files(config: LabConfig) -> None:
    """Write generated files that are intentionally readable."""
    config.env_dir.mkdir(parents=True, exist_ok=True)
    requirements_path = config.env_dir / "requirements.txt"
    if not requirements_path.exists():
        requirements_path.write_text(
            "# Project packages managed by LabKit.\n",
            encoding="utf-8",
        )
    (config.env_dir / "Containerfile").write_text(
        render_containerfile(config),
        encoding="utf-8",
    )
    (config.env_dir / "compose.yaml").write_text(
        render_compose(config),
        encoding="utf-8",
    )
    (config.env_dir / ".gitignore").write_text(
        "state.json\nrequirements.lock\n",
        encoding="utf-8",
    )


def ensure_empty_or_lab_env(env_dir: Path) -> None:
    """Validate that init will not trample a non-LabKit directory."""
    if not env_dir.exists():
        return
    if (env_dir / "lab.toml").exists():
        raise FileExistsError(f"LabKit environment already exists at {env_dir}")
    if any(env_dir.iterdir()):
        raise FileExistsError(f"Refusing to initialize non-empty directory: {env_dir}")
