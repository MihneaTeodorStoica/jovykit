from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from jovykit import commands, runtime
from jovykit.config import JovyKitError


def _recording_runner(calls: list[list[str]]):
    def fake(args: list[str], **kwargs: object) -> int:
        calls.append(list(args))
        return 0

    return fake


def test_compose_args_use_root_compose_file(tmp_path: Path) -> None:
    assert runtime.compose_args(tmp_path, ["up", "-d"]) == [
        "docker",
        "compose",
        "-f",
        str(tmp_path / "compose.yaml"),
        "up",
        "-d",
    ]


def test_compose_passthrough_requires_compose_project(tmp_path: Path) -> None:
    with pytest.raises(JovyKitError, match="compose.yaml not found"):
        commands.compose_passthrough(["ps"], root=tmp_path)


def test_up_maps_to_compose_up(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(runtime, "run_command", _recording_runner(calls))
    (tmp_path / "compose.yaml").write_text("services: {}\n", encoding="utf-8")

    commands.up(["-d"], root=tmp_path)

    assert calls == [
        ["docker", "compose", "-f", str(tmp_path / "compose.yaml"), "up", "-d"]
    ]


def test_start_stop_config_logs_match_compose(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(runtime, "run_command", _recording_runner(calls))
    (tmp_path / "compose.yaml").write_text("services: {}\n", encoding="utf-8")

    commands.start(root=tmp_path)
    commands.stop(["jovy"], root=tmp_path)
    commands.config(["--quiet"], root=tmp_path)
    commands.logs(["-f"], root=tmp_path)

    prefix = ["docker", "compose", "-f", str(tmp_path / "compose.yaml")]
    assert calls == [
        [*prefix, "start"],
        [*prefix, "stop", "jovy"],
        [*prefix, "config", "--quiet"],
        [*prefix, "logs", "-f"],
    ]


def test_shell_maps_to_service_exec(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(runtime, "run_command", _recording_runner(calls))
    (tmp_path / "compose.yaml").write_text("services: {}\n", encoding="utf-8")

    commands.shell(["python"], root=tmp_path)

    assert calls == [
        [
            "docker",
            "compose",
            "-f",
            str(tmp_path / "compose.yaml"),
            "exec",
            "jovy",
            "python",
        ]
    ]


def test_run_command_streams_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(runtime, "require_docker", lambda: None)

    class FakeStdout:
        def __iter__(self):
            return iter(["one\n", "two\n"])

    class FakeProcess:
        stdout = FakeStdout()

        def wait(self) -> int:
            return 0

    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    lines: list[str] = []

    code = runtime.run_command(
        ["docker", "compose", "ps"], cwd=tmp_path, log=lines.append
    )

    assert code == 0
    assert lines == ["one", "two"]
