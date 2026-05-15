"""Textual dashboard for JovyKit project environments."""

from __future__ import annotations

import asyncio
import re
import shlex
import webbrowser
from collections import deque
from collections.abc import Sequence
from pathlib import Path

from rich.panel import Panel
from rich.text import Text
from textual import on
from textual.app import App, ComposeResult, ScreenStackError
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.widgets import Input, RichLog, Static

from jovykit import commands
from jovykit.config import JovyKitError, read_state, write_state
from jovykit.runtime import compose_logs, run_host_command
from jovykit.state import EnvironmentStatus, discover_status
from jovykit.tui_commands import (
    COMMAND_SPECS,
    ParsedTuiCommand,
    TuiCommandKind,
    parse_tui_command,
)


class SelectableLog(RichLog):
    """Rich log that permits selection without stealing command focus."""

    ALLOW_SELECT = True
    FOCUS_ON_CLICK = True

    def __init__(
        self,
        *,
        max_lines: int | None = None,
        min_width: int = 78,
        wrap: bool = False,
        highlight: bool = False,
        markup: bool = False,
        auto_scroll: bool = True,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(
            max_lines=max_lines,
            min_width=min_width,
            wrap=wrap,
            highlight=highlight,
            markup=markup,
            auto_scroll=auto_scroll,
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )
        self.show_vertical_scrollbar = False
        self.show_horizontal_scrollbar = False


_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
STATUS_PANEL_HEIGHT = 6


def _status_key(status: EnvironmentStatus) -> tuple[object, ...]:
    return (
        status.initialized,
        status.project_path,
        status.env_dir,
        status.status,
        status.health,
        status.build,
        status.image,
        status.base_image,
        status.gpu,
        status.port,
        status.url,
        status.package_count,
        status.home_mount,
        status.last_error,
    )


class JovyKitDashboard(App[None]):
    """Full-screen dashboard for managing a local JovyKit environment."""

    CSS = """
    Screen {
        background: #111111;
        color: #e0e0e0;
    }

    #root {
        height: 100%;
        padding: 1;
    }

    #status {
        height: 6;
        min-height: 6;
        max-height: 6;
        margin-bottom: 0;
        color: #e0e0e0;
    }

    #logs {
        height: 1fr;
        border: round #333333;
        padding: 0 1;
        margin-bottom: 1;
        background: #1a1a1a;
        scrollbar-size: 0 0;
        color: #e0e0e0;
    }

    #command {
        height: 3;
        border: tall #333333;
        margin-top: 0;
        margin-bottom: 0;
        background: #1a1a1a;
        color: #e0e0e0;
    }

    #command:focus {
        border: tall #f37726;
    }
    """

    BINDINGS = [
        ("ctrl+c", "clear_or_quit", "Clear/Quit"),
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+l", "clear_logs", "Clear logs"),
        ("tab", "toggle_log_focus", "Toggle log/input focus"),
    ]

    def __init__(self, *, env: Path | None = None) -> None:
        super().__init__()
        self.env = env
        self._last_status: EnvironmentStatus | None = None
        self._last_status_key: tuple[object, ...] | None = None
        self._last_log_snapshot = ""
        self._command_running = False
        self._command_queue: deque[ParsedTuiCommand] = deque()
        self._active_command: ParsedTuiCommand | None = None
        self._progress_label: str | None = None
        self._progress_steps = 0

    def compose(self) -> ComposeResult:
        """Compose the dashboard layout."""
        with Vertical(id="root"):
            yield Static(id="status")
            yield SelectableLog(
                id="logs",
                highlight=False,
                markup=False,
                min_width=1,
                wrap=True,
                auto_scroll=True,
                max_lines=2000,
            )
            yield Input(
                placeholder="up, build --pull, config, open, help", id="command"
            )

    def on_mount(self) -> None:
        """Initialize dashboard state."""
        self.title = "JovyKit"
        self.query_one(Input).focus()
        self._append_markup("[bold cyan][JovyKit][/bold cyan] Ready")
        self._append("Try: init | up | build --pull | config | open | help")
        self.refresh_status()
        self.set_interval(4, self.refresh_status)

    @on(Input.Submitted, "#command")
    async def on_command_submitted(self, event: Input.Submitted) -> None:
        """Handle submitted dashboard commands."""
        raw = event.value
        event.input.clear()
        parsed = parse_tui_command(raw)
        if parsed.kind is TuiCommandKind.EMPTY:
            return
        self._append_command(raw.strip())
        await self._handle_parsed_command(parsed)

    def action_clear_logs(self) -> None:
        """Clear visible dashboard logs."""
        self.query_one(RichLog).clear()

    def action_clear_or_quit(self) -> None:
        """Clear command text when present, otherwise quit the dashboard."""
        command = self.query_one(Input)
        if command.value:
            command.clear()
            return
        self._quit_now()

    def action_toggle_log_focus(self) -> None:
        """Toggle focus between command input and log panel."""
        if self.focused is self.query_one(RichLog):
            self.query_one(Input).focus()
            return
        self.query_one(RichLog).focus()

    async def action_quit(self) -> None:
        """Exit quickly by cancelling background work first."""
        self._quit_now()

    def _quit_now(self) -> None:
        try:
            self.workers.cancel_all()
        except Exception:
            pass
        self.exit()

    def refresh_status(self) -> None:
        """Refresh the top status panel."""
        status = discover_status(self.env)
        self._last_status = status
        queued_labels = tuple(self._queued_command_labels())
        status_key = (
            *_status_key(status),
            self._active_command_label(),
            queued_labels,
            self._progress_label,
            self._progress_steps,
        )
        if status_key != self._last_status_key:
            self._last_status_key = status_key
            self.query_one("#status", Static).update(
                render_status_panel(
                    status,
                    active_command=self._active_command_label(),
                    queued_count=len(self._command_queue),
                    queued_labels=queued_labels,
                    progress_text=self._progress_text(),
                )
            )

    def refresh_logs(self) -> None:
        """Poll recent container logs while the environment is running."""
        status = self._last_status
        if self._command_running:
            return
        if status is None:
            return
        if not status.is_running:
            self._last_log_snapshot = ""
            return
        if status.env_dir is None:
            return
        try:
            config = commands.load_env(self.env)
            snapshot = compose_logs(config, tail="60").strip()
        except JovyKitError:
            return
        if not snapshot or snapshot == self._last_log_snapshot:
            return
        new_text = _snapshot_suffix(self._last_log_snapshot, snapshot)
        self._last_log_snapshot = snapshot
        for line in new_text.splitlines():
            self._append(line)

    async def _handle_parsed_command(self, parsed: ParsedTuiCommand) -> None:
        if parsed.kind is TuiCommandKind.UNKNOWN:
            self._append_error(parsed.message or "Unknown command")
            return
        if parsed.kind is TuiCommandKind.BLOCKED:
            self._append_error(parsed.message or "Command is not available here.")
            return
        if parsed.kind is TuiCommandKind.LOCAL:
            await self._handle_local(parsed)
            return
        if self._command_running:
            self._queue_command(parsed)
            return
        await self._start_parsed_command(parsed)

    async def _start_parsed_command(self, parsed: ParsedTuiCommand) -> None:
        if self._shell_blocked_while_down(parsed):
            await self._start_next_queued_command()
            return
        if parsed.kind is TuiCommandKind.HOST:
            self._begin_command(parsed)
            self.run_worker(self._run_host(parsed.args), exclusive=False)
            return
        if parsed.spec is not None and parsed.spec.opens_screen:
            self._begin_command(parsed)
            self._open_config_screen(run_next_on_close=True)
            return
        if parsed.spec is not None and parsed.spec.suspend_app and not parsed.args:
            await self._run_suspended(parsed)
            return
        if parsed.spec is not None and parsed.spec.run_in_worker:
            self._begin_command(parsed)
            self.run_worker(self._run_jovy(parsed), exclusive=False)
            return
        await self._run_jovy(parsed)

    def _shell_blocked_while_down(self, parsed: ParsedTuiCommand) -> bool:
        if parsed.kind is not TuiCommandKind.JOVY or parsed.name != "shell":
            return False
        status = self._last_status
        if status is None or status.is_running:
            return False
        self._append_error(commands.SHELL_REQUIRES_RUNNING_MESSAGE)
        return True

    def _queue_command(self, parsed: ParsedTuiCommand) -> None:
        label = _command_label(parsed)
        if self._active_command is not None and _same_command(
            parsed, self._active_command
        ):
            self._append_markup(
                "[bold yellow][JovyKit][/bold yellow] " f"Already running: {label}."
            )
            return
        if any(_same_command(parsed, command) for command in self._command_queue):
            position = self._queue_position(parsed) or len(self._command_queue)
            self._append_markup(
                "[bold yellow][JovyKit][/bold yellow] "
                f"Already queued #{position}: {label}."
            )
            return
        self._command_queue.append(parsed)
        self._append_markup(
            "[bold yellow][JovyKit][/bold yellow] "
            f"Queued #{len(self._command_queue)}: {label}."
        )
        self._refresh_status_if_mounted()

    async def _start_next_queued_command(self) -> None:
        if self._command_running:
            return
        if not self._command_queue:
            return
        parsed = self._command_queue.popleft()
        label = _command_label(parsed)
        self._append_markup(f"[cyan][JovyKit][/cyan] Starting: {label}")
        self._refresh_status_if_mounted()
        await self._start_parsed_command(parsed)

    async def _finish_command(
        self,
        *,
        refresh_logs_after: bool = False,
        focus_command: bool = False,
    ) -> None:
        self._active_command = None
        self._set_command_running(False)
        self.refresh_status()
        if refresh_logs_after:
            self.refresh_logs()
        if focus_command:
            self.query_one(Input).focus()
        await self._start_next_queued_command()

    async def _handle_local(self, parsed: ParsedTuiCommand) -> None:
        if parsed.name in {"quit", "exit"}:
            self._quit_now()
            return
        if parsed.name == "clear":
            self.action_clear_logs()
            return
        if parsed.name == "refresh":
            self.refresh_status()
            self.refresh_logs()
            self._append_markup("[cyan][JovyKit][/cyan] Status refreshed.")
            return
        if parsed.name == "open":
            self._open_url()
            return
        if parsed.name == "help":
            self._show_help()

    async def _run_host(self, args: list[str]) -> None:
        self._set_command_running(True)
        try:
            if not args:
                self._append_error("Pass a host command after !.")
                return
            await asyncio.to_thread(
                run_host_command,
                args,
                cwd=Path.cwd(),
                log=lambda line: self.call_from_thread(self._append, line),
            )
            self._clear_last_error()
        except Exception as exc:
            self._record_last_error(str(exc))
            self._append_error(str(exc))
        finally:
            await self._finish_command()

    async def _run_jovy(self, parsed: ParsedTuiCommand) -> None:
        if self._active_command is None:
            self._active_command = parsed
        self._set_command_running(True)
        try:
            await asyncio.to_thread(self._dispatch_jovy_command, parsed)
            self._clear_last_error()
        except Exception as exc:
            self._record_last_error(str(exc))
            self._append_error(str(exc))
        finally:
            await self._finish_command()

    async def _run_suspended(self, parsed: ParsedTuiCommand) -> None:
        if self._active_command is None:
            self._active_command = parsed
        self._set_command_running(True)
        try:
            self._append("Suspending dashboard for interactive command...")
            with self.suspend():
                self._dispatch_jovy_command(parsed, suspended=True)
            self._clear_last_error()
        except Exception as exc:
            self._record_last_error(str(exc))
            self._append_error(str(exc))
        finally:
            await self._finish_command(
                refresh_logs_after=(
                    parsed.spec is not None and parsed.spec.refresh_logs_after
                ),
                focus_command=True,
            )

    def _dispatch_jovy_command(
        self, parsed: ParsedTuiCommand, *, suspended: bool = False
    ) -> None:
        emit = self._append if suspended else self._threadsafe_append
        name = parsed.name
        args = parsed.args
        if name == "init":

            def emit_init_line(line: str) -> None:
                if line.startswith("Jupyter: "):
                    return
                emit(line)

            commands.init_environment(
                path=_init_path(args),
                image=_option_value(args, "--image", "base"),
                gpus=_option_value(args, "--gpus", "auto"),
                port=_option_int(args, "--port") or 8888,
                token=_option_value(args, "--token", commands.DEFAULT_JUPYTER_TOKEN),
                log_level=_option_value(args, "--log-level", "ERROR"),
                project_name=_option_value(args, "--name", "") or None,
                image_name=_option_value(args, "--image-name", "") or None,
                image_tag=_option_value(args, "--tag", "local"),
                workdir=_option_value(args, "--workdir", "work"),
                force="--force" in args,
                emit=emit_init_line,
            )
            emit("Ready. Start Jupyter with: up")
        elif name == "add":
            packages, requirement_files = _add_args(args)
            commands.add(packages, requirement_files=requirement_files, emit=emit)
        elif name == "remove":
            commands.remove(args, emit=emit)
        elif name == "install":
            commands.install(
                commands.load_env(emit=emit),
                no_build="--no-build" in args,
                upgrade="--upgrade" in args,
                emit=emit,
                stream=True,
            )
        elif name == "build":
            verbose = "--verbose" in args or "-v" in args
            if verbose:
                commands.build(
                    no_cache="--no-cache" in args,
                    pull="--pull" in args,
                    emit=emit,
                    stream=True,
                    verbose=True,
                )
            else:
                self._build_with_dashboard_progress(args=args, emit=emit)
        elif name == "up":
            commands.up(no_build="--no-build" in args, emit=emit, stream=False)
        elif name == "down":
            commands.down(
                timeout=_option_int(args, "--timeout"), emit=emit, stream=False
            )
        elif name == "restart":
            commands.restart(
                no_build="--no-build" in args,
                timeout=_option_int(args, "--timeout"),
                emit=emit,
                stream=False,
            )
        elif name == "shell":
            command = _shell_command(args)
            commands.shell(
                command=command,
                emit=emit,
                stream=not suspended and command is not None,
            )
        elif name == "exec":
            commands.exec_in_container(args, emit=emit, stream=True)
        elif name == "status":
            commands.status(json_output="--json" in args, emit=emit)
        elif name == "config":
            raise JovyKitError("Open config from the dashboard command input.")
        elif name == "clean":
            commands.clean(emit=emit)
        elif name == "destroy":
            commands.destroy(
                remove_dir="--remove-dir" in args,
                keep_image="--keep-image" in args,
                emit=emit,
                stream=True,
            )
        else:
            raise JovyKitError(f"Unsupported dashboard command: {name}")

    def _open_url(self) -> None:
        status = self._last_status or discover_status(self.env)
        if status.url == "unavailable":
            self._append_markup(
                "[bold yellow][JovyKit][/bold yellow] "
                "No Jupyter URL yet. Start it with: up"
            )
            return
        webbrowser.open(status.url)
        self._append_markup(f"[cyan][JovyKit][/cyan] Opened {status.url}")

    def _open_config_screen(self, *, run_next_on_close: bool = False) -> None:
        from jovykit.config_editor import JovyKitConfigEditorScreen

        def on_close(result: str | None) -> None:
            if result and result != "cancelled":
                self._append_markup(f"[cyan][JovyKit][/cyan] Config {result}.")
            if run_next_on_close:
                self._active_command = None
                self._set_command_running(False)
                self.refresh_status()
                self._restore_dashboard_focus()
                self.run_worker(self._start_next_queued_command(), exclusive=False)
                return
            self.refresh_status()
            self._restore_dashboard_focus()

        self.push_screen(JovyKitConfigEditorScreen(env=self.env), on_close)

    def _record_last_error(self, message: str) -> None:
        try:
            config = commands.load_env(self.env)
        except JovyKitError:
            return
        state = read_state(config.env_dir)
        state["last_error"] = message
        write_state(config.env_dir, state)

    def _clear_last_error(self) -> None:
        try:
            config = commands.load_env(self.env)
        except JovyKitError:
            return
        state = read_state(config.env_dir)
        if "last_error" in state:
            state.pop("last_error", None)
            write_state(config.env_dir, state)

    def _show_help(self) -> None:
        blocked_commands = [
            spec
            for spec in COMMAND_SPECS
            if not spec.available_in_dashboard and spec.blocked_hint
        ]
        blocked_lines = "\n".join(
            f"- {spec.name}: {spec.blocked_hint}" for spec in blocked_commands
        )
        self._append_markup(
            "[bold cyan]JovyKit Commands[/bold cyan]\n"
            "  init              create .jovy\n"
            "  up/start/u        start Jupyter\n"
            "  down/stop/d       stop Jupyter\n"
            "  build/b           build image\n"
            "  install/apply     refresh lockfile and image\n"
            "  add/remove        edit packages\n"
            "  status/s/ps       show state\n"
            "  config/c          edit settings\n"
            "  shell/sh          open container shell\n"
            "  exec/x            run in container\n"
            "[bold cyan]Dashboard[/bold cyan]\n"
            "  help/?            show this help\n"
            "  open/url          open Jupyter\n"
            "  refresh/reload    refresh state\n"
            "  clear/cls         clear logs\n"
            "  quit/q            exit\n"
            "[bold cyan]Queue[/bold cyan]\n"
            "  Commands entered during a long task wait their turn.\n"
            "[bold cyan]Host Commands[/bold cyan]\n"
            "  !pwd\n"
            "[bold cyan]Blocked in Dashboard[/bold cyan]\n"
            f"{blocked_lines}\n"
            "[bold cyan]Keys[/bold cyan]\n"
            "  ctrl+c clear or quit\n"
            "  ctrl+l clear logs"
        )

    def _threadsafe_append(self, line: str) -> None:
        self.call_from_thread(self._append, line)

    def _build_with_dashboard_progress(
        self,
        *,
        args: list[str],
        emit: commands.Emitter,
    ) -> None:
        config = commands.load_env(self.env, emit=emit)
        config = commands.prepare_environment(config, emit=emit)
        emit("Building JovyKit overlay image...")
        self.call_from_thread(self._begin_progress, "Building JovyKit image")
        try:
            commands.build_streaming(
                config,
                log=lambda _line: self.call_from_thread(self._tick_progress),
                no_cache="--no-cache" in args,
                pull="--pull" in args,
            )
        finally:
            self.call_from_thread(self._finish_progress)

    def _begin_progress(self, label: str) -> None:
        self._progress_label = label
        self._progress_steps = 0
        self._refresh_status_if_mounted()

    def _tick_progress(self) -> None:
        if self._progress_label is None:
            return
        self._progress_steps += 1
        self._refresh_status_if_mounted()

    def _finish_progress(self) -> None:
        self._progress_label = None
        self._progress_steps = 0
        self._refresh_status_if_mounted()

    def _progress_text(self) -> str | None:
        if self._progress_label is None:
            return None
        return _progress_bar(self._progress_steps)

    def _append(self, line: str) -> None:
        self._write_log(Text.from_ansi(line))

    def _append_markup(self, line: str) -> None:
        self._write_log(Text.from_markup(line))

    def _append_command(self, raw: str) -> None:
        text = Text.from_markup("[bold]jovy>[/bold] ")
        text.append(raw)
        self._write_log(text)

    def _append_error(self, message: str) -> None:
        text = Text.from_markup("[bold red][Error][/bold red] ")
        text.append(message)
        self._write_log(text)

    def _write_log(self, text: Text) -> None:
        try:
            log = self.query_one(RichLog)
        except (NoMatches, ScreenStackError):
            return
        try:
            log.write(text)
        except AttributeError:
            return

    def _selected_text(self) -> str | None:
        try:
            return self.screen.get_selected_text()
        except Exception:
            return None

    def _restore_dashboard_focus(self) -> None:
        self.clear_selection()
        self.refresh(repaint=True, layout=True)
        try:
            self.query_one(RichLog).refresh(repaint=True, layout=True)
            self.query_one(Input).focus()
        except (NoMatches, ScreenStackError):
            return

    def _set_command_running(self, running: bool) -> None:
        self._command_running = running
        try:
            command = self.query_one(Input)
        except (NoMatches, ScreenStackError):
            return
        if not running:
            command.focus()

    def _begin_command(self, parsed: ParsedTuiCommand) -> None:
        self._active_command = parsed
        self._set_command_running(True)
        self._refresh_status_if_mounted()

    def _active_command_label(self) -> str | None:
        if self._active_command is None:
            return None
        return _command_label(self._active_command)

    def _queued_command_labels(self) -> list[str]:
        return [_command_label(command) for command in self._command_queue]

    def _queue_position(self, parsed: ParsedTuiCommand) -> int | None:
        for index, command in enumerate(self._command_queue, start=1):
            if _same_command(parsed, command):
                return index
        return None

    def _refresh_status_if_mounted(self) -> None:
        try:
            self.refresh_status()
        except (NoMatches, ScreenStackError):
            return


def render_status_panel(
    status: EnvironmentStatus,
    *,
    active_command: str | None = None,
    queued_count: int = 0,
    queued_labels: Sequence[str] | None = None,
    progress_text: str | None = None,
) -> Panel:
    """Render the top status panel."""
    details = Text(no_wrap=True, overflow="crop")
    details.append("Status: ", style="bold #e0e0e0")
    details.append(_status_label(status))
    details.append("   Build: ", style="bold #e0e0e0")
    details.append(status.build)
    queue_text = _queue_status(queued_labels, queued_count)
    details.append("\nActivity: ", style="bold #e0e0e0")
    details.append(active_command or "idle")
    if progress_text:
        details.append("   ", style="bold #e0e0e0")
        details.append(progress_text, style="#f37726")
    if queue_text:
        details.append("   Queue: ", style="bold #e0e0e0")
        details.append(queue_text)
    details.append("\nImage: ", style="bold #e0e0e0")
    details.append(status.image)
    if status.last_error:
        details.append("\nError: ", style="bold #d33c3c")
        details.append(status.last_error)
    elif status.is_running and status.url:
        details.append("\nURL: ", style="bold #e0e0e0")
        details.append(status.url)
    elif status.home_mount:
        details.append("\nHome: ", style="bold #e0e0e0")
        details.append(status.home_mount)
    else:
        details.append("\nNext: ", style="bold #e0e0e0")
        details.append("up starts Jupyter")
    return Panel(
        details,
        title=f"JovyKit - {status.project_path.name}",
        border_style=_border_style(status.status),
        style="on #1a1a1a",
        height=STATUS_PANEL_HEIGHT,
    )


def run_dashboard(*, env: Path | None = None) -> None:
    """Run the JovyKit Textual dashboard."""
    JovyKitDashboard(env=env).run(mouse=False)


def _status_label(status: EnvironmentStatus) -> str:
    if status.health in {"healthy", "unhealthy"} and status.status == status.health:
        return status.status
    if status.health != "unknown" and status.status == "running":
        return f"{status.status} {status.health}"
    return status.status


def _border_style(status: str) -> str:
    if status in {"healthy", "running"}:
        return "#7ab648"
    if status in {"error", "unhealthy"}:
        return "#d33c3c"
    if status in {"starting", "stale image", "unknown"}:
        return "#f37726"
    return "#6c8ebf"


def _command_label(parsed: ParsedTuiCommand) -> str:
    return parsed.raw or parsed.name


def _same_command(left: ParsedTuiCommand, right: ParsedTuiCommand) -> bool:
    return (
        left.kind is right.kind and left.name == right.name and left.args == right.args
    )


def _queue_status(labels: Sequence[str] | None, queued_count: int) -> str | None:
    if labels:
        if len(labels) <= 2:
            return " -> ".join(labels)
        return f"{labels[0]} -> {labels[1]} (+{len(labels) - 2})"
    if queued_count:
        return f"{queued_count} waiting"
    return None


def _progress_bar(steps: int, *, width: int = 16) -> str:
    """Return an indeterminate progress bar for dashboard commands."""
    if width < 6:
        width = 6
    chunk = min(6, width)
    span = max(0, width - chunk)
    start = steps % (span + 1)
    cells = ["."] * width
    for index in range(start, start + chunk):
        cells[index] = "="
    return "[" + "".join(cells) + f"] {steps} lines"


def _option_value(args: list[str], name: str, default: str) -> str:
    prefix = f"{name}="
    for arg in args:
        if arg.startswith(prefix):
            return arg[len(prefix) :]
    try:
        index = args.index(name)
    except ValueError:
        return default
    try:
        return args[index + 1]
    except IndexError:
        return default


def _option_int(args: list[str], name: str) -> int | None:
    value = _option_value(args, name, "")
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _init_path(args: list[str]) -> Path:
    if args and not args[0].startswith("-"):
        return Path(args[0])
    return Path(commands.DEFAULT_ENV_DIR)


def _add_args(args: list[str]) -> tuple[list[str], list[Path]]:
    packages: list[str] = []
    requirement_files: list[Path] = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in {"-r", "--requirement"} and index + 1 < len(args):
            requirement_files.append(Path(args[index + 1]))
            index += 2
            continue
        if arg.startswith("--requirement="):
            requirement_files.append(Path(arg.split("=", 1)[1]))
            index += 1
            continue
        packages.append(arg)
        index += 1
    return packages, requirement_files


def _shell_command(args: list[str]) -> str | None:
    option_value = _option_value(args, "--command", "")
    if option_value:
        return option_value
    option_value = _option_value(args, "-c", "")
    if option_value:
        return option_value
    if not args:
        return None
    return " ".join(shlex.quote(arg) for arg in args)


def _snapshot_suffix(previous: str, current: str) -> str:
    if previous and current.startswith(previous):
        return current[len(previous) :].lstrip("\n")
    return current


def _strip_ansi(value: str) -> str:
    return _ANSI_RE.sub("", value)
