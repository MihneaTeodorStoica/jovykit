from __future__ import annotations

import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest

from jovykit.cli import main


@dataclass(frozen=True)
class CliResult:
    exit_code: int
    output: str


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
