from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from rich.console import Console

from jovykit import commands
from jovykit.state import EnvironmentStatus
from jovykit.tui import JovyKitDashboard, _status_key, render_status_panel
from jovykit.tui_commands import ParsedTuiCommand, TuiCommandKind


def test_run_jovy_updates_ui_directly_after_threaded_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitDashboard()
    parsed = ParsedTuiCommand(
        kind=TuiCommandKind.JOVY,
        name="init",
        args=[],
        raw="init",
    )
    calls: list[str] = []

    def dispatch(command: ParsedTuiCommand) -> None:
        assert command is parsed
        calls.append("dispatch")

    monkeypatch.setattr(app, "_dispatch_jovy_command", dispatch)
    monkeypatch.setattr(app, "_clear_last_error", lambda: calls.append("clear"))
    monkeypatch.setattr(app, "refresh_status", lambda: calls.append("refresh"))
    monkeypatch.setattr(
        app,
        "call_from_thread",
        lambda *args, **kwargs: pytest.fail("call_from_thread used on app thread"),
    )

    asyncio.run(app._run_jovy(parsed))

    assert calls == ["dispatch", "clear", "refresh"]


def test_run_jovy_records_errors_directly_after_threaded_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitDashboard()
    parsed = ParsedTuiCommand(
        kind=TuiCommandKind.JOVY,
        name="init",
        args=[],
        raw="init",
    )
    calls: list[tuple[str, str]] = []

    def dispatch(_command: ParsedTuiCommand) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(app, "_dispatch_jovy_command", dispatch)
    monkeypatch.setattr(
        app, "_record_last_error", lambda message: calls.append(("error", message))
    )
    monkeypatch.setattr(app, "_append", lambda message: calls.append(("log", message)))
    monkeypatch.setattr(app, "refresh_status", lambda: calls.append(("refresh", "")))
    monkeypatch.setattr(
        app,
        "call_from_thread",
        lambda *args, **kwargs: pytest.fail("call_from_thread used on app thread"),
    )

    asyncio.run(app._run_jovy(parsed))

    assert ("error", "boom") in calls
    assert any(kind == "log" and "boom" in message for kind, message in calls)
    assert calls[-1] == ("refresh", "")


def test_dispatch_init_uses_default_jovykit_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitDashboard()
    parsed = ParsedTuiCommand(
        kind=TuiCommandKind.JOVY,
        name="init",
        args=[],
        raw="init",
    )
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        commands, "init_environment", lambda **kwargs: calls.append(kwargs)
    )

    app._dispatch_jovy_command(parsed, suspended=True)

    assert calls[0]["token"] == commands.DEFAULT_JUPYTER_TOKEN
    assert "password" not in calls[0]


def test_dispatch_destroy_streams_to_dashboard_log(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitDashboard()
    parsed = ParsedTuiCommand(
        kind=TuiCommandKind.JOVY,
        name="destroy",
        args=[],
        raw="destroy",
    )
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(commands, "destroy", lambda **kwargs: calls.append(kwargs))

    app._dispatch_jovy_command(parsed, suspended=True)

    assert calls[0]["stream"] is True


def test_dispatch_shell_command_streams_inside_dashboard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitDashboard()
    parsed = ParsedTuiCommand(
        kind=TuiCommandKind.JOVY,
        name="shell",
        args=["python", "--version"],
        raw="shell python --version",
    )
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(commands, "shell", lambda **kwargs: calls.append(kwargs))

    app._dispatch_jovy_command(parsed)

    assert calls[0]["command"] == "python --version"
    assert calls[0]["stream"] is True


def test_open_config_screen_pushes_editor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitDashboard()
    calls: list[Any] = []

    monkeypatch.setattr(
        app, "push_screen", lambda screen, callback: calls.append(screen)
    )

    app._open_config_screen()

    assert calls
    assert calls[0].env is None


def test_dispatch_config_is_dashboard_only() -> None:
    app = JovyKitDashboard()
    parsed = ParsedTuiCommand(
        kind=TuiCommandKind.JOVY,
        name="config",
        args=[],
        raw="config",
    )

    with pytest.raises(commands.JovyKitError, match="dashboard command input"):
        app._dispatch_jovy_command(parsed)


def test_dispatch_run_is_not_available_in_dashboard() -> None:
    app = JovyKitDashboard()
    parsed = ParsedTuiCommand(
        kind=TuiCommandKind.JOVY,
        name="run",
        args=[],
        raw="run",
    )

    with pytest.raises(
        commands.JovyKitError, match="not available inside the dashboard"
    ):
        app._dispatch_jovy_command(parsed)


def test_set_command_running_keeps_input_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitDashboard()

    class FakeInput:
        disabled = False

        def focus(self) -> None:
            return None

    command = FakeInput()
    monkeypatch.setattr(app, "query_one", lambda *_args, **_kwargs: command)

    app._set_command_running(True)

    assert command.disabled is False


def test_status_key_includes_url(create_project: Any) -> None:
    from jovykit.state import status_from_config

    status = status_from_config(create_project(token="dev-token").config)

    assert any("token=dev-token" in str(item) for item in _status_key(status))


def test_status_panel_keeps_header_compact() -> None:
    status = EnvironmentStatus(
        initialized=True,
        project_path=Path("/tmp/example"),
        env_dir=Path("/tmp/example/.jovy"),
        status="running",
        health="healthy",
        build="fresh",
        image="example:local",
        base_image="ghcr.io/example/base:latest",
        gpu="auto",
        port="127.0.0.1:8888",
        url="http://127.0.0.1:8888/lab?token=jovykit",
        package_count=3,
        volume="example-jovykit-home",
    )
    console = Console(record=True, width=120)

    console.print(render_status_panel(status))
    rendered = console.export_text()

    assert "JovyKit - example" in rendered
    assert "Status:" in rendered
    assert "Build:" in rendered
    assert "URL:" in rendered
    assert "Base:" not in rendered
    assert "GPU:" not in rendered
    assert "Packages:" not in rendered
    assert "Volume:" not in rendered
