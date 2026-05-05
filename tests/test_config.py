from pathlib import Path

from labkit.config import initial_config_text, load_config, slugify_name
from labkit.generate import write_generated_files
from labkit.images import resolve_image


def test_resolve_image_accepts_levels_and_refs() -> None:
    assert resolve_image("base") == "ghcr.io/mihneateodorstoica/labkit-base:latest"
    assert resolve_image("example.com/custom:tag") == "example.com/custom:tag"


def test_slugify_name_returns_docker_friendly_name() -> None:
    assert slugify_name("My Project!") == "my-project"
    assert slugify_name("...") == "project"


def test_generated_environment_files(tmp_path: Path) -> None:
    env_dir = tmp_path / ".lab"
    env_dir.mkdir()
    (env_dir / "lab.toml").write_text(
        initial_config_text(
            project_name="My Project",
            env_name=".lab",
            image="minimal",
            gpus="none",
            port=9999,
        ),
        encoding="utf-8",
    )

    config = load_config(env_dir)
    write_generated_files(config)

    assert config.base_image == "ghcr.io/mihneateodorstoica/labkit-minimal:latest"
    assert (
        "FROM ghcr.io/mihneateodorstoica/labkit-minimal:latest"
        in (env_dir / "Containerfile").read_text()
    )
    compose = (env_dir / "compose.yaml").read_text()
    assert '"127.0.0.1:9999:8888"' in compose
    assert "driver: nvidia" not in compose
