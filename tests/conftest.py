from __future__ import annotations

import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from jovykit.cli import main
from jovykit.config import JovyConfig, initial_config_text, load_config
from jovykit.generate import write_generated_files


@dataclass(frozen=True)
class CliResult:
    exit_code: int
    output: str


@dataclass(frozen=True)
class JovyProject:
    root: Path
    env_dir: Path
    config: JovyConfig


@pytest.fixture
def run_cli(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> Callable[[list[str], int], CliResult]:
    def _run_cli(args: list[str], expected_code: int = 0) -> CliResult:
        monkeypatch.setattr(sys, "argv", ["jovy", *args])
        exit_code = 0
        try:
            main()
        except SystemExit as exc:
            exit_code = int(exc.code or 0)
        output = capsys.readouterr().out
        assert exit_code == expected_code, output
        return CliResult(exit_code=exit_code, output=output)

    return _run_cli


@pytest.fixture
def create_project(tmp_path: Path) -> Callable[..., JovyProject]:
    def _create_project(
        *,
        project_name: str = "My Project",
        env_name: str = ".jovy",
        image: str = "minimal",
        gpus: str = "none",
        port: int = 9999,
        token: str = "",
        password: str = "jovykit",
        log_level: str = "ERROR",
        image_name: str | None = None,
        image_tag: str = "local",
        workdir: str = "work",
        config_transform: Callable[[str], str] | None = None,
        generate: bool = True,
    ) -> JovyProject:
        env_dir = tmp_path / env_name
        env_dir.mkdir(parents=True, exist_ok=True)
        config_text = initial_config_text(
            project_name=project_name,
            env_name=env_name,
            image=image,
            gpus=gpus,
            port=port,
            token=token,
            password=password,
            log_level=log_level,
            image_name=image_name,
            image_tag=image_tag,
            workdir=workdir,
        )
        if config_transform is not None:
            config_text = config_transform(config_text)
        (tmp_path / "jovy.toml").write_text(config_text, encoding="utf-8")
        config = load_config(env_dir)
        if generate:
            config.project_root.mkdir(parents=True, exist_ok=True)
            write_generated_files(config)
        return JovyProject(root=tmp_path, env_dir=env_dir, config=config)

    return _create_project


@pytest.fixture
def capture_calls() -> list[tuple[tuple[Any, ...], dict[str, Any]]]:
    return []


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-docker",
        action="store_true",
        default=False,
        help="run tests marked docker that require a local Docker daemon",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "unit: fast isolated unit tests")
    config.addinivalue_line("markers", "integration: multi-module integration tests")
    config.addinivalue_line("markers", "docker: optional tests requiring Docker")
    config.addinivalue_line("markers", "slow: slower tests skipped in tight loops")


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if config.getoption("--run-docker") or os.environ.get("JOVYKIT_RUN_DOCKER"):
        return
    skip_docker = pytest.mark.skip(
        reason="requires --run-docker or JOVYKIT_RUN_DOCKER=1"
    )
    for item in items:
        if "docker" in item.keywords:
            item.add_marker(skip_docker)
