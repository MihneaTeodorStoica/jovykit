import sys
from pathlib import Path

import pytest

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
