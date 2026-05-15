from __future__ import annotations

import asyncio
from collections import deque
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
    STATUS_PANEL_HEIGHT,
    _progress_bar,
    _status_key,
    _strip_ansi,
    render_status_panel,
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


def test_run_host_without_args_finishes_and_starts_next_queued_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitDashboard()
    queued = parse_tui_command("status")
    app._command_queue.append(queued)
    errors: list[str] = []
    started: list[str] = []

    async def fake_start(command: ParsedTuiCommand) -> None:
        started.append(command.raw)

    monkeypatch.setattr(app, "_append_error", errors.append)
    monkeypatch.setattr(app, "_append_markup", lambda _message: None)
    monkeypatch.setattr(app, "_start_parsed_command", fake_start)
    monkeypatch.setattr(app, "refresh_status", lambda: None)

    asyncio.run(app._run_host([]))

    assert errors == ["Pass a host command after !."]
    assert app._command_running is False
    assert started == ["status"]


def test_handle_command_queues_when_command_is_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitDashboard()
    parsed = parse_tui_command("build --pull")
    messages: list[str] = []
    app._command_running = True

    monkeypatch.setattr(app, "_append_markup", messages.append)

    asyncio.run(app._handle_parsed_command(parsed))

    assert list(app._command_queue) == [parsed]
    assert "Queued #1: build --pull." in messages[-1]


def test_queue_ignores_duplicate_waiting_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitDashboard()
    parsed = parse_tui_command("up")
    messages: list[str] = []
    app._command_running = True
    app._command_queue.append(parsed)

    monkeypatch.setattr(app, "_append_markup", messages.append)

    asyncio.run(app._handle_parsed_command(parse_tui_command("up")))

    assert list(app._command_queue) == [parsed]
    assert "Already queued #1: up." in messages[-1]


def test_queue_ignores_duplicate_running_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitDashboard()
    parsed = parse_tui_command("build")
    messages: list[str] = []
    app._command_running = True
    app._active_command = parsed

    monkeypatch.setattr(app, "_append_markup", messages.append)

    asyncio.run(app._handle_parsed_command(parse_tui_command("build")))

    assert list(app._command_queue) == []
    assert "Already running: build." in messages[-1]


@pytest.mark.parametrize("raw", ["shell", "shell python --version"])
def test_shell_while_down_is_blocked_before_start(
    monkeypatch: pytest.MonkeyPatch,
    raw: str,
) -> None:
    app = JovyKitDashboard()
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
    errors: list[str] = []

    async def fail_suspended(_parsed: ParsedTuiCommand) -> None:
        pytest.fail("shell should not suspend while the environment is down")

    monkeypatch.setattr(app, "_append_error", errors.append)
    monkeypatch.setattr(app, "_run_suspended", fail_suspended)
    monkeypatch.setattr(
        app,
        "run_worker",
        lambda *_args, **_kwargs: pytest.fail(
            "shell should not enter worker mode while the environment is down"
        ),
    )

    asyncio.run(app._start_parsed_command(parse_tui_command(raw)))

    assert errors == [commands.SHELL_REQUIRES_RUNNING_MESSAGE]
    assert app._command_running is False


def test_finish_command_starts_next_queued_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitDashboard()
    queued = parse_tui_command("status")
    app._command_running = True
    app._command_queue.append(queued)
    started: list[str] = []

    async def fake_start(command: ParsedTuiCommand) -> None:
        started.append(command.raw)

    monkeypatch.setattr(app, "_append_markup", lambda _message: None)
    monkeypatch.setattr(app, "_start_parsed_command", fake_start)
    monkeypatch.setattr(app, "refresh_status", lambda: None)

    asyncio.run(app._finish_command())

    assert app._command_running is False
    assert app._command_queue == deque()
    assert started == ["status"]


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


def test_dashboard_init_suppresses_startup_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitDashboard()
    parsed = ParsedTuiCommand(
        kind=TuiCommandKind.JOVY,
        name="init",
        args=[],
        raw="init",
    )
    lines: list[str] = []

    def fake_init_environment(**kwargs: object) -> None:
        emit = kwargs["emit"]
        assert callable(emit)
        emit("Initialized .jovy")
        emit("Jupyter: http://127.0.0.1:8888/lab?token=jovykit")

    monkeypatch.setattr(commands, "init_environment", fake_init_environment)
    monkeypatch.setattr(app, "_append", lines.append)

    app._dispatch_jovy_command(parsed, suspended=True)

    assert lines == ["Initialized .jovy", "Ready. Start Jupyter with: up"]


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


def test_suspended_shell_does_not_refresh_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    app = JovyKitDashboard()
    parsed = parse_tui_command("shell")
    assert parsed.spec is not None
    calls: list[str] = []

    class FakeInput:
        def focus(self) -> None:
            calls.append("focus")

    monkeypatch.setattr(app, "_append", lambda _line: calls.append("append"))
    monkeypatch.setattr(commands, "shell", lambda **_kwargs: calls.append("shell"))
    monkeypatch.setattr(app, "_dispatch_jovy_command", lambda _parsed, **_kwargs: None)
    monkeypatch.setattr(app, "_clear_last_error", lambda: calls.append("clear"))
    monkeypatch.setattr(app, "refresh_status", lambda: calls.append("status"))

    def fail_refresh_logs() -> None:
        pytest.fail("refresh_logs should not run")

    def track_running(running: bool) -> None:
        calls.append(f"running={running}")

    monkeypatch.setattr(app, "refresh_logs", fail_refresh_logs)
    monkeypatch.setattr(app, "_set_command_running", track_running)
    monkeypatch.setattr(app, "query_one", lambda *_args, **_kwargs: FakeInput())

    asyncio.run(app._run_suspended(parsed))

    assert parsed.spec.refresh_logs_after is False
    assert "status" in calls
    assert "refresh_logs" not in calls
    assert "focus" in calls


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
    calls: list[tuple[str, dict[str, object]]] = []
    progress: list[str] = []

    def call_now(method: Any, *args: object) -> None:
        method(*args)

    def fake_prepare(config: object, **kwargs: object) -> object:
        calls.append(("prepare", kwargs))
        emit = kwargs["emit"]
        assert callable(emit)
        emit("Compiling JovyKit dependency lockfile...")
        return config

    def fake_build_streaming(*_args: object, **kwargs: object) -> None:
        calls.append(("build_streaming", kwargs))
        log = kwargs["log"]
        assert callable(log)
        log("step 1")
        log("step 2")

    monkeypatch.setattr(app, "call_from_thread", call_now)
    monkeypatch.setattr(app, "_append", progress.append)
    monkeypatch.setattr(app, "_refresh_status_if_mounted", lambda: None)
    monkeypatch.setattr(commands, "load_env", lambda *args, **kwargs: object())
    monkeypatch.setattr(commands, "prepare_environment", fake_prepare)
    monkeypatch.setattr(commands, "build_streaming", fake_build_streaming)
    monkeypatch.setattr(
        commands, "build", lambda **kwargs: calls.append(("build", kwargs))
    )

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

    assert progress == [
        "Compiling JovyKit dependency lockfile...",
        "Building JovyKit overlay image...",
    ]
    assert calls[0][0] == "prepare"
    assert callable(calls[0][1]["emit"])
    quiet_build = next(kwargs for name, kwargs in calls if name == "build_streaming")
    assert quiet_build["pull"] is True
    assert app._progress_steps == 0
    verbose_build = calls[-1][1]
    assert calls[-1][0] == "build"
    assert verbose_build["stream"] is True
    assert verbose_build["verbose"] is True


def test_progress_bar_animates_with_line_count() -> None:
    assert _progress_bar(0) == "[======..........] 0 lines"
    assert _progress_bar(2) == "[..======........] 2 lines"


def test_dashboard_progress_text_stays_compact() -> None:
    app = JovyKitDashboard()
    app._progress_label = "Building JovyKit image"
    app._progress_steps = 0

    assert app._progress_text() == "[======..........] 0 lines"


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


def test_open_config_screen_cancel_is_quiet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitDashboard()
    callbacks: list[Any] = []
    events: list[str] = []

    monkeypatch.setattr(
        app,
        "push_screen",
        lambda _screen, callback: callbacks.append(callback),
    )
    monkeypatch.setattr(app, "_append_markup", lambda _message: events.append("log"))
    monkeypatch.setattr(app, "refresh_status", lambda: events.append("status"))
    monkeypatch.setattr(app, "_restore_dashboard_focus", lambda: events.append("focus"))

    app._open_config_screen()
    callbacks[0]("cancelled")

    assert events == ["status", "focus"]


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
    assert "Home:" not in rendered


def test_status_panel_shows_dashboard_progress() -> None:
    status = EnvironmentStatus(
        initialized=True,
        project_path=Path("/tmp/example"),
        env_dir=Path("/tmp/example/.jovy"),
        status="stopped",
        health="unknown",
        build="stale",
        image="example:local",
        base_image="ghcr.io/example/base:latest",
        gpu="auto",
        port="127.0.0.1:8888",
        url="unavailable",
        package_count=3,
        home_mount="",
    )
    console = Console(record=True, width=120)

    console.print(
        render_status_panel(
            status,
            active_command="build",
            progress_text=_progress_bar(0),
        )
    )
    rendered = console.export_text()

    assert "Activity: build" in rendered
    assert "[======..........] 0 lines" in rendered
    assert "Building JovyKit image" not in rendered


def test_status_panel_shows_queued_labels() -> None:
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

    console.print(
        render_status_panel(
            status,
            active_command="build",
            queued_labels=("up", "status"),
        )
    )
    rendered = console.export_text()

    assert "Activity: build" in rendered
    assert "Queue: up -> status" in rendered


def test_status_panel_height_is_stable_during_actions() -> None:
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
    variants = [
        render_status_panel(status),
        render_status_panel(status, active_command="build"),
        render_status_panel(status, active_command="build", queued_labels=("up",)),
        render_status_panel(
            status,
            active_command="build",
            queued_labels=("up",),
            progress_text=_progress_bar(0),
        ),
        render_status_panel(
            EnvironmentStatus(
                initialized=True,
                project_path=status.project_path,
                env_dir=status.env_dir,
                status="error",
                health=status.health,
                build=status.build,
                image=status.image,
                base_image=status.base_image,
                gpu=status.gpu,
                port=status.port,
                url=status.url,
                package_count=status.package_count,
                home_mount=status.home_mount,
                last_error="bad value(s) in fds_to_keep",
            ),
            active_command="build",
            progress_text=_progress_bar(0),
        ),
    ]

    for panel in variants:
        console = Console(record=True, width=120)
        console.print(panel)
        rendered = console.export_text()

        assert len(rendered.splitlines()) == STATUS_PANEL_HEIGHT


def test_status_panel_crops_cleanly_in_narrow_terminals() -> None:
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
    lines = rendered.splitlines()

    assert "JovyKit - ai" in rendered
    assert "Status: healthy   Build: fresh" in rendered
    assert "Image: jovykit-ai:local" in rendered
    assert "http://127.0.0.1:8888/lab?token" in rendered
    assert "Home:" not in rendered
    assert len(lines) == STATUS_PANEL_HEIGHT
    assert all(len(line) <= 40 for line in lines)
