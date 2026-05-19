from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from jovykit import commands


def test_no_args_initializes_empty_project(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, run_cli
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(commands, "detect_gpu_mode", lambda: "none")

    result = run_cli([])

    assert (tmp_path / "compose.yaml").exists()
    assert (tmp_path / "Dockerfile").exists()
    assert (tmp_path / "requirements.txt").exists()
    assert "Created compose.yaml" in result.output
    assert "Created Dockerfile" in result.output
    assert "Created requirements.txt" in result.output
    assert "Created work/" in result.output
    assert "Created .jupyter/" in result.output
    assert "gpus:" not in (tmp_path / "compose.yaml").read_text()


def test_no_args_prints_help_when_project_exists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, run_cli
) -> None:
    (tmp_path / "compose.yaml").write_text("services: {}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = run_cli([])

    assert "JovyKit" in result.output
    assert "jovy up" in result.output


def test_compose_command_passes_to_compose(
    monkeypatch: pytest.MonkeyPatch, run_cli
) -> None:
    calls: list[list[str]] = []

    def fake_compose(args: list[str], **kwargs: object) -> int:
        calls.append(list(args))
        return 7

    monkeypatch.setattr(
        commands,
        "compose_passthrough",
        fake_compose,
    )

    result = run_cli(["compose", "logs", "-f"], expected_code=7)

    assert calls == [["logs", "-f"]]
    assert result.output == ""


def test_compose_like_commands_pass_args(
    monkeypatch: pytest.MonkeyPatch, run_cli
) -> None:
    calls: list[tuple[str, list[str]]] = []

    def fake_up(args: list[str]) -> int:
        calls.append(("up", list(args)))
        return 0

    def fake_config(args: list[str]) -> int:
        calls.append(("config", list(args)))
        return 0

    monkeypatch.setattr(commands, "up", fake_up)
    monkeypatch.setattr(commands, "config", fake_config)

    run_cli(["up", "-d", "--build"])
    run_cli(["config", "--quiet"])

    assert calls == [("up", ["-d", "--build"]), ("config", ["--quiet"])]


def test_unknown_command_errors(run_cli) -> None:
    result = run_cli(["pull"], expected_code=2)

    assert "unknown command: pull" in result.output
    assert "jovy up" in result.output


def test_init_accepts_python_level_gpu_and_port(tmp_path: Path, run_cli) -> None:
    run_cli(
        [
            "init",
            str(tmp_path),
            "--image-level",
            "extended",
            "--python",
            "3.12",
            "--gpu",
            "all",
            "--port",
            "9999",
            "--token",
            "custom-token",
        ]
    )

    compose = yaml.safe_load((tmp_path / "compose.yaml").read_text())
    service = compose["services"]["jovy"]
    assert service["build"]["args"] == {
        "JOVY_BASE_IMAGE": ("ghcr.io/mihneateodorstoica/jovykit-extended:python-3.12"),
    }
    assert service["gpus"] == "all"
    assert service["environment"] == {"JUPYTER_TOKEN": "custom-token"}
    assert (tmp_path / "requirements.txt").read_text() == ""
    dockerfile = (tmp_path / "Dockerfile").read_text()
    assert (
        "ARG JOVY_BASE_IMAGE=ghcr.io/mihneateodorstoica/jovykit-extended:python-3.12"
        in dockerfile
    )
    assert "ARG PYTHON_VERSION" not in dockerfile


def test_init_auto_enables_detected_gpu(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, run_cli
) -> None:
    monkeypatch.setattr(commands, "detect_gpu_mode", lambda: "all")

    run_cli(["init", str(tmp_path)])

    compose = yaml.safe_load((tmp_path / "compose.yaml").read_text())
    assert compose["services"]["jovy"]["gpus"] == "all"


def test_help_is_compose_first(run_cli) -> None:
    result = run_cli(["--help"])

    assert "jovy up" in result.output
    assert "jovy start" in result.output
    assert "jovy config" in result.output
    assert "jovy compose COMMAND" in result.output
    assert "jovy add PACKAGE" in result.output
    assert "destroy" not in result.output
    assert "clean" not in result.output
