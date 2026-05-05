from pathlib import Path
from typing import Any

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st

from jovykit.config import (
    ConfigError,
    initial_config_text,
    load_config,
    read_state,
    slugify_name,
    write_state,
)
from jovykit.generate import write_generated_files
from jovykit.images import resolve_image


def test_resolve_image_accepts_levels_and_refs() -> None:
    assert resolve_image("base") == "ghcr.io/mihneateodorstoica/jovykit-base:latest"
    assert resolve_image("example.com/custom:tag") == "example.com/custom:tag"


def test_slugify_name_returns_docker_friendly_name() -> None:
    assert slugify_name("My Project!") == "my-project"
    assert slugify_name("...") == "project"


@given(st.text())
def test_slugify_name_always_returns_docker_friendly_slug(value: str) -> None:
    slug = slugify_name(value)

    assert slug
    assert slug == slug.lower()
    assert all(char.isalnum() or char in "_.-" for char in slug)
    assert not slug.startswith(("-", "_", "."))
    assert not slug.endswith(("-", "_", "."))


def test_generated_environment_files(tmp_path: Path) -> None:
    env_dir = tmp_path / ".jovy"
    env_dir.mkdir()
    (tmp_path / "jovy.toml").write_text(
        initial_config_text(
            project_name="My Project",
            env_name=".jovy",
            image="minimal",
            gpus="none",
            port=9999,
        ),
        encoding="utf-8",
    )

    config = load_config(env_dir)
    write_generated_files(config)

    assert config.base_image == "ghcr.io/mihneateodorstoica/jovykit-minimal:latest"
    assert (
        "FROM ghcr.io/mihneateodorstoica/jovykit-minimal:latest"
        in (env_dir / "Containerfile").read_text()
    )
    compose = (env_dir / "compose.yaml").read_text()
    data = yaml.safe_load(compose)
    service = data["services"]["jovy"]
    assert service["ports"] == ["127.0.0.1:9999:8888"]
    assert service["volumes"][0] == f"../work:{config.work_mount}"
    assert service["environment"] == {
        "JUPYTER_ENABLE_LAB": "yes",
        "JUPYTER_LOG_LEVEL": "ERROR",
    }
    assert service["develop"]["watch"] == [
        {"action": "rebuild", "path": "requirements.txt"},
        {"action": "rebuild", "path": "Containerfile"},
        {
            "action": "sync+restart",
            "path": "../jovy.toml",
            "target": "/tmp/jovykit-watch/jovy.toml",
            "initial_sync": True,
        },
    ]
    assert "deploy" not in service


def test_jupyter_token_and_workdir_affect_generated_compose(tmp_path: Path) -> None:
    env_dir = tmp_path / ".jovy"
    notebooks_dir = tmp_path / "notebooks"
    env_dir.mkdir()
    notebooks_dir.mkdir()
    config_text = initial_config_text(
        project_name="My Project",
        env_name=".jovy",
        image="minimal",
        gpus="none",
        port=9999,
        workdir="notebooks",
    ).replace('token = "auto"', 'token = "secret-token"')
    (tmp_path / "jovy.toml").write_text(config_text, encoding="utf-8")

    config = load_config(env_dir)
    write_generated_files(config)

    service = yaml.safe_load((env_dir / "compose.yaml").read_text())["services"]["jovy"]
    assert config.project_root == notebooks_dir
    assert service["environment"]["JUPYTER_TOKEN"] == "secret-token"
    assert service["volumes"][0] == f"../notebooks:{config.work_mount}"
    assert all(
        watch_rule.get("path") != "../notebooks"
        for watch_rule in service["develop"]["watch"]
    )


def test_legacy_environment_config_is_migrated(tmp_path: Path) -> None:
    env_dir = tmp_path / ".jovy"
    env_dir.mkdir()
    legacy_config = env_dir / "jovy.toml"
    legacy_config.write_text(
        initial_config_text(
            project_name="My Project",
            env_name=".jovy",
            image="minimal",
            gpus="none",
            port=9999,
        ),
        encoding="utf-8",
    )

    config = load_config(env_dir)

    assert config.config_path == tmp_path / "jovy.toml"
    assert config.config_path.exists()
    assert not legacy_config.exists()


def test_customization_tables_render_into_generated_files(tmp_path: Path) -> None:
    env_dir = tmp_path / ".jovy"
    env_dir.mkdir()
    config_text = initial_config_text(
        project_name="My Project",
        env_name=".jovy",
        image="minimal",
        gpus="none",
        port=9999,
    )
    config_text = config_text.replace(
        "[runtime.env]\n\n[runtime.volumes]",
        '[runtime.env]\nEXTRA_FLAG = "yes"\n\n[runtime.volumes]\n"./data" = "/data"',
    )
    config_text = config_text.replace(
        'restart = "unless-stopped"',
        'restart = "always"\nuser = "1000:1000"',
    )
    config_text = config_text.replace(
        'log_level = "ERROR"',
        'log_level = "INFO"\ncommand = "start-notebook.py --ServerApp.root_dir=/home/jovyan/work"',
    )
    config_text = config_text.replace(
        'workspace_mode = "bind"',
        'workspace_mode = "sync"',
    )
    config_text = config_text.replace(
        'restart = ["jovy.toml"]',
        'restart = ["jovy.toml", "runtime.toml"]',
    )
    config_text = config_text.replace(
        "pull = false\n\n[image.build_args]",
        'pull = true\ntarget = "base"\nplatform = "linux/amd64"\n\n[image.build_args]\nEXAMPLE = "1"',
    )
    config_text = config_text.replace(
        "packages = []",
        'packages = ["curl"]',
    )
    config_text = config_text.replace(
        "pip_args = []",
        'pip_args = ["--upgrade"]',
    )
    (tmp_path / "jovy.toml").write_text(config_text, encoding="utf-8")

    config = load_config(env_dir)
    write_generated_files(config)

    service = yaml.safe_load((env_dir / "compose.yaml").read_text())["services"]["jovy"]
    assert service["build"]["target"] == "base"
    assert service["build"]["platform"] == "linux/amd64"
    assert service["build"]["args"] == {"EXAMPLE": "1"}
    assert service["environment"]["EXTRA_FLAG"] == "yes"
    assert service["restart"] == "always"
    assert service["user"] == "1000:1000"
    assert service["command"].startswith("start-notebook.py")
    assert f"../work:{config.work_mount}" not in service["volumes"]
    assert "./data:/data" in service["volumes"]
    assert service["develop"]["watch"][0]["action"] == "sync"
    assert service["develop"]["watch"][-1]["action"] == "sync+restart"
    assert service["develop"]["watch"][-1]["path"] == "../runtime.toml"

    containerfile = (env_dir / "Containerfile").read_text(encoding="utf-8")
    assert "apt-get install -y --no-install-recommends curl" in containerfile
    assert "uv pip install --upgrade --system" in containerfile


def test_load_config_reports_missing_config(tmp_path: Path) -> None:
    env_dir = tmp_path / ".jovy"
    env_dir.mkdir()

    with pytest.raises(ConfigError, match="No JovyKit configuration found"):
        load_config(env_dir)


def test_load_config_reports_malformed_toml(tmp_path: Path) -> None:
    env_dir = tmp_path / ".jovy"
    env_dir.mkdir()
    (tmp_path / "jovy.toml").write_text("[project\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="Could not parse"):
        load_config(env_dir)


def test_load_config_reports_missing_required_image_setting(tmp_path: Path) -> None:
    env_dir = tmp_path / ".jovy"
    env_dir.mkdir()
    (tmp_path / "jovy.toml").write_text(
        """
[project]
name = "Example"

[image]
name = "example"
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="Missing required setting"):
        load_config(env_dir)


def test_load_config_reports_invalid_runtime_values(tmp_path: Path) -> None:
    env_dir = tmp_path / ".jovy"
    env_dir.mkdir()
    config_text = initial_config_text(
        project_name="Example",
        env_name=".jovy",
        image="minimal",
        gpus="none",
        port=8888,
    ).replace("port = 8888", 'port = "not-a-port"')
    (tmp_path / "jovy.toml").write_text(config_text, encoding="utf-8")

    with pytest.raises(ConfigError, match="Invalid setting"):
        load_config(env_dir)


def test_load_config_coerces_env_volumes_and_lists(tmp_path: Path) -> None:
    env_dir = tmp_path / ".jovy"
    env_dir.mkdir()
    config_text = initial_config_text(
        project_name="Example",
        env_name=".jovy",
        image="minimal",
        gpus="none",
        port=8888,
    )
    config_text = config_text.replace(
        "[runtime.env]\n\n[runtime.volumes]",
        '[runtime.env]\nNUMBER = 1\nFLAG = true\n\n[runtime.volumes]\n"./data" = 123',
    )
    config_text = config_text.replace(
        'ignore = [".jovy/", ".git/", ".venv/", "__pycache__/", ".mypy_cache/", ".pytest_cache/", ".ruff_cache/"]',
        "ignore = [123, 456]",
    )
    (tmp_path / "jovy.toml").write_text(config_text, encoding="utf-8")

    config = load_config(env_dir)

    assert config.runtime_env == {"NUMBER": "1", "FLAG": "True"}
    assert config.runtime_volumes == {"./data": "123"}
    assert config.watch_ignore == ["123", "456"]


def test_config_path_helpers_return_compose_relative_paths(create_project: Any) -> None:
    project = create_project(workdir="notebooks")

    assert project.config.compose_workdir == "../notebooks"
    assert project.config.compose_project_path("jovy.toml") == "../jovy.toml"
    assert project.config.compose_project_path(str(project.root / "data")) == "../data"


def test_state_round_trips_sorted_json(tmp_path: Path) -> None:
    env_dir = tmp_path / ".jovy"
    env_dir.mkdir()

    assert read_state(env_dir) == {}

    write_state(env_dir, {"z": 1, "a": {"nested": True}})

    assert read_state(env_dir) == {"a": {"nested": True}, "z": 1}
    assert (env_dir / "state.json").read_text(encoding="utf-8").startswith('{\n  "a"')
