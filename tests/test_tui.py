from __future__ import annotations

import asyncio
from typing import Any

import pytest

from jovykit import commands
from jovykit.tui import JovyKitDashboard, _status_key
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


def test_dispatch_config_launches_editor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitDashboard()
    parsed = ParsedTuiCommand(
        kind=TuiCommandKind.JOVY,
        name="config",
        args=[],
        raw="config",
    )
    calls: list[Any] = []

    monkeypatch.setattr(
        "jovykit.config_editor.run_config_editor",
        lambda **kwargs: calls.append(kwargs["env"]),
    )
    monkeypatch.setattr(app, "_append", lambda message: calls.append(message))

    app._dispatch_jovy_command(parsed, suspended=True)

    assert calls[0] is None
    assert "Config editor closed." in calls


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
