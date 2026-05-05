from __future__ import annotations

import asyncio

import pytest

from jovykit import commands
from jovykit.tui import JovyKitDashboard
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


def test_dispatch_init_uses_default_jovykit_password(
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

    assert calls[0]["password"] == commands.DEFAULT_JUPYTER_PASSWORD


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
