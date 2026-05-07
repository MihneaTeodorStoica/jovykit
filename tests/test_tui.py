from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast

import pytest
from rich.console import Console
from rich.text import Text
from textual.widgets import Input, RichLog

from jovykit import commands
from jovykit.state import EnvironmentStatus
from jovykit.tui import (
    JovyKitDashboard,
    SelectableLog,
    _status_key,
    render_status_panel,
    _strip_ansi,
)
from jovykit.tui_commands import ParsedTuiCommand, TuiCommandKind, parse_tui_command


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
    monkeypatch.setattr(
        app, "_append_error", lambda message: calls.append(("log", message))
    )
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


def test_run_host_records_errors_instead_of_crashing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitDashboard()
    calls: list[tuple[str, str]] = []

    def fail_host_command(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("host command failed")

    monkeypatch.setattr("jovykit.tui.run_host_command", fail_host_command)
    monkeypatch.setattr(
        app, "_record_last_error", lambda message: calls.append(("error", message))
    )
    monkeypatch.setattr(
        app, "_append_error", lambda message: calls.append(("log", message))
    )
    monkeypatch.setattr(app, "refresh_status", lambda: calls.append(("refresh", "")))

    asyncio.run(app._run_host(["false"]))

    assert ("error", "host command failed") in calls
    assert any(kind == "log" and "host command failed" in msg for kind, msg in calls)
    assert calls[-1] == ("refresh", "")


def test_log_append_keeps_process_output_literal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitDashboard()
    written: list[Text] = []

    class FakeLog:
        def write(self, value: Text) -> None:
            written.append(value)

    monkeypatch.setattr(app, "query_one", lambda *_args, **_kwargs: FakeLog())

    app._append("package[dev]\\path")
    app._append_command("logs [latest]")
    app._append_error("bad [config]")

    assert [value.plain for value in written] == [
        "package[dev]\\path",
        "jovy> logs [latest]",
        "[Error] bad [config]",
    ]


def test_dashboard_log_allows_text_selection() -> None:
    log = SelectableLog(id="logs", min_width=1)

    assert log.allow_select is True
    assert log.focus_on_click() is True
    assert log.min_width == 1


def test_log_append_preserves_ansi_coloring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitDashboard()
    written: list[Text] = []

    class FakeLog:
        def write(self, value: Text) -> None:
            written.append(value)

    monkeypatch.setattr(app, "query_one", lambda *_args, **_kwargs: FakeLog())

    app._append("\x1b[31mred\x1b[0m plain")

    assert written[0].plain == "red plain"
    assert len(written[0].spans) > 0


def test_ctrl_c_clears_command_input_when_text_is_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitDashboard()
    exited: list[bool] = []

    class FakeInput:
        value = "run --build"

        def clear(self) -> None:
            self.value = ""

    command = FakeInput()
    monkeypatch.setattr(app, "query_one", lambda *_args, **_kwargs: command)
    monkeypatch.setattr(app, "exit", lambda: exited.append(True))

    app.action_clear_or_quit()

    assert command.value == ""
    assert exited == []


def test_ctrl_c_quits_when_command_input_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitDashboard()
    exited: list[bool] = []

    class FakeInput:
        value = ""

    command = FakeInput()
    monkeypatch.setattr(app, "query_one", lambda *_args, **_kwargs: command)
    monkeypatch.setattr(app, "exit", lambda: exited.append(True))

    app.action_clear_or_quit()

    assert exited == [True]


def test_dashboard_bindings_include_log_focus_toggle() -> None:
    binding_keys = [
        cast(tuple[str, str, str], binding)[0] for binding in JovyKitDashboard.BINDINGS
    ]

    assert "tab" in binding_keys


def test_dashboard_log_hides_scrollbars() -> None:
    log = SelectableLog(id="logs")

    assert log.show_vertical_scrollbar is False
    assert log.show_horizontal_scrollbar is False


def test_theme_command_is_now_unknown() -> None:
    parsed = parse_tui_command("theme dark")

    assert parsed.kind is TuiCommandKind.UNKNOWN
    assert parsed.name == "theme"
    assert parsed.args == ["dark"]


def test_strip_ansi_removes_color_codes() -> None:
    assert _strip_ansi("\x1b[31mred\x1b[0m plain") == "red plain"


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
    assert calls[0]["log_level"] == "ERROR"
    assert "password" not in calls[0]


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


def test_dispatch_shell_command_supports_cli_style_c_option(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitDashboard()
    parsed = ParsedTuiCommand(
        kind=TuiCommandKind.JOVY,
        name="shell",
        args=["-c", "python --version"],
        raw='shell -c "python --version"',
    )
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(commands, "shell", lambda **kwargs: calls.append(kwargs))

    app._dispatch_jovy_command(parsed)

    assert calls[0]["command"] == "python --version"
    assert calls[0]["stream"] is True


def test_dispatch_shell_command_supports_cli_style_long_option_equals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitDashboard()
    parsed = ParsedTuiCommand(
        kind=TuiCommandKind.JOVY,
        name="shell",
        args=["--command=python --version"],
        raw='shell --command="python --version"',
    )
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(commands, "shell", lambda **kwargs: calls.append(kwargs))

    app._dispatch_jovy_command(parsed)

    assert calls[0]["command"] == "python --version"
    assert calls[0]["stream"] is True


def test_dispatch_init_supports_cli_style_long_option_equals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitDashboard()
    parsed = ParsedTuiCommand(
        kind=TuiCommandKind.JOVY,
        name="init",
        args=["--log-level=INFO"],
        raw="init --log-level=INFO",
    )
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        commands, "init_environment", lambda **kwargs: calls.append(kwargs)
    )

    app._dispatch_jovy_command(parsed, suspended=True)

    assert calls[0]["log_level"] == "INFO"


def test_dispatch_build_is_quiet_by_default_and_verbose_when_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitDashboard()
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(commands, "build", lambda **kwargs: calls.append(kwargs))

    app._dispatch_jovy_command(
        ParsedTuiCommand(
            kind=TuiCommandKind.JOVY,
            name="build",
            args=["--pull"],
            raw="build --pull",
        )
    )
    app._dispatch_jovy_command(
        ParsedTuiCommand(
            kind=TuiCommandKind.JOVY,
            name="build",
            args=["--verbose"],
            raw="build --verbose",
        )
    )

    assert calls[0]["pull"] is True
    assert calls[0]["stream"] is False
    assert calls[0]["verbose"] is False
    assert calls[1]["stream"] is True
    assert calls[1]["verbose"] is True


def test_open_config_screen_pushes_editor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitDashboard()
    calls: list[Any] = []
    callbacks: list[Any] = []
    events: list[str] = []

    def fake_push_screen(screen: object, callback: object) -> None:
        calls.append(screen)
        callbacks.append(callback)

    monkeypatch.setattr(app, "push_screen", fake_push_screen)
    monkeypatch.setattr(app, "_append_markup", lambda _message: events.append("log"))
    monkeypatch.setattr(app, "refresh_status", lambda: events.append("status"))
    monkeypatch.setattr(app, "_restore_dashboard_focus", lambda: events.append("focus"))

    app._open_config_screen()

    assert calls
    assert calls[0].env is None
    callbacks[0]("saved")
    assert events == ["log", "status", "focus"]


def test_restore_dashboard_focus_clears_selection_and_repaints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitDashboard()
    events: list[str] = []

    class FakeLog:
        def refresh(self, *, repaint: bool = True, layout: bool = False) -> None:
            events.append(f"log:{repaint}:{layout}")

    class FakeInput:
        def focus(self) -> None:
            events.append("focus")

    def fake_query_one(selector: object, *_args: object, **_kwargs: object) -> object:
        if selector is RichLog:
            return FakeLog()
        if selector is Input:
            return FakeInput()
        raise AssertionError(selector)

    monkeypatch.setattr(app, "clear_selection", lambda: events.append("clear"))
    monkeypatch.setattr(app, "refresh", lambda **_kwargs: events.append("refresh"))
    monkeypatch.setattr(app, "query_one", fake_query_one)

    app._restore_dashboard_focus()

    assert events == ["clear", "refresh", "log:True:True", "focus"]


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

    with pytest.raises(commands.JovyKitError, match="Unsupported dashboard command"):
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


def test_show_help_includes_blocked_and_keybinding_hints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitDashboard()
    written: list[Text] = []

    class FakeLog:
        def write(self, value: Text) -> None:
            written.append(value)

    monkeypatch.setattr(app, "query_one", lambda *_args, **_kwargs: FakeLog())

    app._show_help()

    assert written
    help_text = written[-1].plain
    assert "Blocked in Dashboard" in help_text
    assert "run: The run command is not available inside the dashboard." in help_text
    assert "logs: The logs command is not available inside the dashboard." in help_text
    assert "ctrl+l clear logs" in help_text


def test_refresh_logs_clears_snapshot_when_environment_is_not_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitDashboard()
    app._last_log_snapshot = "old logs"
    app._last_status = EnvironmentStatus(
        initialized=True,
        project_path=Path("/tmp/example"),
        env_dir=Path("/tmp/example/.jovy"),
        status="stopped",
        health="unknown",
        build="fresh",
        image="example:local",
        base_image="ghcr.io/example/base:latest",
        gpu="auto",
        port="127.0.0.1:8888",
        url="http://127.0.0.1:8888/lab?token=jovykit",
        package_count=3,
        home_mount="/tmp/example/.jovy/home",
    )
    monkeypatch.setattr(
        "jovykit.tui.compose_logs",
        lambda *_args, **_kwargs: pytest.fail(
            "compose_logs should not run when stopped"
        ),
    )

    app.refresh_logs()

    assert app._last_log_snapshot == ""


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
        home_mount="/tmp/example/.jovy/home",
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
    assert "Home:" in rendered


def test_status_panel_wraps_cleanly_in_narrow_terminals() -> None:
    status = EnvironmentStatus(
        initialized=True,
        project_path=Path("/tmp/ai"),
        env_dir=Path("/tmp/ai/.jovy"),
        status="healthy",
        health="healthy",
        build="fresh",
        image="jovykit-ai:local",
        base_image="ghcr.io/example/base:latest",
        gpu="auto",
        port="127.0.0.1:8888",
        url="http://127.0.0.1:8888/lab?token=jovykit",
        package_count=3,
        home_mount="/tmp/ai/.jovy/home",
    )
    console = Console(record=True, width=40)

    console.print(render_status_panel(status))
    rendered = console.export_text()

    assert "JovyKit - ai" in rendered
    assert "Status: healthy   Build: fresh" in rendered
    assert "Image: jovykit-ai:local" in rendered
    assert "http://127.0.0.1:8888/lab?token=" in rendered
    assert all(len(line) <= 40 for line in rendered.splitlines())
