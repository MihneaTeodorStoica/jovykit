import sys
from pathlib import Path

import pytest

import jovykit.cli as cli
from jovykit.cli import main


def run_cli(monkeypatch: pytest.MonkeyPatch, args: list[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["jovy", *args])
    try:
        main()
    except SystemExit as exc:
        if exc.code != 0:
            raise


def test_run_without_environment_prints_clean_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exc:
        run_cli(monkeypatch, ["run"])

    assert exc.value.code == 1
    output = capsys.readouterr().out
    assert "No JovyKit environment found" in output
    assert "Traceback" not in output


def test_init_existing_environment_prints_clean_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    run_cli(monkeypatch, ["init", ".jovy"])

    with pytest.raises(SystemExit) as exc:
        run_cli(monkeypatch, ["init", ".jovy"])

    assert exc.value.code == 1
    output = capsys.readouterr().out
    assert "JovyKit environment already exists" in output
    assert "Traceback" not in output


def test_version_flag_prints_package_version(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    run_cli(monkeypatch, ["--version"])

    assert "jovykit" in capsys.readouterr().out


def test_init_accepts_jupyter_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    run_cli(
        monkeypatch,
        ["init", ".jovy", "--token", "dev-token", "--log-level", "INFO"],
    )

    config_text = (tmp_path / ".jovy" / "jovy.toml").read_text(encoding="utf-8")
    assert 'token = "dev-token"' in config_text
    assert 'log_level = "INFO"' in config_text


def test_run_uses_compose_watch_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    run_cli(monkeypatch, ["init", ".jovy"])
    calls: list[tuple[str, ...]] = []

    def fake_compose(config, *args: str, attached: bool = False) -> None:
        calls.append(args)

    monkeypatch.setattr(cli, "compose", fake_compose)

    run_cli(monkeypatch, ["run", "--no-build"])

    assert calls == [("up", "--watch")]


def test_start_can_disable_compose_watch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    run_cli(monkeypatch, ["init", ".jovy"])
    calls: list[tuple[str, ...]] = []

    def fake_compose(config, *args: str, attached: bool = False) -> None:
        calls.append(args)

    monkeypatch.setattr(cli, "compose", fake_compose)

    run_cli(monkeypatch, ["start", "--no-build", "--no-watch"])

    assert calls == [("up", "-d")]


def test_logs_accepts_since_and_timestamps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    run_cli(monkeypatch, ["init", ".jovy"])
    calls: list[tuple[str, ...]] = []

    def fake_compose(config, *args: str, attached: bool = False) -> None:
        calls.append(args)

    monkeypatch.setattr(cli, "compose", fake_compose)

    run_cli(monkeypatch, ["logs", "--tail", "50", "--since", "10m", "--timestamps"])

    assert calls == [("logs", "--tail", "50", "--since", "10m", "--timestamps", "-f")]
