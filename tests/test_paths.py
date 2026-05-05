from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from jovykit.config import JovyKitError
from jovykit.paths import (
    DEFAULT_ENV_DIR,
    environment_from_path,
    find_environment,
    has_stale_legacy_config,
    legacy_config_path,
    root_config_path,
)


def test_environment_from_path_accepts_project_root_and_env_dir(tmp_path: Path) -> None:
    assert environment_from_path(tmp_path) == tmp_path / DEFAULT_ENV_DIR
    assert (
        environment_from_path(tmp_path / DEFAULT_ENV_DIR) == tmp_path / DEFAULT_ENV_DIR
    )


path_name = st.text(
    alphabet=st.sampled_from(
        list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    ),
    min_size=1,
    max_size=40,
)


@given(path_name)
def test_environment_from_path_preserves_explicit_env_name(name: str) -> None:
    candidate = Path("/tmp/jovykit-hypothesis") / name

    resolved = environment_from_path(candidate)

    if candidate.resolve().name == DEFAULT_ENV_DIR:
        assert resolved == candidate.resolve()
    else:
        assert resolved == candidate.resolve() / DEFAULT_ENV_DIR


def test_config_path_helpers(create_project: Any) -> None:
    project = create_project()

    assert legacy_config_path(project.env_dir) == project.env_dir / "jovy.toml"
    assert root_config_path(project.env_dir) == project.root / "jovy.toml"


def test_find_environment_prefers_root_config_from_nested_directory(
    tmp_path: Path, create_project: Any
) -> None:
    project = create_project()
    nested = tmp_path / "work" / "nested"
    nested.mkdir(parents=True)

    assert find_environment(nested) == project.env_dir


def test_find_environment_falls_back_to_legacy_config(tmp_path: Path) -> None:
    env_dir = tmp_path / ".jovy"
    env_dir.mkdir()
    (env_dir / "jovy.toml").write_text("[project]\n", encoding="utf-8")

    assert find_environment(tmp_path) == env_dir


def test_find_environment_reports_missing_environment(tmp_path: Path) -> None:
    with pytest.raises(JovyKitError, match="No JovyKit environment found"):
        find_environment(tmp_path)


def test_has_stale_legacy_config_detects_root_and_legacy_configs(
    create_project: Any,
) -> None:
    project = create_project()
    (project.env_dir / "jovy.toml").write_text("[legacy]\n", encoding="utf-8")

    assert has_stale_legacy_config(project.env_dir) is True
