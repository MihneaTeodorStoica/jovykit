"""Generate JovyKit environment files."""

from __future__ import annotations

from pathlib import Path

from jovykit.config import JovyConfig, JovyKitError
from jovykit.templates import render_compose, render_containerfile


def write_generated_files(config: JovyConfig) -> None:
    """Write generated files that are intentionally readable."""
    config.env_dir.mkdir(parents=True, exist_ok=True)
    (config.env_dir / "Containerfile").write_text(
        render_containerfile(config),
        encoding="utf-8",
    )
    (config.env_dir / "compose.yaml").write_text(
        render_compose(config),
        encoding="utf-8",
    )
    (config.env_dir / ".gitignore").write_text(
        "state.json\nwatcher.pid\nwatcher.log\n.generated/\n",
        encoding="utf-8",
    )


def ensure_empty_or_jovy_env(env_dir: Path) -> None:
    """Validate that init will not trample a non-JovyKit directory."""
    if not env_dir.exists():
        return
    if (env_dir / "jovy.toml").exists() or (env_dir.parent / "jovy.toml").exists():
        raise JovyKitError(
            f"JovyKit environment already exists at {env_dir}. "
            "Use --force to refresh its generated files."
        )
    if any(env_dir.iterdir()):
        raise JovyKitError(f"Refusing to initialize non-empty directory: {env_dir}")
