from __future__ import annotations

from pathlib import Path

import pytest

from jovykit.config import JovyKitError, initial_config_text
from jovykit.deps import add_packages, import_requirements, remove_packages


def write_config(path: Path) -> Path:
    config_path = path / "jovy.toml"
    config_path.write_text(
        initial_config_text(
            project_name="Example",
            env_name=".jovy",
            image="minimal",
            gpus="none",
            port=8888,
        ),
        encoding="utf-8",
    )
    return config_path


def test_add_packages_updates_toml_and_deduplicates(tmp_path: Path) -> None:
    config_path = write_config(tmp_path)

    update = add_packages(config_path, ["numpy", " pandas ", "numpy"])

    assert update.added == ["numpy", "pandas"]
    assert 'packages = ["numpy", "pandas"]' in config_path.read_text(encoding="utf-8")


def test_remove_packages_updates_toml_exactly(tmp_path: Path) -> None:
    config_path = write_config(tmp_path)
    add_packages(config_path, ["numpy", "pandas", "requests"])

    update = remove_packages(config_path, ["pandas", "missing"])

    assert update.removed == ["pandas"]
    assert 'packages = ["numpy", "requests"]' in config_path.read_text(encoding="utf-8")


def test_import_requirements_recurses_and_preserves_constraints(tmp_path: Path) -> None:
    nested = tmp_path / "nested.txt"
    constraints = tmp_path / "constraints.txt"
    root = tmp_path / "requirements.txt"
    package_dir = tmp_path / "localpkg"
    package_dir.mkdir()
    nested.write_text(
        "\n".join(
            [
                "pandas",
                "./localpkg",
                "-e ./localpkg",
                "# ignored",
            ]
        ),
        encoding="utf-8",
    )
    constraints.write_text("numpy==1.26.0\n", encoding="utf-8")
    root.write_text(
        "\n".join(
            [
                "numpy",
                "-r nested.txt",
                "--requirement nested.txt",
                "-c constraints.txt",
                "git+https://example.test/repo.git#egg=demo",
                "numpy  # duplicate",
            ]
        ),
        encoding="utf-8",
    )

    imported = import_requirements([root], project_dir=tmp_path)

    assert imported.packages == [
        "numpy",
        "pandas",
        "localpkg",
        "-e localpkg",
        "git+https://example.test/repo.git#egg=demo",
    ]
    assert imported.constraints == ["constraints.txt"]


def test_import_requirements_detects_cycles(tmp_path: Path) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("-r second.txt\nnumpy\n", encoding="utf-8")
    second.write_text("-r first.txt\npandas\n", encoding="utf-8")

    imported = import_requirements([first], project_dir=tmp_path)

    assert imported.packages == ["pandas", "numpy"]


def test_import_requirements_rejects_unsupported_options(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "--index-url https://example.test/simple\n", encoding="utf-8"
    )

    with pytest.raises(JovyKitError, match="Unsupported requirement option"):
        import_requirements([requirements], project_dir=tmp_path)
