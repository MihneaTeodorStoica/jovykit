from __future__ import annotations

from jovykit.tui_commands import TuiCommandKind, parse_tui_command


def test_plain_input_maps_to_jovy_command() -> None:
    parsed = parse_tui_command("add numpy pandas")

    assert parsed.kind is TuiCommandKind.JOVY
    assert parsed.name == "add"
    assert parsed.args == ["numpy", "pandas"]


def test_host_shell_command_uses_bang_prefix() -> None:
    parsed = parse_tui_command("!docker ps")

    assert parsed.kind is TuiCommandKind.HOST
    assert parsed.args == ["docker", "ps"]


def test_exec_command_keeps_container_command_args() -> None:
    parsed = parse_tui_command("exec python --version")

    assert parsed.kind is TuiCommandKind.JOVY
    assert parsed.name == "exec"
    assert parsed.args == ["python", "--version"]


def test_quit_and_exit_are_local_dashboard_commands() -> None:
    assert parse_tui_command("quit").kind is TuiCommandKind.LOCAL
    assert parse_tui_command("exit").kind is TuiCommandKind.LOCAL


def test_unknown_command_suggests_close_match() -> None:
    parsed = parse_tui_command("stats")

    assert parsed.kind is TuiCommandKind.UNKNOWN
    assert parsed.message == "Unknown command: stats\nDid you mean: status?"


def test_removed_lifecycle_commands_are_not_primary() -> None:
    assert (
        parse_tui_command("start").message == "No primary command named start. Use: up"
    )
    assert (
        parse_tui_command("stop").message == "No primary command named stop. Use: down"
    )
    assert (
        parse_tui_command("sync").message
        == "No primary command named sync. Use: install"
    )
