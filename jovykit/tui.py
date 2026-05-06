"""Textual dashboard for JovyKit project environments."""

from __future__ import annotations

import asyncio
import shlex
import webbrowser
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
from jovykit.tui_commands import ParsedTuiCommand, TuiCommandKind, parse_tui_command


class SelectableLog(RichLog):
    """Rich log with dashboard text selection kept explicit."""

    ALLOW_SELECT = True
    FOCUS_ON_CLICK = True


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
        status.volume,
        status.last_error,
    )


class JovyKitDashboard(App[None]):
    """Full-screen dashboard for managing a local JovyKit environment."""

    CSS = """
    Screen {
        background: #101418;
        color: #e8eef2;
    }

    #root {
        height: 100%;
        padding: 1;
    }

    #status {
        height: auto;
        min-height: 5;
        margin-bottom: 1;
    }

    #logs {
        height: 1fr;
        border: round #3b5666;
        padding: 0 1;
        background: #0b0f12;
    }

    #command {
        height: 3;
        border: tall #4f7890;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        ("ctrl+c", "quit_or_copy", "Copy/Quit"),
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+l", "clear_logs", "Clear logs"),
    ]

    def __init__(self, *, env: Path | None = None) -> None:
        super().__init__()
        self.env = env
        self._last_status: EnvironmentStatus | None = None
        self._last_status_key: tuple[object, ...] | None = None
        self._last_log_snapshot = ""
        self._command_running = False

    def compose(self) -> ComposeResult:
        """Compose the dashboard layout."""
        with Vertical(id="root"):
            yield Static(id="status")
            yield Input(placeholder="jovy> up", id="command")
            yield SelectableLog(
                id="logs",
                highlight=False,
                markup=False,
                min_width=1,
                wrap=True,
                auto_scroll=True,
                max_lines=2000,
            )

    def on_mount(self) -> None:
        """Initialize dashboard state."""
        self.title = "JovyKit"
        self.query_one(Input).focus()
        self._append_markup(
            "[bold cyan][JovyKit][/bold cyan] Dashboard ready. Type help."
        )
        self.refresh_status()
        self.set_interval(4, self.refresh_status)
        self.set_interval(5, self.refresh_logs)

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

    def action_quit_or_copy(self) -> None:
        """Copy selected text when present, otherwise quit the dashboard."""
        selected = self._selected_text()
        if selected is not None:
            self.copy_to_clipboard(selected)
            return
        self.exit()

    def refresh_status(self) -> None:
        """Refresh the top status panel."""
        status = discover_status(self.env)
        self._last_status = status
        status_key = _status_key(status)
        if status_key != self._last_status_key:
            self._last_status_key = status_key
            self.query_one("#status", Static).update(render_status_panel(status))

    def refresh_logs(self) -> None:
        """Poll recent container logs while the environment is running."""
        status = self._last_status
        if self._command_running:
            return
        if status is None or not status.is_running or status.env_dir is None:
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
        if parsed.kind is TuiCommandKind.LOCAL:
            await self._handle_local(parsed)
            return
        if self._command_running:
            self._append_markup(
                "[bold yellow][JovyKit][/bold yellow] Command already running."
            )
            return
        if parsed.kind is TuiCommandKind.HOST:
            self.run_worker(self._run_host(parsed.args), exclusive=False)
            return
        if parsed.name == "config":
            self._open_config_screen()
            return
        if parsed.name == "shell" and not parsed.args:
            await self._run_suspended(parsed)
            return
        self.run_worker(self._run_jovy(parsed), exclusive=False)

    async def _handle_local(self, parsed: ParsedTuiCommand) -> None:
        if parsed.name in {"quit", "exit"}:
            self.exit()
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
        if not args:
            self._append_error("Pass a host command after !.")
            return
        self._set_command_running(True)
        try:
            await asyncio.to_thread(
                run_host_command,
                args,
                cwd=Path.cwd(),
                log=lambda line: self.call_from_thread(self._append, line),
            )
        finally:
            self._set_command_running(False)

    async def _run_jovy(self, parsed: ParsedTuiCommand) -> None:
        self._set_command_running(True)
        try:
            await asyncio.to_thread(self._dispatch_jovy_command, parsed)
            self._clear_last_error()
        except Exception as exc:
            self._record_last_error(str(exc))
            self._append_error(str(exc))
        finally:
            self._set_command_running(False)
            self.refresh_status()

    async def _run_suspended(self, parsed: ParsedTuiCommand) -> None:
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
            self._set_command_running(False)
            self.refresh_status()
            self.refresh_logs()
            self.query_one(Input).focus()

    def _dispatch_jovy_command(
        self, parsed: ParsedTuiCommand, *, suspended: bool = False
    ) -> None:
        emit = self._append if suspended else self._threadsafe_append
        name = parsed.name
        args = parsed.args
        if name == "init":
            commands.init_environment(
                path=_init_path(args),
                image=_option_value(args, "--image", "base"),
                gpus=_option_value(args, "--gpus", "auto"),
                port=_option_int(args, "--port") or 8888,
                token=_option_value(args, "--token", commands.DEFAULT_JUPYTER_TOKEN),
                project_name=_option_value(args, "--name", "") or None,
                image_name=_option_value(args, "--image-name", "") or None,
                image_tag=_option_value(args, "--tag", "local"),
                workdir=_option_value(args, "--workdir", "work"),
                force="--force" in args,
                emit=emit,
            )
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
            commands.build(
                no_cache="--no-cache" in args,
                pull="--pull" in args,
                emit=emit,
                stream=True,
            )
        elif name == "run":
            raise JovyKitError(
                "The run command is not available inside the dashboard. "
                "Use up, or run jovy run from your shell."
            )
        elif name == "up":
            commands.up(no_build="--no-build" in args, emit=emit, stream=True)
        elif name == "down":
            commands.down(
                timeout=_option_int(args, "--timeout"), emit=emit, stream=True
            )
        elif name == "restart":
            commands.restart(
                no_build="--no-build" in args,
                timeout=_option_int(args, "--timeout"),
                emit=emit,
                stream=True,
            )
        elif name == "logs":
            commands.logs(
                follow=False,
                tail=_option_value(args, "--tail", "100"),
                emit=emit,
                stream=True,
            )
        elif name == "shell":
            command = " ".join(shlex.quote(arg) for arg in args) if args else None
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

    def _open_url(self) -> None:
        status = self._last_status or discover_status(self.env)
        if status.url == "unavailable":
            self._append_markup("[bold yellow][JovyKit][/bold yellow] URL unavailable.")
            return
        webbrowser.open(status.url)
        self._append_markup(f"[cyan][JovyKit][/cyan] Opened {status.url}")

    def _open_config_screen(self) -> None:
        from jovykit.config_editor import JovyKitConfigEditorScreen

        def on_close(result: str | None) -> None:
            if result:
                self._append_markup(f"[cyan][JovyKit][/cyan] Config {result}.")
            self.refresh_status()
            self.refresh_logs()
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
        self._append_markup(
            "[bold cyan]Commands[/bold cyan]\n"
            "init, add, remove, install, build, up, down, restart, logs, shell, "
            "exec, status, config, clean, destroy\n"
            "[bold cyan]Dashboard[/bold cyan]\n"
            "help, clear, open, refresh, quit, exit\n"
            "[bold cyan]Host shell[/bold cyan]\n"
            "!pwd, !ls, !docker ps"
        )

    def _threadsafe_append(self, line: str) -> None:
        self.call_from_thread(self._append, line)

    def _append(self, line: str) -> None:
        self.query_one(RichLog).write(Text(line))

    def _append_markup(self, line: str) -> None:
        self.query_one(RichLog).write(Text.from_markup(line))

    def _append_command(self, raw: str) -> None:
        text = Text.from_markup("[bold]jovy>[/bold] ")
        text.append(raw)
        self.query_one(RichLog).write(text)

    def _append_error(self, message: str) -> None:
        text = Text.from_markup("[bold red][Error][/bold red] ")
        text.append(message)
        self.query_one(RichLog).write(text)

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


def render_status_panel(status: EnvironmentStatus) -> Panel:
    """Render the top status panel."""
    details = Text()
    details.append("Status: ", style="bold")
    details.append(_status_label(status))
    details.append("   Build: ", style="bold")
    details.append(status.build)
    details.append("\nImage: ", style="bold")
    details.append(status.image)
    if status.url:
        details.append("\nURL: ", style="bold")
        details.append(status.url)
    if status.last_error:
        details.append("\nError: ", style="bold red")
        details.append(status.last_error)
    return Panel(
        details,
        title=f"JovyKit - {status.project_path.name}",
        border_style=_border_style(status.status),
    )


def run_dashboard(*, env: Path | None = None) -> None:
    """Run the JovyKit Textual dashboard."""
    JovyKitDashboard(env=env).run()


def _status_label(status: EnvironmentStatus) -> str:
    if status.health in {"healthy", "unhealthy"} and status.status == status.health:
        return status.status
    if status.health != "unknown" and status.status == "running":
        return f"{status.status} {status.health}"
    return status.status


def _border_style(status: str) -> str:
    if status in {"healthy", "running"}:
        return "green"
    if status in {"error", "unhealthy"}:
        return "red"
    if status in {"starting", "stale image", "unknown"}:
        return "yellow"
    return "blue"


def _option_value(args: list[str], name: str, default: str) -> str:
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


def _snapshot_suffix(previous: str, current: str) -> str:
    if previous and current.startswith(previous):
        return current[len(previous) :].lstrip("\n")
    return current
