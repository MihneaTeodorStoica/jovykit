from __future__ import annotations

from pathlib import Path

import pytest

from jovykit.config import JovyKitError
from jovykit.paths import compose_path, ensure_compose_project


def test_ensure_compose_project_returns_root(tmp_path: Path) -> None:
    (tmp_path / "compose.yaml").write_text("services: {}\n", encoding="utf-8")

    assert ensure_compose_project(tmp_path) == tmp_path


def test_ensure_compose_project_rejects_legacy_config(tmp_path: Path) -> None:
    (tmp_path / "jovy.toml").write_text("[project]\n", encoding="utf-8")
    (tmp_path / "compose.yaml").write_text("services: {}\n", encoding="utf-8")

    with pytest.raises(JovyKitError, match="jovy.toml is no longer used"):
        ensure_compose_project(tmp_path)


def test_compose_path_is_root_file(tmp_path: Path) -> None:
    assert compose_path(tmp_path) == tmp_path / "compose.yaml"
