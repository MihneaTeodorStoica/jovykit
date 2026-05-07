from __future__ import annotations

from jovykit.tui_commands import COMMAND_SPECS, TuiCommandKind, parse_tui_command


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


def test_config_command_maps_to_jovy_command() -> None:
    parsed = parse_tui_command("config")

    assert parsed.kind is TuiCommandKind.JOVY
    assert parsed.name == "config"


def test_run_command_is_blocked_in_dashboard() -> None:
    parsed = parse_tui_command("run")

    assert parsed.kind is TuiCommandKind.BLOCKED
    assert parsed.name == "run"
    assert parsed.message is not None
    assert "not available inside the dashboard" in parsed.message


def test_logs_command_is_blocked_in_dashboard() -> None:
    parsed = parse_tui_command("logs")

    assert parsed.kind is TuiCommandKind.BLOCKED
    assert parsed.name == "logs"
    assert parsed.message is not None
    assert "not available inside the dashboard" in parsed.message


def test_destroy_command_is_blocked_in_dashboard() -> None:
    parsed = parse_tui_command("destroy")

    assert parsed.kind is TuiCommandKind.BLOCKED
    assert parsed.name == "destroy"
    assert parsed.message is not None
    assert "destructive" in parsed.message


def test_quit_and_exit_are_local_dashboard_commands() -> None:
    quit_parsed = parse_tui_command("quit")
    exit_parsed = parse_tui_command("exit")

    assert quit_parsed.kind is TuiCommandKind.LOCAL
    assert exit_parsed.kind is TuiCommandKind.LOCAL
    assert quit_parsed.name == "quit"
    assert exit_parsed.name == "quit"


def test_unknown_command_suggests_close_match() -> None:
    parsed = parse_tui_command("stats")

    assert parsed.kind is TuiCommandKind.UNKNOWN
    assert parsed.message == "Unknown command: stats\nDid you mean: status?"


def test_removed_lifecycle_commands_are_not_primary() -> None:
    start = parse_tui_command("start")
    stop = parse_tui_command("stop")
    assert start.kind is TuiCommandKind.JOVY
    assert stop.kind is TuiCommandKind.JOVY
    assert start.name == "up"
    assert stop.name == "down"
    assert (
        parse_tui_command("sync").message
        == "No primary command named sync. Use: install"
    )


def test_registry_commands_are_parseable_with_expected_kinds() -> None:
    for spec in COMMAND_SPECS:
        parsed = parse_tui_command(spec.name)
        if spec.available_in_dashboard:
            expected_kind = (
                TuiCommandKind.LOCAL
                if spec.category == "local"
                else TuiCommandKind.JOVY
            )
            assert parsed.kind is expected_kind
        else:
            assert parsed.kind is TuiCommandKind.BLOCKED
