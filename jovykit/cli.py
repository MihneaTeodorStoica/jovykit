"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from rich.console import Console
from rich.padding import Padding
from rich.table import Table
from rich.text import Text

from jovykit import __version__, commands
from jovykit.config import JovyKitError
from jovykit.images import DEFAULT_PYTHON_VERSION, IMAGE_LEVELS
from jovykit.paths import has_project_markers

console = Console()

COMPOSE_ALIASES: dict[str, str] = {
    name: name
    for name in (
        "up",
        "down",
        "start",
        "stop",
        "restart",
        "config",
        "logs",
        "build",
        "watch",
    )
}

HELP_USAGE = (
    "jovy",
    "jovy init [OPTIONS]",
    "jovy install-docker [--yes]",
    "jovy doctor [--fix] [--yes] [--security]",
    "jovy token rotate|show [OPTIONS]",
    "jovy COMMAND [ARGS...]",
)
HELP_SECTIONS = (
    (
        "Compose commands",
        (
            ("up [ARGS...]", "Create and start the Jupyter service."),
            ("down [ARGS...]", "Stop and remove compose resources."),
            ("start [ARGS...]", "Start existing containers."),
            ("stop [ARGS...]", "Stop running containers."),
            ("restart [ARGS...]", "Restart the service."),
            ("config [ARGS...]", "Render the compose config."),
            ("logs [ARGS...]", "Show service logs."),
            ("build [ARGS...]", "Build the local project image."),
            ("watch [ARGS...]", "Run compose watch."),
        ),
    ),
    (
        "Project commands",
        (
            ("init [OPTIONS]", "Write compose.yaml, Dockerfile, requirements.txt."),
            ("add PACKAGE [PACKAGE...]", "Add Python packages to requirements.txt."),
            ("remove PACKAGE [PACKAGE...]", "Remove Python packages."),
            ("upgrade [OPTIONS]", "Upgrade image level, Python, and project options."),
            ("status [OPTIONS]", "Show project status."),
            ("token rotate|show [OPTIONS]", "Rotate or show the local token."),
            ("shell [COMMAND...]", "Exec in the service."),
            ("run COMMAND [ARGS...]", "Run one command in a fresh service container."),
            ("open", "Open JupyterLab."),
            ("token [show|rotate]", "Show or rotate Jupyter token."),
            ("doctor [OPTIONS]", "Check Docker, compose, GPU, and project files."),
            ("install-docker [--yes]", "Print or run a Linux Docker install plan."),
        ),
    ),
    (
        "Escape hatch",
        (("compose COMMAND [ARGS...]", "Pass through to docker compose."),),
    ),
)
HELP_EXAMPLES = (
    "jovy up -d",
    "jovy build",
    "jovy watch",
    "jovy logs -f",
    "jovy shell",
    "jovy install-docker --dry-run",
)


def main(argv: list[str] | None = None) -> None:
    """Run the CLI."""
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        raise SystemExit(_main(args))
    except JovyKitError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise SystemExit(1) from exc


def _main(args: list[str]) -> int:
    if not args:
        if not has_project_markers():
            _init([])
            return 0
        _print_help()
        return 0
    command = args[0]
    if command in {"-h", "--help", "help"}:
        _print_help()
        return 0
    if command == "--version":
        console.print(__version__)
        return 0
    if command == "init":
        _init(args[1:])
        return 0
    if command == "add":
        _add(args[1:])
        return 0
    if command == "remove":
        _remove(args[1:])
        return 0
    if command == "upgrade":
        _upgrade(args[1:])
        return 0
    if command == "open":
        console.print(commands.open_browser())
        return 0
    if command == "doctor":
        _doctor(args[1:])
        return 0
    if command == "token":
        _token(args[1:])
        return 0
    if command == "install-docker":
        _install_docker(args[1:])
        return 0
    if command in COMPOSE_ALIASES:
        handler: Callable[[list[str]], int] = getattr(
            commands, COMPOSE_ALIASES[command]
        )
        return handler(args[1:])
    if command == "status":
        _status(args[1:])
        return 0
    if command == "shell":
        return commands.shell(args[1:])
    if command == "run":
        return commands.run(args[1:])
    if command == "compose":
        return commands.compose_passthrough(args[1:])
    console.print(f"[red]error:[/red] unknown command: {command}")
    _print_help()
    return 2


def _print_help() -> None:
    console.print(Text("JovyKit", style="bold #f37726"))
    console.print(Text("Compose-shaped Jupyter environments.", style="#9aa4b2"))
    console.print()

    _print_usage()
    for title, rows in HELP_SECTIONS:
        _print_command_section(title, rows)

    console.print(Text("Examples", style="bold #4fc3f7"))
    for example in HELP_EXAMPLES:
        console.print(Text(f"  {example}", style="#d6deeb"))


def _print_usage() -> None:
    console.print(Text("Usage", style="bold #4fc3f7"))
    for usage in HELP_USAGE:
        console.print(Text(f"  {usage}", style="#d6deeb"))
    console.print()


def _print_command_section(title: str, rows: tuple[tuple[str, str], ...]) -> None:
    console.print(Text(title, style="bold #4fc3f7"))
    table = Table.grid(padding=(0, 2))
    table.add_column("command", style="bold #8f79d6", no_wrap=False, overflow="fold")
    table.add_column("description", style="#d6deeb", no_wrap=False, overflow="fold")
    for command, description in rows:
        table.add_row(f"jovy {command}", description)
    console.print(Padding(table, (0, 0, 1, 0)))


def _init(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="jovy init")
    parser.add_argument("path", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument(
        "--image-level", "--level", choices=tuple(IMAGE_LEVELS), default="base"
    )
    parser.add_argument(
        "--python",
        "--python-version",
        dest="python_version",
        default=DEFAULT_PYTHON_VERSION,
    )
    parser.add_argument("--gpu", choices=tuple(commands.VALID_GPU), default=None)
    parser.add_argument("--port", default="8888")
    parser.add_argument("--token", default=None)
    parser.add_argument("--force", action="store_true")
    namespace = parser.parse_args(args)
    commands.init_project(
        namespace.path,
        level=namespace.image_level,
        python_version=namespace.python_version,
        gpu=namespace.gpu,
        port=namespace.port,
        token=namespace.token,
        force=namespace.force,
        emit=console.print,
    )


def _add(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="jovy add")
    parser.add_argument("--raw", action="store_true")
    parser.add_argument("--allow-unsafe-requirement", action="store_true")
    parser.add_argument("packages", nargs="*")
    namespace, remaining = parser.parse_known_args(args)
    if namespace.raw:
        namespace.allow_unsafe_requirement = True
    packages = [*namespace.packages, *remaining]
    if not packages:
        parser.error("the following arguments are required: PACKAGE [PACKAGE...]")
    commands.add_packages(
        packages,
        allow_unsafe_requirement=namespace.allow_unsafe_requirement,
        emit=console.print,
    )


def _remove(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="jovy remove")
    parser.add_argument("packages", nargs="+")
    namespace = parser.parse_args(args)
    commands.remove_packages(namespace.packages, emit=console.print)


def _upgrade(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="jovy upgrade")
    parser.add_argument(
        "--image-level", "--level", dest="image_level", choices=tuple(IMAGE_LEVELS)
    )
    parser.add_argument(
        "--python",
        "--python-version",
        dest="python_version",
    )
    parser.add_argument("--gpu", choices=tuple(commands.VALID_GPU))
    parser.add_argument("--port")
    parser.add_argument("--token")
    parser.add_argument("--dry-run", action="store_true")
    namespace = parser.parse_args(args)
    commands.upgrade_project(
        level=namespace.image_level,
        python_version=namespace.python_version,
        gpu=namespace.gpu,
        port=namespace.port,
        token=namespace.token,
        dry_run=namespace.dry_run,
        emit=console.print,
    )


def _install_docker(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="jovy install-docker")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--skip-hello-world", action="store_true")
    namespace = parser.parse_args(args)
    if namespace.dry_run and namespace.yes:
        parser.error("--dry-run cannot be combined with --yes")
    commands.install_docker(
        yes=namespace.yes,
        skip_hello_world=namespace.skip_hello_world,
        emit=console.print,
    )


def _status(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="jovy status")
    parser.add_argument("--json", action="store_true")
    namespace = parser.parse_args(args)
    console.print(commands.status(json_output=namespace.json))


def _doctor(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="jovy doctor")
    parser.add_argument("--fix", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--security", action="store_true")
    namespace = parser.parse_args(args)
    commands.doctor(
        fix=namespace.fix,
        yes=namespace.yes,
        security=namespace.security,
        emit=console.print,
    )


def _token(args: list[str]) -> None:
    if not args:
        raise JovyKitError("token requires a subcommand: rotate or show")
    subcommand = args[0]
    if subcommand == "rotate":
        parser = argparse.ArgumentParser(prog="jovy token rotate")
        parser.add_argument("--token", default=None)
        namespace = parser.parse_args(args[1:])
        commands.rotate_token(token=namespace.token, emit=console.print)
        return
    if subcommand == "show":
        parser = argparse.ArgumentParser(prog="jovy token show")
        parser.parse_args(args[1:])
        commands.show_token(emit=console.print)
        return
    raise JovyKitError(f"unknown token subcommand: {subcommand}")


if __name__ == "__main__":
    main()
