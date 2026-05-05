"""Interactive editor for core JovyKit configuration settings."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import tomlkit
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
    Switch,
    TextArea,
)

from jovykit import commands
from jovykit.config import JovyConfig, JovyKitError, load_config
from jovykit.images import IMAGE_LEVELS

GPU_CHOICES = ("auto", "none", "all")
LOG_LEVEL_CHOICES = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
RESTART_POLICY_CHOICES = ("no", "always", "unless-stopped", "on-failure")
WORKSPACE_MODE_CHOICES = ("bind", "sync")
CUSTOM_IMAGE_VALUE = "__custom__"


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


def run_config_editor(*, env: Path | None = None) -> str | None:
    """Run the interactive config editor."""
    return ConfigEditorApp(env=env).run()


class ConfigEditorApp(App[str | None]):
    """Textual app for editing core ``jovy.toml`` settings."""

    CSS = """
    Screen {
        background: #101418;
        color: #e8eef2;
    }

    #editor {
        padding: 1 2;
    }

    .section {
        border: round #3b5666;
        padding: 1 2;
        margin-bottom: 1;
    }

    .field {
        height: auto;
        margin-bottom: 1;
    }

    .field Label {
        width: 24;
        padding-top: 1;
    }

    .field Input, .field Select {
        width: 1fr;
    }

    TextArea {
        height: 6;
        border: tall #4f7890;
    }

    #message {
        min-height: 2;
        color: #f2cf65;
        margin-bottom: 1;
    }

    #actions {
        height: auto;
    }

    Button {
        margin-right: 1;
    }
    """

    BINDINGS = [
        ("ctrl+s", "save_only", "Save"),
        ("ctrl+a", "apply_now", "Apply"),
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, *, env: Path | None = None) -> None:
        super().__init__()
        self.env = env
        self.config: JovyConfig | None = None

    def compose(self) -> ComposeResult:
        """Compose the editor layout."""
        self.config = commands.load_env(self.env)
        values = values_from_config(self.config)
        image_value, custom_image = _image_select_state(values.base_image)
        self.title = "JovyKit Config"
        yield Header()
        with VerticalScroll(id="editor"):
            yield Static("", id="message")
            with Vertical(classes="section"):
                yield Label("Project")
                yield _input_row("Project name", "project_name", values.project_name)
                yield _input_row("Workdir", "workdir", values.workdir)
            with Vertical(classes="section"):
                yield Label("Image")
                yield _select_row(
                    "Base image", "base_image", _image_options(), image_value
                )
                yield _input_row("Custom image ref", "custom_base_image", custom_image)
                yield _input_row("Image name", "image_name", values.image_name)
                yield _input_row("Image tag", "image_tag", values.image_tag)
            with Vertical(classes="section"):
                yield Label("Runtime")
                yield _input_row("Port", "port", str(values.port), input_type="integer")
                yield _select_row(
                    "GPU mode", "gpus", _choice_options(GPU_CHOICES), values.gpus
                )
                yield _select_row(
                    "Restart policy",
                    "restart_policy",
                    _choice_options(RESTART_POLICY_CHOICES),
                    values.restart_policy,
                )
            with Vertical(classes="section"):
                yield Label("Jupyter")
                yield _input_row("Token", "jupyter_token", values.jupyter_token)
                yield _select_row(
                    "Log level",
                    "jupyter_log_level",
                    _choice_options(LOG_LEVEL_CHOICES),
                    values.jupyter_log_level,
                )
                yield _switch_row("Lab", "jupyter_lab", values.jupyter_lab)
            with Vertical(classes="section"):
                yield Label("Mounts and Watch")
                yield _input_row("Work mount", "work_mount", values.work_mount)
                yield _switch_row("Watch", "watch_enabled", values.watch_enabled)
                yield _select_row(
                    "Workspace mode",
                    "watch_workspace_mode",
                    _choice_options(WORKSPACE_MODE_CHOICES),
                    values.watch_workspace_mode,
                )
            with Vertical(classes="section"):
                yield Label("Packages")
                yield TextArea(
                    format_list_lines(values.python_packages),
                    id="python_packages",
                    show_line_numbers=True,
                    placeholder="numpy\npandas",
                )
            with Vertical(classes="section"):
                yield Label("Runtime env")
                yield TextArea(
                    format_mapping_lines(values.runtime_env),
                    id="runtime_env",
                    show_line_numbers=True,
                    placeholder="KEY=value",
                )
            with Vertical(classes="section"):
                yield Label("Runtime volumes")
                yield TextArea(
                    format_mapping_lines(values.runtime_volumes),
                    id="runtime_volumes",
                    show_line_numbers=True,
                    placeholder="./data=/data",
                )
            with Horizontal(id="actions"):
                yield Button("Save only", id="save_only", variant="primary")
                yield Button("Apply now", id="apply_now", variant="success")
                yield Button("Cancel", id="cancel")
        yield Footer()

    @on(Button.Pressed, "#save_only")
    def on_save_only(self) -> None:
        """Save without applying."""
        self._save(apply_now=False)

    @on(Button.Pressed, "#apply_now")
    def on_apply_now(self) -> None:
        """Save and apply immediately."""
        self._save(apply_now=True)

    @on(Button.Pressed, "#cancel")
    def on_cancel_pressed(self) -> None:
        """Exit without saving."""
        self.exit("cancelled")

    def action_save_only(self) -> None:
        """Keyboard shortcut for save-only."""
        self._save(apply_now=False)

    def action_apply_now(self) -> None:
        """Keyboard shortcut for apply-now."""
        self._save(apply_now=True)

    def action_cancel(self) -> None:
        """Keyboard shortcut for cancel."""
        self.exit("cancelled")

    def _save(self, *, apply_now: bool) -> None:
        if self.config is None:
            self.config = commands.load_env(self.env)
        try:
            save_config_values(
                self.config,
                self._values_from_widgets(),
                apply_now=apply_now,
                emit=self._show_message,
            )
        except Exception as exc:
            self._show_message(f"Error: {exc}")
            return
        self.exit("applied" if apply_now else "saved")

    def _values_from_widgets(self) -> ConfigEditorValues:
        base_choice = str(self.query_one("#base_image", Select).value)
        custom_base = self.query_one("#custom_base_image", Input).value.strip()
        base_image = custom_base if base_choice == CUSTOM_IMAGE_VALUE else base_choice
        return ConfigEditorValues(
            project_name=self.query_one("#project_name", Input).value.strip(),
            workdir=self.query_one("#workdir", Input).value.strip(),
            base_image=base_image,
            image_name=self.query_one("#image_name", Input).value.strip(),
            image_tag=self.query_one("#image_tag", Input).value.strip(),
            port=int(self.query_one("#port", Input).value),
            gpus=str(self.query_one("#gpus", Select).value),
            restart_policy=str(self.query_one("#restart_policy", Select).value),
            jupyter_token=self.query_one("#jupyter_token", Input).value,
            jupyter_log_level=str(self.query_one("#jupyter_log_level", Select).value),
            jupyter_lab=self.query_one("#jupyter_lab", Switch).value,
            work_mount=self.query_one("#work_mount", Input).value.strip(),
            watch_enabled=self.query_one("#watch_enabled", Switch).value,
            watch_workspace_mode=str(
                self.query_one("#watch_workspace_mode", Select).value
            ),
            python_packages=parse_list_lines(
                self.query_one("#python_packages", TextArea).text
            ),
            runtime_env=parse_mapping_lines(
                self.query_one("#runtime_env", TextArea).text,
                field_name="Runtime env",
            ),
            runtime_volumes=parse_mapping_lines(
                self.query_one("#runtime_volumes", TextArea).text,
                field_name="Runtime volumes",
            ),
        )

    def _show_message(self, message: str) -> None:
        self.query_one("#message", Static).update(message)


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


def _choice_options(values: tuple[str, ...]) -> list[tuple[str, str]]:
    return [(value, value) for value in values]


def _image_options() -> list[tuple[str, str]]:
    options = [(level, image) for level, image in IMAGE_LEVELS.items()]
    options.append(("Custom image ref", CUSTOM_IMAGE_VALUE))
    return options


def _image_select_state(base_image: str) -> tuple[str, str]:
    if base_image in IMAGE_LEVELS.values():
        return base_image, ""
    return CUSTOM_IMAGE_VALUE, base_image


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


def _input_row(
    label: str,
    field_id: str,
    value: str,
    *,
    input_type: Literal["integer", "number", "text"] = "text",
) -> Horizontal:
    return Horizontal(
        Label(label),
        Input(value=value, id=field_id, type=input_type),
        classes="field",
    )


def _select_row(
    label: str,
    field_id: str,
    options: list[tuple[str, str]],
    value: str,
) -> Horizontal:
    if value not in {option_value for _, option_value in options}:
        options = [*options, (value, value)]
    return Horizontal(
        Label(label),
        Select(options, id=field_id, value=value, allow_blank=False),
        classes="field",
    )


def _switch_row(label: str, field_id: str, value: bool) -> Horizontal:
    return Horizontal(Label(label), Switch(value=value, id=field_id), classes="field")
