"""Small parser for commands entered in the JovyKit dashboard."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from difflib import get_close_matches
from enum import Enum


class TuiCommandKind(str, Enum):
    """Kinds of commands accepted by the dashboard input."""

    EMPTY = "empty"
    HOST = "host"
    JOVY = "jovy"
    LOCAL = "local"
    UNKNOWN = "unknown"


JOVY_COMMANDS = {
    "init",
    "add",
    "remove",
    "install",
    "build",
    "up",
    "down",
    "restart",
    "logs",
    "shell",
    "exec",
    "status",
    "config",
    "clean",
    "destroy",
}

LOCAL_COMMANDS = {"help", "clear", "open", "refresh", "quit", "exit", "theme"}
BLOCKED_COMMAND_HINTS = {
    "run": "The run command is not available inside the dashboard. Use up, or run jovy run from your shell.",
}
REMOVED_COMMAND_HINTS = {
    "start": "No primary command named start. Use: up",
    "stop": "No primary command named stop. Use: down",
    "sync": "No primary command named sync. Use: install",
}


@dataclass(frozen=True)
class ParsedTuiCommand:
    """Parsed dashboard command input."""

    kind: TuiCommandKind
    name: str
    args: list[str]
    raw: str
    message: str | None = None


def parse_tui_command(raw: str) -> ParsedTuiCommand:
    """Parse dashboard input into a command shape."""
    stripped = raw.strip()
    if not stripped:
        return ParsedTuiCommand(TuiCommandKind.EMPTY, "", [], raw)
    if stripped.startswith("/"):
        stripped = stripped[1:].strip()
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
    name = parts[0]
    args = parts[1:]
    if name in LOCAL_COMMANDS:
        return ParsedTuiCommand(TuiCommandKind.LOCAL, name, args, raw)
    if name in BLOCKED_COMMAND_HINTS:
        return ParsedTuiCommand(
            TuiCommandKind.UNKNOWN,
            name,
            args,
            raw,
            BLOCKED_COMMAND_HINTS[name],
        )
    if name in JOVY_COMMANDS:
        return ParsedTuiCommand(TuiCommandKind.JOVY, name, args, raw)
    return ParsedTuiCommand(
        TuiCommandKind.UNKNOWN,
        name,
        args,
        raw,
        unknown_command_message(name),
    )


def unknown_command_message(name: str) -> str:
    """Return a helpful message for an unknown dashboard command."""
    if name in REMOVED_COMMAND_HINTS:
        return REMOVED_COMMAND_HINTS[name]
    suggestion = suggest_command(name)
    if suggestion:
        return f"Unknown command: {name}\nDid you mean: {suggestion}?"
    return f"Unknown command: {name}"


def suggest_command(name: str) -> str | None:
    """Suggest the closest supported dashboard command."""
    candidates = sorted(JOVY_COMMANDS | LOCAL_COMMANDS)
    matches = get_close_matches(name, candidates, n=1, cutoff=0.5)
    return matches[0] if matches else None
