from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from jovykit import commands
from jovykit.config import JovyKitError


def test_load_env_reports_stale_legacy_config(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    (project.env_dir / "jovy.toml").write_text("legacy\n", encoding="utf-8")
    messages: list[str] = []

    config = commands.load_env(project.env_dir, emit=messages.append)

    assert config.env_dir == project.env_dir
    assert "Ignoring stale legacy config" in messages[0]


def test_ensure_built_streams_stale_build(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    calls: list[str] = []
    messages: list[str] = []
    monkeypatch.setattr(commands, "is_build_stale", lambda config: True)
    monkeypatch.setattr(
        commands,
        "build_streaming",
        lambda config, *, log: calls.append(config.image_ref),
    )

    commands.ensure_built(project.config, emit=messages.append, stream=True)

    assert calls == [project.config.image_ref]
    assert messages == ["Building JovyKit overlay image..."]


def test_ensure_built_skips_fresh_build(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    monkeypatch.setattr(commands, "is_build_stale", lambda config: False)
    monkeypatch.setattr(
        commands,
        "build_image",
        lambda config: pytest.fail("fresh build should not run"),
    )

    commands.ensure_built(project.config)


def test_init_environment_force_rejects_non_jovykit_directory(tmp_path: Path) -> None:
    env_dir = tmp_path / ".jovy"
    env_dir.mkdir()
    (env_dir / "notes.txt").write_text("not jovykit", encoding="utf-8")

    with pytest.raises(JovyKitError, match="Refusing to force initialize"):
        commands.init_environment(path=env_dir, force=True)


def test_jupyter_access_url_includes_token(create_project: Any) -> None:
    project = create_project(token="dev-token")

    assert commands.jupyter_access_url(project.config).endswith("/lab?token=dev-token")


def test_build_uses_streaming_backend(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    calls: list[tuple[bool, bool]] = []
    monkeypatch.chdir(project.root)
    monkeypatch.setattr(
        commands,
        "compile_requirements_lock",
        lambda *args, **kwargs: kwargs["output_file"].write_text(
            "locked\n", encoding="utf-8"
        ),
    )
    monkeypatch.setattr(
        commands,
        "build_streaming",
        lambda config, *, log, no_cache=False, pull=False: calls.append(
            (no_cache, pull)
        ),
    )

    commands.build(no_cache=True, pull=True, stream=True)

    assert calls == [(True, True)]


def test_shell_command_can_stream_without_tty(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    monkeypatch.chdir(project.root)
    compose_calls: list[tuple[tuple[str, ...], bool, bool]] = []

    monkeypatch.setattr(
        commands,
        "compose",
        lambda config, *args, attached=False, log=None: compose_calls.append(
            (args, attached, log is not None)
        ),
    )

    commands.shell(command="python --version", stream=True, emit=lambda line: None)

    assert compose_calls == [
        (("exec", "-T", "jovy", "bash", "-lc", "python --version"), False, True)
    ]


def test_install_restarts_running_container_after_build(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    events: list[object] = []
    ps_output = json.dumps(
        [{"Service": "jovy", "State": "running", "Health": "healthy"}]
    )

    def prepare(config: Any, **_kwargs: Any) -> Any:
        events.append("prepare")
        return config

    monkeypatch.setattr(commands, "compose_ps", lambda config: ps_output)
    monkeypatch.setattr(commands, "prepare_environment", prepare)
    monkeypatch.setattr(commands, "is_build_stale", lambda config: True)
    monkeypatch.setattr(
        commands,
        "build_streaming",
        lambda config, *, log: events.append("build"),
    )
    monkeypatch.setattr(
        commands,
        "stop_watcher",
        lambda env_dir: events.append(("stop_watcher", env_dir)),
    )
    monkeypatch.setattr(
        commands,
        "start_watcher",
        lambda env_dir: events.append(("start_watcher", env_dir)),
    )
    monkeypatch.setattr(
        commands,
        "compose",
        lambda config, *args, attached=False, log=None: events.append(
            ("compose", args, attached, log is not None)
        ),
    )

    commands.install(project.config, stream=True, emit=lambda line: None)

    assert events == [
        "prepare",
        "build",
        ("stop_watcher", project.env_dir),
        ("compose", ("up", "-d", "--no-build", "jovy"), False, True),
        ("start_watcher", project.env_dir),
    ]


def test_is_container_running_accepts_json_lines(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    output = (
        '{"Service": "helper", "State": "exited"}\n'
        "not-json\n"
        '{"Name": "project-jovy-1", "state": "running"}\n'
    )
    monkeypatch.setattr(commands, "compose_ps", lambda config: output)

    assert commands.is_container_running(project.config) is True


def test_is_container_running_handles_missing_or_stopped_services(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    monkeypatch.setattr(commands, "compose_ps", lambda config: "")
    assert commands.is_container_running(project.config) is False

    monkeypatch.setattr(
        commands,
        "compose_ps",
        lambda config: json.dumps([{"Service": "jovy", "State": "exited"}]),
    )
    assert commands.is_container_running(project.config) is False


def test_install_skips_restart_when_no_build_is_used(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    events: list[str] = []
    monkeypatch.setattr(
        commands,
        "compose_ps",
        lambda config: json.dumps([{"Service": "jovy", "State": "running"}]),
    )
    monkeypatch.setattr(
        commands, "prepare_environment", lambda config, **kwargs: config
    )
    monkeypatch.setattr(commands, "is_build_stale", lambda config: True)
    monkeypatch.setattr(
        commands, "compose", lambda *args, **kwargs: events.append("compose")
    )

    commands.install(project.config, no_build=True)

    assert events == []


def test_lifecycle_commands_support_streaming_compose(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    monkeypatch.chdir(project.root)
    compose_calls: list[tuple[tuple[str, ...], bool, bool]] = []
    watcher_starts: list[Path] = []
    watcher_stops: list[Path] = []
    monkeypatch.setattr(commands, "install", lambda config, **kwargs: None)
    monkeypatch.setattr(
        commands,
        "compose",
        lambda config, *args, attached=False, log=None: compose_calls.append(
            (args, attached, log is not None)
        ),
    )
    monkeypatch.setattr(
        commands, "start_watcher", lambda env_dir: watcher_starts.append(env_dir)
    )
    monkeypatch.setattr(
        commands, "stop_watcher", lambda env_dir: watcher_stops.append(env_dir)
    )

    commands.up(stream=True, emit=lambda line: None)
    commands.down(timeout=3, stream=True, emit=lambda line: None)
    commands.restart(no_build=True, timeout=4, stream=True, emit=lambda line: None)
    commands.logs(
        tail="10",
        since="5m",
        timestamps=True,
        follow=True,
        stream=True,
        emit=lambda line: None,
    )

    assert compose_calls == [
        (("up", "-d"), False, True),
        (("stop", "--timeout", "3"), False, True),
        (("stop", "--timeout", "4"), False, True),
        (("up", "-d"), False, True),
        (("logs", "--tail", "10", "--since", "5m", "--timestamps", "-f"), False, True),
    ]
    assert watcher_starts == [project.env_dir, project.env_dir]
    assert watcher_stops == [project.env_dir, project.env_dir]


def test_exec_streaming_disables_tty(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    monkeypatch.chdir(project.root)
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        commands,
        "compose",
        lambda config, *args, attached=False, log=None: calls.append(args),
    )

    commands.exec_in_container(
        ["python", "--version"], stream=True, emit=lambda line: None
    )

    assert calls == [("exec", "-T", "jovy", "python", "--version")]
