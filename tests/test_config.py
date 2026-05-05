from pathlib import Path

import yaml

from jovykit.config import initial_config_text, load_config, slugify_name
from jovykit.generate import write_generated_files
from jovykit.images import resolve_image


def test_resolve_image_accepts_levels_and_refs() -> None:
    assert resolve_image("base") == "ghcr.io/mihneateodorstoica/jovykit-base:latest"
    assert resolve_image("example.com/custom:tag") == "example.com/custom:tag"


def test_slugify_name_returns_docker_friendly_name() -> None:
    assert slugify_name("My Project!") == "my-project"
    assert slugify_name("...") == "project"


def test_generated_environment_files(tmp_path: Path) -> None:
    env_dir = tmp_path / ".jovy"
    env_dir.mkdir()
    (env_dir / "jovy.toml").write_text(
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
        workdir="../notebooks",
    ).replace('token = "auto"', 'token = "secret-token"')
    (env_dir / "jovy.toml").write_text(config_text, encoding="utf-8")

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
