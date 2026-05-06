"""Interactive editor for core JovyKit configuration settings."""

from __future__ import annotations

import sys
import tempfile
import termios
import tty
from io import StringIO
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Static
import tomlkit

from jovykit import commands
from jovykit.config import JovyConfig, JovyKitError, load_config
from jovykit.images import IMAGE_LEVELS

GPU_CHOICES = ("auto", "none", "all")
LOG_LEVEL_CHOICES = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
RESTART_POLICY_CHOICES = ("no", "always", "unless-stopped", "on-failure")
WORKSPACE_MODE_CHOICES = ("bind", "sync")

InputFunc = Callable[[str], str]
KeyFunc = Callable[[], str]
OutputFunc = Callable[[str], None]


@dataclass(frozen=True)
class ConfigEditorValues:
    """Editable core settings from ``jovy.toml``."""

    project_name: str
    workdir: str
    base_image: str
    image_name: str
    image_tag: str
    port: int
    gpus: str
    restart_policy: str
    jupyter_token: str
    jupyter_log_level: str
    jupyter_lab: bool
    work_mount: str
    watch_enabled: bool
    watch_workspace_mode: str
    python_packages: list[str]
    runtime_env: dict[str, str]
    runtime_volumes: dict[str, str]


@dataclass(frozen=True)
class ConfigEditResult:
    """Result of writing edited configuration."""

    config: JovyConfig
    build_state_cleared: bool


@dataclass(frozen=True)
class ConfigField:
    """A scalar setting edited by the keyboard config loop."""

    key: str
    label: str
    kind: str = "text"
    choices: tuple[str, ...] = ()


SCALAR_FIELDS = (
    ConfigField("project_name", "Project name"),
    ConfigField("workdir", "Workdir"),
    ConfigField("base_image", "Base image"),
    ConfigField("image_name", "Image name"),
    ConfigField("image_tag", "Image tag"),
    ConfigField("port", "Port", "number"),
    ConfigField("gpus", "GPU mode", "choice", GPU_CHOICES),
    ConfigField("restart_policy", "Restart policy", "choice", RESTART_POLICY_CHOICES),
    ConfigField("jupyter_token", "Jupyter token"),
    ConfigField("jupyter_log_level", "Jupyter log level", "choice", LOG_LEVEL_CHOICES),
    ConfigField("jupyter_lab", "JupyterLab enabled", "bool"),
    ConfigField("work_mount", "Container work mount"),
    ConfigField("watch_enabled", "Config watch enabled", "bool"),
    ConfigField(
        "watch_workspace_mode",
        "Watch workspace mode",
        "choice",
        WORKSPACE_MODE_CHOICES,
    ),
)
SCALAR_FIELD_MAP = {field.key: field for field in SCALAR_FIELDS}
EDITOR_FIELDS = (
    *SCALAR_FIELDS,
    ConfigField("runtime_env", "Runtime env", "mapping"),
    ConfigField("runtime_volumes", "Runtime volumes", "mapping"),
)


def values_from_config(config: JovyConfig) -> ConfigEditorValues:
    """Return editor values from a loaded config."""
    project_environment = _read_project_environment(config.config_path)
    return ConfigEditorValues(
        project_name=config.project_name,
        workdir=project_environment or config.project_root.name,
        base_image=config.base_image,
        image_name=config.image_name,
        image_tag=config.image_tag,
        port=config.port,
        gpus=config.gpus,
        restart_policy=config.restart_policy,
        jupyter_token=config.jupyter_token,
        jupyter_log_level=config.jupyter_log_level,
        jupyter_lab=config.jupyter_lab,
        work_mount=config.work_mount,
        watch_enabled=config.watch_enabled,
        watch_workspace_mode=config.watch_workspace_mode,
        python_packages=config.python_packages,
        runtime_env=config.runtime_env,
        runtime_volumes=config.runtime_volumes,
    )


def parse_list_lines(text: str) -> list[str]:
    """Parse one non-empty list item per line."""
    return [line.strip() for line in text.splitlines() if line.strip()]


def parse_mapping_lines(text: str, *, field_name: str) -> dict[str, str]:
    """Parse ``KEY=value`` lines into a string mapping."""
    parsed: dict[str, str] = {}
    for index, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if "=" not in line:
            raise JovyKitError(f"{field_name} line {index} must use key=value syntax.")
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            raise JovyKitError(f"{field_name} line {index} has an empty key.")
        parsed[key] = value.strip()
    return parsed


def format_list_lines(values: list[str]) -> str:
    """Format a list for line-based editing."""
    return "\n".join(values)


def format_mapping_lines(values: dict[str, str]) -> str:
    """Format a mapping for line-based editing."""
    return "\n".join(f"{key}={value}" for key, value in values.items())


def save_config_values(
    config: JovyConfig,
    values: ConfigEditorValues,
    *,
    apply_now: bool,
    emit: commands.Emitter = commands.noop_emit,
) -> ConfigEditResult:
    """Save edited values and optionally apply them immediately."""
    _validate_values(values)
    original = config.config_path.read_text(encoding="utf-8")
    data = tomlkit.parse(original)
    _apply_values(data, values)
    rendered = tomlkit.dumps(data)
    _validate_rendered_config(config.env_dir, rendered)

    build_affecting_changed = _build_affecting_changed(config, values)
    config.config_path.write_text(rendered, encoding="utf-8")
    saved_config = load_config(config.env_dir)
    if build_affecting_changed:
        commands.clear_build_state(saved_config.env_dir)

    if apply_now:
        commands.install(saved_config, emit=emit, stream=True)
    elif build_affecting_changed:
        emit(
            "Saved jovy.toml. Run jovy install, jovy run, or jovy up to apply changes."
        )
    else:
        emit("Saved jovy.toml.")

    return ConfigEditResult(
        config=saved_config,
        build_state_cleared=build_affecting_changed,
    )


def run_config_editor(
    *,
    env: Path | None = None,
    input_func: InputFunc = input,
    key_func: KeyFunc | None = None,
    output: OutputFunc = print,
) -> str | None:
    """Run the keyboard-driven config editor."""
    if input_func is input and key_func is None and output is print:
        return run_textual_config_editor(env=env)
    return run_keyboard_config_editor(
        env=env,
        input_func=input_func,
        key_func=key_func,
        output=output,
    )


def run_textual_config_editor(*, env: Path | None = None) -> str | None:
    """Run the Textual config editor used by the CLI."""
    return JovyKitConfigEditor(env=env).run()


def run_keyboard_config_editor(
    *,
    env: Path | None = None,
    input_func: InputFunc = input,
    key_func: KeyFunc | None = None,
    output: OutputFunc = print,
) -> str | None:
    """Run the testable keyboard-driven config editor."""
    config = commands.load_env(env, emit=output)
    values = values_from_config(config)
    selected = 0
    status = "Use arrow keys. Press Enter to edit, s to save, a to apply, q to quit."
    key_reader = key_func or _read_key
    while True:
        _render_editor(values, selected, status, output)
        key = key_reader()
        try:
            if key == "up":
                selected = (selected - 1) % len(EDITOR_FIELDS)
            elif key == "down":
                selected = (selected + 1) % len(EDITOR_FIELDS)
            elif key in {"left", "right"}:
                values = _cycle_field(values, EDITOR_FIELDS[selected], key)
                status = f"Updated {EDITOR_FIELDS[selected].key}."
            elif key == "enter":
                values = _edit_field(
                    values,
                    EDITOR_FIELDS[selected],
                    input_func=input_func,
                    output=output,
                )
                status = f"Updated {EDITOR_FIELDS[selected].key}."
            elif key == "s":
                save_config_values(config, values, apply_now=False, emit=output)
                return "saved"
            elif key == "a":
                save_config_values(config, values, apply_now=True, emit=output)
                return "applied"
            elif key in {"q", "escape"}:
                output("Cancelled.")
                return "cancelled"
            else:
                status = "Use up/down, left/right, Enter, s, a, or q."
        except JovyKitError as exc:
            status = f"Error: {exc}"


class JovyKitConfigEditorScreen(Screen[str | None]):
    """Textual screen for core JovyKit configuration."""

    CSS = """
    Screen {
        background: #f8f8f8;
        color: #1f1f1f;
    }

    Screen:dark {
        background: #101418;
        color: #e8eef2;
    }

    #root {
        height: 100%;
        padding: 1;
    }

    #fields {
        height: 1fr;
        border: round #c0c0c0;
        padding: 0 1;
        background: #ffffff;
        color: #1f1f1f;
        margin-bottom: 1;
    }

    Screen:dark #fields {
        border: round #3b5666;
        background: #0b0f12;
        color: #e8eef2;
    }

    """

    BINDINGS = [
        ("q", "cancel", "Quit"),
        ("escape", "cancel", "Cancel"),
        ("up", "previous_field", "Previous"),
        ("down", "next_field", "Next"),
        ("left", "cycle_left", "Cycle left"),
        ("right", "cycle_right", "Cycle right"),
        ("enter", "edit_selected", "Edit"),
        ("w", "save", "Save"),
        ("a", "apply", "Apply"),
    ]

    def __init__(self, *, env: Path | None = None) -> None:
        super().__init__()
        self.env = env
        self.config: JovyConfig | None = None
        self.values: ConfigEditorValues | None = None
        self.editing_field: ConfigField | None = None
        self.choosing_field: ConfigField | None = None
        self.editing_value = ""
        self.editing_cursor = 0
        self.dirty = False
        self.discard_prompt = False
        self.selected = 0
        self.status = "Edit the selected setting, or use arrow keys to move."

    def compose(self) -> ComposeResult:
        """Compose the editor layout."""
        with Vertical(id="root"):
            yield Static(id="fields")

    def on_mount(self) -> None:
        """Load config and initialize the editor."""
        self.title = "JovyKit Config"
        try:
            self.config = commands.load_env(self.env)
            self.values = values_from_config(self.config)
        except JovyKitError as exc:
            self.status = f"Error: {exc}"
            self._append(f"[bold red][Error][/bold red] {_escape_markup(str(exc))}")
        self._refresh()

    def on_key(self, event: Key) -> None:
        """Handle navigation keys even when no field owns focus."""
        if self.editing_field is not None:
            event.prevent_default()
            event.stop()
            self._handle_inline_edit_key(event)
            return
        if self.choosing_field is not None:
            actions = {
                "up": self.action_cycle_left,
                "left": self.action_cycle_left,
                "down": self.action_cycle_right,
                "right": self.action_cycle_right,
                "enter": self.action_edit_selected,
            }
            action = actions.get(event.key)
            if action is None:
                return
            event.prevent_default()
            event.stop()
            action()
            return
        actions = {
            "up": self.action_previous_field,
            "down": self.action_next_field,
            "enter": self.action_edit_selected,
        }
        action = actions.get(event.key)
        if action is None:
            return
        event.prevent_default()
        event.stop()
        action()

    def action_previous_field(self) -> None:
        """Move to the previous editable field."""
        if self.values is None:
            return
        if self.choosing_field is not None:
            self._cycle_selected("left")
            return
        self._cancel_inline_edit()
        self.selected = (self.selected - 1) % len(EDITOR_FIELDS)
        self.status = "Edit the selected setting, or use arrow keys to move."
        self._refresh()

    def action_next_field(self) -> None:
        """Move to the next editable field."""
        if self.values is None:
            return
        if self.choosing_field is not None:
            self._cycle_selected("right")
            return
        self._cancel_inline_edit()
        self.selected = (self.selected + 1) % len(EDITOR_FIELDS)
        self.status = "Edit the selected setting, or use arrow keys to move."
        self._refresh()

    def action_cycle_left(self) -> None:
        """Cycle the selected choice backward."""
        self._cycle_selected("left")

    def action_cycle_right(self) -> None:
        """Cycle the selected choice forward."""
        self._cycle_selected("right")

    def action_edit_selected(self) -> None:
        """Open a prompt for typed fields."""
        if self.values is None:
            return
        if self.choosing_field is not None:
            self.status = f"Updated {self.choosing_field.label}."
            self.choosing_field = None
            self._refresh()
            return
        field = EDITOR_FIELDS[self.selected]
        if field.kind in {"bool", "choice"}:
            self.choosing_field = field
            self.status = (
                f"Changing {field.label}. Use left/right or up/down, Enter to choose."
            )
            self._refresh()
            return
        current = _format_field_value(self.values, field)
        self.editing_field = field
        self.editing_value = "" if current == "-" else current
        self.editing_cursor = len(self.editing_value)
        self.status = f"Editing {field.label}. Type value, Enter to choose."
        self._refresh()

    def action_save(self) -> None:
        """Save edited values without closing the editor."""
        self._save(apply_now=False, close=False)

    def action_apply(self) -> None:
        """Save, apply edited values, and exit."""
        self._save(apply_now=True, close=True)

    def action_cancel(self) -> None:
        """Cancel editing."""
        if self.editing_field is not None:
            self._cancel_inline_edit()
            self.status = "Edit cancelled."
            self._refresh()
            return
        if self.choosing_field is not None:
            self.choosing_field = None
            self.status = "Edit cancelled."
            self._refresh()
            return
        if self.dirty and not self.discard_prompt:
            self.discard_prompt = True
            self.status = (
                "Unsaved changes. Press w to save, a to apply, or q again to discard."
            )
            self._refresh()
            return
        self.dismiss("cancelled")

    def _cycle_selected(self, direction: str) -> None:
        if self.values is None:
            return
        field = self.choosing_field
        if field is None:
            self.status = "Press Enter to change this setting."
            self._refresh()
            return
        try:
            self.values = _cycle_field(self.values, field, direction)
            self.status = (
                f"Changing {field.label}: {_format_field_value(self.values, field)}. "
                "Press Enter to choose."
            )
            self.dirty = True
            self.discard_prompt = False
            self._append(
                f"[cyan][JovyKit][/cyan] Updated {field.label}: "
                f"{_escape_markup(_format_field_value(self.values, field))}"
            )
        except JovyKitError as exc:
            self.status = f"Error: {exc}"
            self._append(f"[bold red][Error][/bold red] {_escape_markup(str(exc))}")
        self._refresh()

    def _save(self, *, apply_now: bool, close: bool = True) -> None:
        if self.config is None or self.values is None:
            return
        try:
            save_config_values(
                self.config,
                self.values,
                apply_now=apply_now,
                emit=lambda line: self._append(_escape_markup(line)),
            )
        except JovyKitError as exc:
            self.status = f"Error: {exc}"
            self._append(f"[bold red][Error][/bold red] {_escape_markup(str(exc))}")
            self._refresh()
            return
        self.dirty = False
        self.discard_prompt = False
        self.status = "Saved." if not apply_now else "Applied."
        self._refresh()
        if close:
            self.dismiss("applied" if apply_now else "saved")

    def _refresh(self) -> None:
        self.query_one("#fields", Static).update(
            _render_textual_fields(
                self.values,
                self.selected,
                self.status,
                dirty=self.dirty,
                choosing_key=self.choosing_field.key if self.choosing_field else None,
                editing_key=self.editing_field.key if self.editing_field else None,
                editing_value=self.editing_value,
                editing_cursor=self.editing_cursor,
            )
        )

    def _append(self, line: str) -> None:
        return None

    def _apply_prompt_value(self, raw: str | None) -> None:
        if raw is None or self.values is None or self.editing_field is None:
            return
        field = self.editing_field
        try:
            self.values = _set_textual_field_value(self.values, field, raw.strip())
            self.status = f"Updated {field.label}."
            self.dirty = True
            self.discard_prompt = False
        except JovyKitError as exc:
            self.status = f"Error: {exc}"
        self._cancel_inline_edit()
        self._refresh()

    def _handle_inline_edit_key(self, event: Key) -> None:
        if event.key == "enter":
            self._apply_prompt_value(self.editing_value)
            return
        if event.key == "escape":
            self._cancel_inline_edit()
            self.status = "Edit cancelled."
            self._refresh()
            return
        if event.key == "left":
            self.editing_cursor = max(0, self.editing_cursor - 1)
            self._refresh()
            return
        if event.key == "right":
            self.editing_cursor = min(len(self.editing_value), self.editing_cursor + 1)
            self._refresh()
            return
        if event.key == "home":
            self.editing_cursor = 0
            self._refresh()
            return
        if event.key == "end":
            self.editing_cursor = len(self.editing_value)
            self._refresh()
            return
        if event.key == "backspace":
            if self.editing_cursor > 0:
                self.editing_value = (
                    self.editing_value[: self.editing_cursor - 1]
                    + self.editing_value[self.editing_cursor :]
                )
                self.editing_cursor -= 1
            self._refresh()
            return
        if event.key == "delete":
            if self.editing_cursor < len(self.editing_value):
                self.editing_value = (
                    self.editing_value[: self.editing_cursor]
                    + self.editing_value[self.editing_cursor + 1 :]
                )
            self._refresh()
            return
        character = getattr(event, "character", None)
        if character:
            self.editing_value = (
                self.editing_value[: self.editing_cursor]
                + character
                + self.editing_value[self.editing_cursor :]
            )
            self.editing_cursor += len(character)
            self.dirty = True
            self.discard_prompt = False
            self._refresh()

    def _cancel_inline_edit(self) -> None:
        self.editing_field = None
        self.choosing_field = None
        self.editing_value = ""
        self.editing_cursor = 0
        self.discard_prompt = False


class JovyKitConfigEditor(App[str | None]):
    """Standalone Textual app for core JovyKit configuration."""

    CSS = JovyKitConfigEditorScreen.CSS

    def __init__(self, *, env: Path | None = None) -> None:
        super().__init__()
        self.env = env

    def on_mount(self) -> None:
        """Open the config editor screen."""
        self.push_screen(JovyKitConfigEditorScreen(env=self.env), self.exit)


def _render_textual_fields(
    values: ConfigEditorValues | None,
    selected: int,
    status: str,
    dirty: bool = False,
    choosing_key: str | None = None,
    editing_key: str | None = None,
    editing_value: str = "",
    editing_cursor: int = 0,
) -> Panel:
    table = Table.grid(expand=True)
    table.add_column(width=2, no_wrap=True)
    table.add_column(ratio=1)
    table.add_column(ratio=2)
    if values is None:
        table.add_row(
            Text("!", style="bold red"),
            Text("Config"),
            Text(status),
        )
    else:
        for index, field in enumerate(EDITOR_FIELDS):
            is_selected = index == selected
            is_choosing = field.key == choosing_key
            is_editing = field.key == editing_key
            value = (
                _render_inline_edit_value(editing_value, editing_cursor)
                if is_editing
                else Text(_format_field_value(values, field))
            )
            if is_editing:
                value.stylize("bold white")
            else:
                value.stylize(
                    "bold yellow"
                    if is_choosing
                    else "bold white" if is_selected else "bright_black"
                )
            table.add_row(
                Text(
                    (
                        "*"
                        if is_choosing
                        else "|" if is_editing else ">" if is_selected else " "
                    ),
                    style=(
                        "bold yellow"
                        if is_choosing
                        else "bold white" if is_editing else "bold cyan"
                    ),
                ),
                Text(
                    field.label,
                    style=(
                        "bold yellow"
                        if is_choosing
                        else (
                            "bold white"
                            if is_editing
                            else "bold cyan" if is_selected else "white"
                        )
                    ),
                ),
                value,
            )

    body = Table.grid(expand=True)
    body.add_column(ratio=1)
    body.add_row(table)
    body.add_row("")
    body.add_row(
        Text(status, style="bold red" if status.startswith("Error:") else "cyan")
    )
    body.add_row("")
    body.add_row(
        Text(
            "q quit | w save | a apply | arrows move | Enter edit",
            style="dim #666666" if not dirty else "bold #f37726",
        )
    )
    return Panel(
        body, title="JovyKit config", border_style="#6c8ebf", style="on #ffffff"
    )


def _render_inline_edit_value(value: str, cursor: int) -> Text:
    cursor = max(0, min(cursor, len(value)))
    text = Text()
    text.append(value[:cursor])
    if cursor < len(value):
        text.append(value[cursor], style="reverse")
        text.append(value[cursor + 1 :])
    else:
        text.append(" ", style="reverse")
    return text


def _set_textual_field_value(
    values: ConfigEditorValues,
    field: ConfigField,
    raw: str,
) -> ConfigEditorValues:
    if field.kind == "bool":
        raise JovyKitError("Use left/right arrows to toggle this setting.")
    if field.kind == "choice":
        raise JovyKitError("Use left/right arrows to choose this setting.")
    if field.kind == "list":
        return _replace_editor_value(values, field.key, _parse_inline_list(raw))
    if field.kind == "mapping":
        return _replace_editor_value(
            values,
            field.key,
            _parse_inline_mapping(raw, field.label),
        )
    if not raw:
        return values
    return _set_scalar_value(values, field.key, raw)


def _field_placeholder(values: ConfigEditorValues, field: ConfigField) -> str:
    current = _format_field_value(values, field)
    if field.kind == "choice":
        return f"{field.label}: {current} (use left/right)"
    if field.kind == "bool":
        return f"{field.label}: {current} (use left/right)"
    if field.kind == "list":
        return f"{field.label}: comma-separated packages"
    if field.kind == "mapping":
        return f"{field.label}: comma-separated KEY=VALUE entries"
    return f"{field.label}: {current}"


def _status_markup(status: str) -> str:
    escaped = _escape_markup(status)
    if status.startswith("Error:"):
        return f"[bold red]{escaped}[/bold red]"
    return f"[cyan]{escaped}[/cyan]"


def _escape_markup(value: str) -> str:
    return value.replace("[", "\\[").replace("]", "\\]")


def _render_editor(
    values: ConfigEditorValues,
    selected: int,
    status: str,
    output: OutputFunc,
) -> None:
    buffer = StringIO()
    console = Console(
        file=buffer,
        force_terminal=True,
        color_system="truecolor",
        width=96,
        legacy_windows=False,
    )
    console.print("\x1b[2J\x1b[H", end="")

    fields = Table.grid(expand=True)
    fields.add_column(width=2)
    fields.add_column(width=24)
    fields.add_column(ratio=1)
    for index, field in enumerate(EDITOR_FIELDS):
        is_selected = index == selected
        marker = ">" if is_selected else " "
        label_style = "bold cyan" if is_selected else "white"
        value_style = "bold white" if is_selected else "bright_black"
        fields.add_row(
            Text(marker, style="bold cyan" if is_selected else "dim"),
            Text(field.label, style=label_style),
            Text(_format_field_value(values, field), style=value_style),
        )

    hint = Text(
        "Up/down move | left/right cycle | Enter edit | s save | a apply | q quit",
        style="dim",
    )
    status_style = "bold red" if status.startswith("Error:") else "cyan"
    body = Group(
        Text("JovyKit config", style="bold cyan"),
        hint,
        Text(""),
        fields,
        Text(""),
        Text(status, style=status_style),
    )
    console.print(
        Panel(
            body,
            title="JovyKit",
            border_style="bright_blue",
            padding=(1, 2),
        )
    )
    output(buffer.getvalue().rstrip())


def _format_field_value(values: ConfigEditorValues, field: ConfigField) -> str:
    value = getattr(values, field.key)
    if field.kind == "list":
        return ", ".join(value) if value else "-"
    if field.kind == "mapping":
        return _format_mapping(value)
    return _format_value(value)


def _cycle_field(
    values: ConfigEditorValues,
    field: ConfigField,
    direction: str,
) -> ConfigEditorValues:
    if field.kind == "bool":
        return _replace_editor_value(values, field.key, not getattr(values, field.key))
    if field.kind != "choice":
        raise JovyKitError("This field is edited with Enter.")
    current = str(getattr(values, field.key))
    try:
        index = field.choices.index(current)
    except ValueError:
        index = 0
    step = -1 if direction == "left" else 1
    return _replace_editor_value(
        values,
        field.key,
        field.choices[(index + step) % len(field.choices)],
    )


def _edit_field(
    values: ConfigEditorValues,
    field: ConfigField,
    *,
    input_func: InputFunc,
    output: OutputFunc,
) -> ConfigEditorValues:
    if field.kind == "choice":
        return _edit_choice(values, field, input_func=input_func, output=output)
    if field.kind == "bool":
        return _replace_editor_value(values, field.key, not getattr(values, field.key))
    if field.kind == "list":
        raw = _prompt(
            "Comma-separated packages",
            ", ".join(getattr(values, field.key)),
            input_func,
            output,
        )
        return _replace_editor_value(values, field.key, _parse_inline_list(raw))
    if field.kind == "mapping":
        raw = _prompt(
            "Comma-separated KEY=VALUE entries",
            _format_mapping(getattr(values, field.key)),
            input_func,
            output,
        )
        return _replace_editor_value(
            values,
            field.key,
            _parse_inline_mapping(raw, field.label),
        )
    raw = _prompt(
        field.label, _format_value(getattr(values, field.key)), input_func, output
    )
    return _set_scalar_value(values, field.key, raw)


def _edit_choice(
    values: ConfigEditorValues,
    field: ConfigField,
    *,
    input_func: InputFunc,
    output: OutputFunc,
) -> ConfigEditorValues:
    output("")
    output(f"{field.label} choices: {', '.join(field.choices)}")
    raw = _prompt(field.label, str(getattr(values, field.key)), input_func, output)
    return _set_scalar_value(values, field.key, raw)


def _prompt(
    label: str,
    current: str,
    input_func: InputFunc,
    output: OutputFunc,
) -> str:
    output("")
    output(f"{label} [{current}]:")
    raw = input_func("> ")
    return current if raw == "" else raw


def _read_key() -> str:
    with _raw_terminal(enabled=sys.stdin.isatty()):
        char = sys.stdin.read(1)
        if char == "\x1b":
            rest = sys.stdin.read(2)
            if rest == "[A":
                return "up"
            if rest == "[B":
                return "down"
            if rest == "[C":
                return "right"
            if rest == "[D":
                return "left"
            return "escape"
        if char in {"\r", "\n"}:
            return "enter"
        return char.lower() if char else "q"


@contextmanager
def _raw_terminal(*, enabled: bool) -> Any:
    if not enabled:
        yield
        return
    fd = sys.stdin.fileno()
    settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, settings)


def _format_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _format_mapping(values: dict[str, str]) -> str:
    if not values:
        return "-"
    return ", ".join(f"{key}={value}" for key, value in values.items())


def _set_scalar_value(
    values: ConfigEditorValues,
    key: str,
    raw_value: str,
) -> ConfigEditorValues:
    field = SCALAR_FIELD_MAP.get(key)
    if field is None:
        raise JovyKitError(f"Unknown field: {key}. Type list to see fields.")
    if key == "port":
        try:
            value: object = int(raw_value)
        except ValueError as exc:
            raise JovyKitError("Port must be an integer.") from exc
    elif key in {"jupyter_lab", "watch_enabled"}:
        value = _parse_bool(raw_value)
    elif key == "base_image":
        value = IMAGE_LEVELS.get(raw_value, raw_value)
    else:
        value = raw_value
    if field.choices and key not in {"jupyter_lab", "watch_enabled"}:
        _validate_choice(field.label, str(value), field.choices)
    return _replace_editor_value(values, key, value)


def _replace_editor_value(
    values: ConfigEditorValues,
    key: str,
    value: object,
) -> ConfigEditorValues:
    if key == "project_name":
        if not isinstance(value, str):
            raise JovyKitError("project_name must be a string.")
        return replace(values, project_name=value)
    if key == "workdir":
        if not isinstance(value, str):
            raise JovyKitError("workdir must be a string.")
        return replace(values, workdir=value)
    if key == "base_image":
        if not isinstance(value, str):
            raise JovyKitError("base_image must be a string.")
        return replace(values, base_image=value)
    if key == "image_name":
        if not isinstance(value, str):
            raise JovyKitError("image_name must be a string.")
        return replace(values, image_name=value)
    if key == "image_tag":
        if not isinstance(value, str):
            raise JovyKitError("image_tag must be a string.")
        return replace(values, image_tag=value)
    if key == "gpus":
        if not isinstance(value, str):
            raise JovyKitError("gpus must be a string.")
        return replace(values, gpus=value)
    if key == "restart_policy":
        if not isinstance(value, str):
            raise JovyKitError("restart_policy must be a string.")
        return replace(values, restart_policy=value)
    if key == "jupyter_token":
        if not isinstance(value, str):
            raise JovyKitError("jupyter_token must be a string.")
        return replace(values, jupyter_token=value)
    if key == "jupyter_log_level":
        if not isinstance(value, str):
            raise JovyKitError("jupyter_log_level must be a string.")
        return replace(values, jupyter_log_level=value)
    if key == "work_mount":
        if not isinstance(value, str):
            raise JovyKitError("work_mount must be a string.")
        return replace(values, work_mount=value)
    if key == "watch_workspace_mode":
        if not isinstance(value, str):
            raise JovyKitError("watch_workspace_mode must be a string.")
        return replace(values, watch_workspace_mode=value)
    if key == "port":
        if not isinstance(value, int):
            raise JovyKitError("port must be an integer.")
        return replace(values, port=value)
    if key == "jupyter_lab":
        if not isinstance(value, bool):
            raise JovyKitError("jupyter_lab must be a boolean.")
        return replace(values, jupyter_lab=value)
    if key == "watch_enabled":
        if not isinstance(value, bool):
            raise JovyKitError("watch_enabled must be a boolean.")
        return replace(values, watch_enabled=value)
    if key == "python_packages":
        if not isinstance(value, list):
            raise JovyKitError("python_packages must be a list.")
        return replace(values, python_packages=value)
    if key == "runtime_env":
        if not isinstance(value, dict):
            raise JovyKitError("runtime_env must be a mapping.")
        return replace(values, runtime_env=value)
    if key == "runtime_volumes":
        if not isinstance(value, dict):
            raise JovyKitError("runtime_volumes must be a mapping.")
        return replace(values, runtime_volumes=value)
    raise JovyKitError(f"Unknown field: {key}. Type list to see fields.")


def _parse_bool(raw_value: str) -> bool:
    normalized = raw_value.strip().lower()
    if normalized in {"1", "yes", "y", "true", "on"}:
        return True
    if normalized in {"0", "no", "n", "false", "off"}:
        return False
    raise JovyKitError("Boolean values must be true/false, yes/no, or on/off.")


def _parse_inline_list(raw_value: str) -> list[str]:
    if not raw_value.strip() or raw_value.strip() == "-":
        return []
    return [
        item.strip()
        for group in raw_value.split(",")
        for item in group.split()
        if item.strip()
    ]


def _parse_inline_mapping(raw_value: str, field_name: str) -> dict[str, str]:
    if not raw_value.strip() or raw_value.strip() == "-":
        return {}
    return parse_mapping_lines(
        "\n".join(part.strip() for part in raw_value.split(",") if part.strip()),
        field_name=field_name,
    )


def _validate_values(values: ConfigEditorValues) -> None:
    if not values.project_name:
        raise JovyKitError("Project name cannot be empty.")
    if not values.workdir:
        raise JovyKitError("Workdir cannot be empty.")
    if not values.base_image:
        raise JovyKitError("Base image cannot be empty.")
    if not values.image_name:
        raise JovyKitError("Image name cannot be empty.")
    if not values.image_tag:
        raise JovyKitError("Image tag cannot be empty.")
    if values.port < 1 or values.port > 65535:
        raise JovyKitError("Port must be between 1 and 65535.")
    _validate_choice("GPU mode", values.gpus, GPU_CHOICES)
    _validate_choice("Restart policy", values.restart_policy, RESTART_POLICY_CHOICES)
    _validate_choice("Jupyter log level", values.jupyter_log_level, LOG_LEVEL_CHOICES)
    _validate_choice(
        "Watch workspace mode",
        values.watch_workspace_mode,
        WORKSPACE_MODE_CHOICES,
    )
    if not values.work_mount.startswith("/"):
        raise JovyKitError("Work mount must be an absolute container path.")


def _validate_choice(name: str, value: str, choices: tuple[str, ...]) -> None:
    if value not in choices:
        raise JovyKitError(f"{name} must be one of: {', '.join(choices)}.")


def _apply_values(data: tomlkit.TOMLDocument, values: ConfigEditorValues) -> None:
    _table(data, "project")["name"] = values.project_name
    _table(data, "project")["workdir"] = values.workdir
    _table(data, "image")["base"] = values.base_image
    _table(data, "image")["name"] = values.image_name
    _table(data, "image")["tag"] = values.image_tag
    _table(data, "runtime")["port"] = values.port
    _table(data, "runtime")["gpus"] = values.gpus
    _table(data, "runtime")["restart"] = values.restart_policy
    runtime_env = _table(data, "runtime", "env")
    runtime_env.clear()
    runtime_env.update(values.runtime_env)
    runtime_volumes = _table(data, "runtime", "volumes")
    runtime_volumes.clear()
    runtime_volumes.update(values.runtime_volumes)
    _table(data, "jupyter")["token"] = values.jupyter_token
    _table(data, "jupyter")["log_level"] = values.jupyter_log_level
    _table(data, "jupyter")["lab"] = values.jupyter_lab
    _table(data, "mounts")["work"] = values.work_mount
    _table(data, "watch")["enabled"] = values.watch_enabled
    _table(data, "watch")["workspace_mode"] = values.watch_workspace_mode
    _table(data, "python")["packages"] = values.python_packages


def _validate_rendered_config(env_dir: Path, rendered: str) -> None:
    with tempfile.TemporaryDirectory(prefix="jovykit-config-") as temp_dir:
        root = Path(temp_dir)
        temp_env = root / env_dir.name
        temp_env.mkdir()
        (root / "jovy.toml").write_text(rendered, encoding="utf-8")
        load_config(temp_env)


def _build_affecting_changed(config: JovyConfig, values: ConfigEditorValues) -> bool:
    return (
        config.base_image != values.base_image
        or config.image_name != values.image_name
        or config.image_tag != values.image_tag
        or config.python_packages != values.python_packages
    )


def _table(data: Any, *path: str) -> Any:
    current = data
    for key in path:
        existing = current.get(key)
        if not isinstance(existing, tomlkit.items.Table):
            existing = tomlkit.table()
            current[key] = existing
        current = existing
    return current


def _read_project_environment(config_path: Path) -> str | None:
    try:
        data = tomlkit.parse(config_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    project = data.get("project", {})
    if not isinstance(project, dict):
        return None
    environment = project.get("workdir")
    return str(environment) if environment is not None else None
