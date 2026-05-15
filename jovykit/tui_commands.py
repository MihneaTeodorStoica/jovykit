"""Command model and parser for the JovyKit dashboard."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from difflib import get_close_matches
from enum import Enum
from typing import Literal


class TuiCommandKind(str, Enum):
    """Kinds of commands accepted by the dashboard input."""

    EMPTY = "empty"
    HOST = "host"
    JOVY = "jovy"
    LOCAL = "local"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


CommandNamespace = Literal["local", "jovy"]


@dataclass(frozen=True)
class DashboardCommandSpec:
    """Authoritative metadata for a dashboard command."""

    name: str
    category: CommandNamespace
    help_text: str
    usage: str | None = None
    aliases: tuple[str, ...] = ()
    available_in_dashboard: bool = True
    local_only: bool = False
    run_in_worker: bool = True
    suspend_app: bool = False
    opens_screen: bool = False
    refresh_status_after: bool = True
    refresh_logs_after: bool = False
    blocked_hint: str | None = None


COMMAND_SPECS: tuple[DashboardCommandSpec, ...] = (
    DashboardCommandSpec(
        "help",
        "local",
        "Show dashboard command help.",
        usage="help",
        aliases=("?",),
        local_only=True,
        run_in_worker=False,
        refresh_status_after=False,
    ),
    DashboardCommandSpec(
        "clear",
        "local",
        "Clear dashboard logs.",
        usage="clear",
        aliases=("cls",),
        local_only=True,
        run_in_worker=False,
        refresh_status_after=False,
    ),
    DashboardCommandSpec(
        "open",
        "local",
        "Open the current Jupyter URL in a browser.",
        usage="open",
        aliases=("url", "browser"),
        local_only=True,
        run_in_worker=False,
        refresh_status_after=False,
    ),
    DashboardCommandSpec(
        "refresh",
        "local",
        "Refresh environment status and recent logs now.",
        usage="refresh",
        aliases=("reload",),
        local_only=True,
        run_in_worker=False,
        refresh_status_after=True,
        refresh_logs_after=True,
    ),
    DashboardCommandSpec(
        "quit",
        "local",
        "Exit the dashboard.",
        usage="quit",
        aliases=("exit", "q"),
        local_only=True,
        run_in_worker=False,
        refresh_status_after=False,
    ),
    DashboardCommandSpec(
        "init",
        "jovy",
        "Create a JovyKit environment.",
        usage="init [--image base] [--port 8888] [--token jovykit]",
    ),
    DashboardCommandSpec(
        "add",
        "jovy",
        "Add Python packages to jovy.toml.",
        usage="add <package...>",
    ),
    DashboardCommandSpec(
        "remove",
        "jovy",
        "Remove Python packages from jovy.toml.",
        usage="remove <package...>",
    ),
    DashboardCommandSpec(
        "install",
        "jovy",
        "Regenerate files and install/build as needed.",
        aliases=("apply",),
    ),
    DashboardCommandSpec(
        "build",
        "jovy",
        "Build the project overlay image.",
        usage="build [--pull] [--no-cache] [--verbose]",
        aliases=("b", "rebuild"),
    ),
    DashboardCommandSpec(
        "up",
        "jovy",
        "Start Jupyter in the background.",
        usage="up [--no-build]",
        aliases=("start", "u"),
    ),
    DashboardCommandSpec(
        "down",
        "jovy",
        "Stop the background environment.",
        usage="down [--timeout SEC]",
        aliases=("stop", "d"),
    ),
    DashboardCommandSpec(
        "restart",
        "jovy",
        "Restart the background environment.",
        aliases=("r",),
    ),
    DashboardCommandSpec(
        "shell",
        "jovy",
        "Open a shell in the container, or run a shell command.",
        usage="shell OR shell <command...>",
        aliases=("sh",),
        suspend_app=True,
        refresh_logs_after=False,
    ),
    DashboardCommandSpec(
        "exec",
        "jovy",
        "Run a command in the container.",
        usage="exec <command...>",
        aliases=("x",),
    ),
    DashboardCommandSpec(
        "status",
        "jovy",
        "Show environment status.",
        aliases=("s", "ps"),
    ),
    DashboardCommandSpec(
        "config",
        "jovy",
        "Open the config editor screen.",
        aliases=("settings", "c"),
        run_in_worker=False,
        opens_screen=True,
        refresh_logs_after=True,
    ),
    DashboardCommandSpec(
        "clean",
        "jovy",
        "Remove generated files and build state.",
        aliases=("reset-build",),
    ),
    DashboardCommandSpec(
        "destroy",
        "jovy",
        "Use the CLI for destructive cleanup.",
        available_in_dashboard=False,
        blocked_hint="Destroy is destructive. Run jovy destroy from your shell so the confirmation prompt is visible.",
        refresh_logs_after=True,
    ),
    DashboardCommandSpec(
        "run",
        "jovy",
        "Not available in dashboard.",
        available_in_dashboard=False,
        blocked_hint="The run command is not available inside the dashboard. Use up, or run jovy run from your shell.",
    ),
    DashboardCommandSpec(
        "logs",
        "jovy",
        "Not available in dashboard.",
        available_in_dashboard=False,
        blocked_hint="The logs command is not available inside the dashboard. Use jovy logs from your shell.",
    ),
    DashboardCommandSpec(
        "sync",
        "jovy",
        "Legacy alias for install.",
        available_in_dashboard=False,
        blocked_hint="No primary command named sync. Use: install",
    ),
)

COMMAND_BY_NAME: dict[str, DashboardCommandSpec] = {}
for _spec in COMMAND_SPECS:
    COMMAND_BY_NAME[_spec.name] = _spec
    for _alias in _spec.aliases:
        COMMAND_BY_NAME[_alias] = _spec

LOCAL_COMMANDS = {spec.name for spec in COMMAND_SPECS if spec.category == "local"}
JOVY_COMMANDS = {spec.name for spec in COMMAND_SPECS if spec.category == "jovy"}


@dataclass(frozen=True)
class ParsedTuiCommand:
    """Parsed dashboard command input."""

    kind: TuiCommandKind
    name: str
    args: list[str]
    raw: str
    message: str | None = None
    spec: DashboardCommandSpec | None = None


def parse_tui_command(raw: str) -> ParsedTuiCommand:
    """Parse dashboard input into a command shape."""
    stripped = raw.strip()
    if not stripped:
        return ParsedTuiCommand(TuiCommandKind.EMPTY, "", [], raw)
    if stripped.startswith("!"):
        host_command = stripped[1:].strip()
        if not host_command:
            return ParsedTuiCommand(
                TuiCommandKind.UNKNOWN,
                "!",
                [],
                raw,
                "Pass a host command after !, for example: !pwd",
            )
        return ParsedTuiCommand(
            TuiCommandKind.HOST,
            "!",
            shlex.split(host_command),
            raw,
        )
    try:
        parts = shlex.split(stripped)
    except ValueError as exc:
        return ParsedTuiCommand(TuiCommandKind.UNKNOWN, stripped, [], raw, str(exc))
    if not parts:
        return ParsedTuiCommand(TuiCommandKind.EMPTY, "", [], raw)
    name = parts[0].strip()
    args = parts[1:]
    spec = COMMAND_BY_NAME.get(name)
    if spec is None:
        return ParsedTuiCommand(
            TuiCommandKind.UNKNOWN,
            name,
            args,
            raw,
            unknown_command_message(name),
        )
    if not spec.available_in_dashboard:
        return ParsedTuiCommand(
            TuiCommandKind.BLOCKED,
            spec.name,
            args,
            raw,
            spec.blocked_hint,
            spec=spec,
        )
    kind = TuiCommandKind.LOCAL if spec.category == "local" else TuiCommandKind.JOVY
    return ParsedTuiCommand(kind, spec.name, args, raw, spec=spec)


def unknown_command_message(name: str) -> str:
    """Return a helpful message for an unknown dashboard command."""
    suggestion = suggest_command(name)
    if suggestion:
        return f"Unknown command: {name}\nDid you mean: {suggestion}?"
    return f"Unknown command: {name}"


def suggest_command(name: str) -> str | None:
    """Suggest the closest supported dashboard command."""
    candidates = sorted(COMMAND_BY_NAME)
    matches = get_close_matches(name, candidates, n=1, cutoff=0.5)
    return matches[0] if matches else None
