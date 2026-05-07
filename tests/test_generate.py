from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from jovykit.config import JovyKitError
from jovykit.generate import ensure_empty_or_jovy_env, write_generated_files


def test_write_generated_files_creates_expected_readable_files(
    create_project: Any,
) -> None:
    project = create_project(generate=False)
    home_path = project.config.home_path
    if (home_path / ".bashrc").exists():
        (home_path / ".bashrc").unlink()

    write_generated_files(project.config)

    assert (project.env_dir / "Containerfile").exists()
    assert (project.env_dir / "compose.yaml").exists()
    assert not (project.env_dir / "requirements.txt").exists()
    assert (project.env_dir / ".gitignore").read_text(encoding="utf-8") == (
        "state.json\nwatcher.pid\nwatcher.log\n.generated/\nhome/\n"
    )
    assert (project.config.home_path / ".ssh").is_dir()
    bashrc_text = (home_path / ".bashrc").read_text(encoding="utf-8")
    assert "JovyKit shell bootstrap." in bashrc_text
    assert "/etc/skel/.bashrc" in bashrc_text


def test_ensure_empty_or_jovy_env_allows_missing_directory(tmp_path: Path) -> None:
    ensure_empty_or_jovy_env(tmp_path / ".jovy")


def test_ensure_empty_or_jovy_env_rejects_existing_jovy_environment(
    create_project: Any,
) -> None:
    project = create_project()

    with pytest.raises(JovyKitError, match="already exists"):
        ensure_empty_or_jovy_env(project.env_dir)


def test_ensure_empty_or_jovy_env_rejects_non_empty_directory(tmp_path: Path) -> None:
    env_dir = tmp_path / ".jovy"
    env_dir.mkdir()
    (env_dir / "file.txt").write_text("data", encoding="utf-8")

    with pytest.raises(JovyKitError, match="non-empty directory"):
        ensure_empty_or_jovy_env(env_dir)
