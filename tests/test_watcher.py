from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

import jovykit.watcher as watcher
from jovykit.config import initial_config_text, load_config
from jovykit.generate import write_generated_files


def test_apply_config_change_regenerates_and_restarts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    calls: list[tuple[str, ...]] = []

    monkeypatch.setattr(watcher, "is_build_stale", lambda config: False)
    monkeypatch.setattr(
        watcher,
        "compose",
        lambda config, *args, attached=False: calls.append(args),
    )

    watcher.apply_config_change(env_dir)

    assert calls == [("up", "-d", "jovy")]


def test_pid_and_log_paths_are_inside_environment(tmp_path: Path) -> None:
    env_dir = tmp_path / ".jovy"

    assert watcher.pid_path(env_dir) == env_dir / watcher.PID_FILE
    assert watcher.log_path(env_dir) == env_dir / watcher.LOG_FILE


def test_is_process_running_uses_signal_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[int, int]] = []
    monkeypatch.setattr(
        watcher.os, "kill", lambda pid, signal: calls.append((pid, signal))
    )

    assert watcher.is_process_running(1234) is True
    assert calls == [(1234, 0)]


def test_is_process_running_returns_false_for_os_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_kill(pid: int, signal: int) -> None:
        raise OSError("missing")

    monkeypatch.setattr(watcher.os, "kill", fake_kill)

    assert watcher.is_process_running(1234) is False


def test_start_watcher_returns_when_existing_pid_is_running(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    watcher.pid_path(project.env_dir).write_text("1234\n", encoding="utf-8")
    monkeypatch.setattr(watcher, "is_process_running", lambda pid: True)
    monkeypatch.setattr(
        watcher.subprocess,
        "Popen",
        lambda *args, **kwargs: pytest.fail("watcher should not start twice"),
    )

    watcher.start_watcher(project.env_dir)

    assert watcher.pid_path(project.env_dir).read_text(encoding="utf-8") == "1234\n"


def test_start_watcher_replaces_stale_pid_and_writes_new_pid(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    watcher.pid_path(project.env_dir).write_text("not-a-pid\n", encoding="utf-8")
    popen_calls: list[tuple[list[str], dict[str, Any]]] = []

    class FakeProcess:
        pid = 5678

    def fake_popen(args: list[str], **kwargs: Any) -> FakeProcess:
        popen_calls.append((args, kwargs))
        return FakeProcess()

    monkeypatch.setattr(watcher.subprocess, "Popen", fake_popen)

    watcher.start_watcher(project.env_dir)

    assert watcher.pid_path(project.env_dir).read_text(encoding="utf-8") == "5678\n"
    assert popen_calls[0][0][-3:] == [
        str(project.env_dir),
        "--poll-interval",
        str(project.config.watch_poll_interval),
    ]
    assert popen_calls[0][1]["start_new_session"] is True


def test_stop_watcher_removes_invalid_pid(create_project: Any) -> None:
    project = create_project()
    watcher.pid_path(project.env_dir).write_text("bad\n", encoding="utf-8")

    watcher.stop_watcher(project.env_dir)

    assert not watcher.pid_path(project.env_dir).exists()


def test_stop_watcher_sends_sigterm_to_running_pid(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    watcher.pid_path(project.env_dir).write_text("1234\n", encoding="utf-8")
    signals: list[tuple[int, int]] = []
    monkeypatch.setattr(watcher, "is_process_running", lambda pid: True)
    monkeypatch.setattr(
        watcher.os, "kill", lambda pid, signal: signals.append((pid, signal))
    )

    watcher.stop_watcher(project.env_dir)

    assert signals == [(1234, watcher.signal.SIGTERM)]
    assert not watcher.pid_path(project.env_dir).exists()


def test_apply_config_change_builds_when_stale(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    calls: list[str] = []
    monkeypatch.setattr(watcher, "is_build_stale", lambda config: True)
    monkeypatch.setattr(watcher, "build_image", lambda config: calls.append("build"))
    monkeypatch.setattr(
        watcher,
        "compose",
        lambda config, *args, attached=False: calls.append("compose"),
    )

    watcher.apply_config_change(project.env_dir)

    assert calls == ["build", "compose"]


def test_watch_config_applies_change_and_continues_after_jovykit_error(
    monkeypatch: pytest.MonkeyPatch,
    create_project: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = create_project()
    mtimes = iter([1.0, 2.0, 3.0])
    apply_calls: list[Path] = []

    class FakeConfigPath:
        def stat(self) -> Any:
            return type("Stat", (), {"st_mtime": next(mtimes)})()

        def __str__(self) -> str:
            return str(project.config.config_path)

    config = replace(project.config, config_path=FakeConfigPath())
    monkeypatch.setattr(watcher, "load_config", lambda env_dir: config)

    def fake_sleep(interval: float) -> None:
        if len(apply_calls) >= 2:
            raise KeyboardInterrupt

    def fake_apply(env_dir: Path) -> None:
        apply_calls.append(env_dir)
        if len(apply_calls) == 1:
            raise watcher.JovyKitError("bad config")

    monkeypatch.setattr(watcher.time, "sleep", fake_sleep)
    monkeypatch.setattr(watcher, "apply_config_change", fake_apply)

    with pytest.raises(KeyboardInterrupt):
        watcher.watch_config(project.env_dir, poll_interval=0.01)

    output = capsys.readouterr().out
    assert "Watching" in output
    assert "Error: bad config" in output
    assert "Applied config change" in output
