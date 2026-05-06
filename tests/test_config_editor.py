from __future__ import annotations

from typing import Any, cast

import pytest

from jovykit.config import JovyKitError, read_state, write_state
from jovykit.config_editor import (
    ConfigField,
    ConfigEditorValues,
    EDITOR_FIELDS,
    JovyKitConfigEditor,
    format_list_lines,
    format_mapping_lines,
    parse_list_lines,
    parse_mapping_lines,
    run_config_editor,
    save_config_values,
    values_from_config,
    _cycle_field,
    _edit_field,
    _field_placeholder,
    _parse_bool,
    _read_key,
    _replace_editor_value,
    _render_textual_fields,
    _set_scalar_value,
    _set_textual_field_value,
    _validate_values,
)


def test_save_config_values_preserves_advanced_toml_and_clears_build_state(
    create_project: Any,
) -> None:
    project = create_project(
        config_transform=lambda text: text.replace(
            'log_level = "ERROR"',
            'log_level = "ERROR"\ncommand = "start-notebook.py"',
        )
    )
    write_state(project.env_dir, {"build_signature": "old", "other": "kept"})
    values = values_from_config(project.config)
    edited = ConfigEditorValues(
        **{
            **values.__dict__,
            "port": 7777,
            "python_packages": ["numpy", "pandas"],
            "runtime_env": {"EXTRA_FLAG": "yes"},
            "runtime_volumes": {"./data": "/data"},
        }
    )
    messages: list[str] = []

    result = save_config_values(
        project.config,
        edited,
        apply_now=False,
        emit=messages.append,
    )

    config_text = (project.root / "jovy.toml").read_text(encoding="utf-8")
    assert 'command = "start-notebook.py"' in config_text
    assert "port = 7777" in config_text
    assert 'packages = ["numpy", "pandas"]' in config_text
    assert 'EXTRA_FLAG = "yes"' in config_text
    assert '"./data" = "/data"' in config_text
    assert read_state(project.env_dir) == {"other": "kept"}
    assert result.build_state_cleared is True
    assert "jovy install" in messages[-1]


def test_save_config_values_can_apply_immediately(
    monkeypatch: pytest.MonkeyPatch,
    create_project: Any,
) -> None:
    project = create_project()
    values = values_from_config(project.config)
    calls: list[str] = []

    monkeypatch.setattr(
        "jovykit.config_editor.commands.install",
        lambda config, **kwargs: calls.append(config.image_ref),
    )

    save_config_values(project.config, values, apply_now=True)

    assert calls == [project.config.image_ref]


def test_save_config_values_rejects_invalid_restricted_choice(
    create_project: Any,
) -> None:
    project = create_project()
    values = values_from_config(project.config)
    edited = ConfigEditorValues(**{**values.__dict__, "gpus": "sometimes"})

    with pytest.raises(JovyKitError, match="GPU mode"):
        save_config_values(project.config, edited, apply_now=False)


def test_parse_mapping_lines_requires_key_value_syntax() -> None:
    with pytest.raises(JovyKitError, match="key=value"):
        parse_mapping_lines("BROKEN", field_name="Runtime env")


def test_line_parsers_ignore_blanks_and_preserve_values() -> None:
    assert parse_list_lines("\n numpy \n\n pandas>=2 \n") == ["numpy", "pandas>=2"]
    assert parse_mapping_lines(
        "\n API_URL=https://example.invalid \n EMPTY= \n",
        field_name="Runtime env",
    ) == {"API_URL": "https://example.invalid", "EMPTY": ""}
    assert format_list_lines(["numpy", "pandas"]) == "numpy\npandas"
    assert format_mapping_lines({"A": "1", "B": "two"}) == "A=1\nB=two"


def test_parse_mapping_lines_requires_non_empty_key() -> None:
    with pytest.raises(JovyKitError, match="empty key"):
        parse_mapping_lines("=missing", field_name="Runtime env")


def test_run_config_editor_defaults_to_textual_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launched: list[object] = []

    def fake_run_textual_config_editor(**kwargs: object) -> str:
        launched.append(kwargs["env"])
        return "saved"

    monkeypatch.setattr(
        "jovykit.config_editor.run_textual_config_editor",
        fake_run_textual_config_editor,
    )

    assert run_config_editor(env=None) == "saved"
    assert launched == [None]


def test_keyboard_editor_updates_values_and_saves(create_project: Any) -> None:
    project = create_project()
    keys = iter(
        [
            *["down"] * 5,
            "enter",
            *["up"] * 3,
            "enter",
            *["down"] * 10,
            "right",
            *["down"] * 2,
            "enter",
            "down",
            "enter",
            "s",
        ]
    )
    inputs = iter(
        [
            "7777",
            "base",
            "API_URL=https://example.invalid",
            "./data=/data",
        ]
    )
    messages: list[str] = []

    result = run_config_editor(
        env=project.env_dir,
        input_func=lambda prompt: next(inputs),
        key_func=lambda: next(keys),
        output=messages.append,
    )

    config_text = (project.root / "jovy.toml").read_text(encoding="utf-8")
    assert result == "saved"
    assert "port = 7777" in config_text
    assert 'base = "ghcr.io/mihneateodorstoica/jovykit-base:latest"' in config_text
    assert "enabled = false" in config_text
    assert "packages = []" in config_text
    assert 'API_URL = "https://example.invalid"' in config_text
    assert '"./data" = "/data"' in config_text
    assert any("JovyKit config" in message for message in messages)


def test_keyboard_editor_reports_errors_and_can_cancel(create_project: Any) -> None:
    project = create_project()
    keys = iter([*["down"] * 6, "enter", "q"])
    inputs = iter(["sometimes"])
    messages: list[str] = []

    result = run_config_editor(
        env=project.env_dir,
        input_func=lambda prompt: next(inputs),
        key_func=lambda: next(keys),
        output=messages.append,
    )

    assert result == "cancelled"
    assert any("GPU mode" in message for message in messages)


def test_keyboard_editor_cycles_choice_and_applies(
    monkeypatch: pytest.MonkeyPatch,
    create_project: Any,
) -> None:
    project = create_project()
    keys = iter([*["down"] * 6, "right", "a"])
    messages: list[str] = []
    installed: list[str] = []
    monkeypatch.setattr(
        "jovykit.config_editor.commands.install",
        lambda config, **kwargs: installed.append(config.gpus),
    )

    result = run_config_editor(
        env=project.env_dir,
        key_func=lambda: next(keys),
        output=messages.append,
    )

    assert result == "applied"
    assert installed == ["all"]


def test_keyboard_editor_reports_unknown_key(create_project: Any) -> None:
    project = create_project()
    keys = iter(["x", "q"])
    messages: list[str] = []

    result = run_config_editor(
        env=project.env_dir,
        key_func=lambda: next(keys),
        output=messages.append,
    )

    assert result == "cancelled"
    assert any("Use up/down" in message for message in messages)


def test_inline_empty_values_clear_mappings(create_project: Any) -> None:
    project = create_project(
        config_transform=lambda text: text.replace(
            "[runtime.env]\n\n[runtime.volumes]",
            '[runtime.env]\nAPI_URL = "https://example.invalid"\n\n'
            '[runtime.volumes]\n"./data" = "/data"',
        )
    )
    keys = iter([*["down"] * 14, "enter", "down", "enter", "s"])
    inputs = iter(["-", "-"])

    result = run_config_editor(
        env=project.env_dir,
        input_func=lambda prompt: next(inputs),
        key_func=lambda: next(keys),
        output=lambda message: None,
    )

    config_text = (project.root / "jovy.toml").read_text(encoding="utf-8")
    assert result == "saved"
    assert "packages = []" in config_text
    assert "API_URL" not in config_text
    assert '"./data"' not in config_text


def test_cycle_field_rejects_text_and_handles_unknown_choice(
    create_project: Any,
) -> None:
    values = values_from_config(create_project().config)

    with pytest.raises(JovyKitError, match="edited with Enter"):
        _cycle_field(values, ConfigField("project_name", "Project name"), "right")

    edited = ConfigEditorValues(**{**values.__dict__, "gpus": "surprise"})

    assert (
        _cycle_field(
            edited,
            ConfigField("gpus", "GPU mode", "choice", ("auto", "none", "all")),
            "right",
        ).gpus
        == "none"
    )


def test_edit_field_toggles_booleans(create_project: Any) -> None:
    values = values_from_config(create_project().config)

    edited = _edit_field(
        values,
        ConfigField("watch_enabled", "Config watch enabled", "bool"),
        input_func=lambda prompt: pytest.fail("boolean edit should not prompt"),
        output=lambda message: None,
    )

    assert edited.watch_enabled is False


def test_editor_fields_do_not_include_package_selection() -> None:
    assert all(field.key != "python_packages" for field in EDITOR_FIELDS)


def test_textual_field_helpers_update_and_render_values(create_project: Any) -> None:
    values = values_from_config(create_project().config)

    edited = _set_textual_field_value(
        values,
        ConfigField("runtime_env", "Runtime env", "mapping"),
        "API_URL=https://example.invalid",
    )

    assert edited.runtime_env == {"API_URL": "https://example.invalid"}
    assert "KEY=VALUE" in _field_placeholder(
        edited,
        ConfigField("runtime_env", "Runtime env", "mapping"),
    )
    assert _render_textual_fields(edited, 0, "Updated Project name.").title == (
        "JovyKit config"
    )
    assert _render_textual_fields(None, 0, "Error: nope").title == "JovyKit config"


def test_textual_editor_mount_loads_values(
    monkeypatch: pytest.MonkeyPatch,
    create_project: Any,
) -> None:
    project = create_project()
    app = JovyKitConfigEditor(env=project.env_dir)
    focused: list[str] = []

    class FakeInput:
        def focus(self) -> None:
            focused.append("focus")

    monkeypatch.setattr(
        "jovykit.config_editor.commands.load_env",
        lambda env: project.config,
    )
    monkeypatch.setattr(app, "_refresh", lambda: focused.append("refresh"))
    monkeypatch.setattr(app, "query_one", lambda *_args, **_kwargs: FakeInput())

    app.on_mount()

    assert app.config == project.config
    assert app.values == values_from_config(project.config)
    assert focused == ["refresh", "focus"]


def test_textual_editor_mount_reports_load_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = JovyKitConfigEditor()
    messages: list[str] = []

    class FakeInput:
        def focus(self) -> None:
            messages.append("focus")

    def fail_load(env: object) -> object:
        raise JovyKitError("missing config")

    monkeypatch.setattr("jovykit.config_editor.commands.load_env", fail_load)
    monkeypatch.setattr(app, "_append", messages.append)
    monkeypatch.setattr(app, "_refresh", lambda: messages.append("refresh"))
    monkeypatch.setattr(app, "query_one", lambda *_args, **_kwargs: FakeInput())

    app.on_mount()

    assert "Error: missing config" in app.status
    assert any("missing config" in message for message in messages)


def test_textual_editor_actions_update_selection_and_cycle(
    monkeypatch: pytest.MonkeyPatch,
    create_project: Any,
) -> None:
    app = JovyKitConfigEditor()
    app.values = values_from_config(create_project().config)
    app.selected = 6
    refreshed: list[str] = []
    messages: list[str] = []
    monkeypatch.setattr(app, "_refresh", lambda: refreshed.append(app.status))
    monkeypatch.setattr(app, "_append", messages.append)

    app.action_next_field()
    app.action_previous_field()
    app.action_cycle_right()
    app.selected = 0
    app.action_cycle_left()

    assert app.selected == 0
    assert app.values.gpus == "all"
    assert any("Updated GPU mode" in message for message in messages)
    assert "Error: This field is edited with Enter." in refreshed[-1]


def test_textual_editor_actions_noop_without_values() -> None:
    app = JovyKitConfigEditor()

    app.action_next_field()
    app.action_previous_field()
    app.action_cycle_left()
    app.action_cycle_right()
    app._save(apply_now=False)

    assert app.selected == 0


def test_textual_editor_input_commands_and_value_updates(
    monkeypatch: pytest.MonkeyPatch,
    create_project: Any,
) -> None:
    app = JovyKitConfigEditor()
    app.values = values_from_config(create_project().config)
    events: list[str] = []
    monkeypatch.setattr(app, "action_save", lambda: events.append("save"))
    monkeypatch.setattr(app, "action_apply", lambda: events.append("apply"))
    monkeypatch.setattr(app, "action_cancel", lambda: events.append("cancel"))
    monkeypatch.setattr(app, "_refresh", lambda: events.append("refresh"))
    monkeypatch.setattr(app, "_append", events.append)

    app.on_value_submitted(cast(Any, _FakeSubmitted("s")))
    app.on_value_submitted(cast(Any, _FakeSubmitted("a")))
    app.on_value_submitted(cast(Any, _FakeSubmitted("q")))
    app.selected = 5
    app.on_value_submitted(cast(Any, _FakeSubmitted("7777")))
    app.selected = 6
    app.on_value_submitted(cast(Any, _FakeSubmitted("sometimes")))

    assert events[:3] == ["save", "apply", "cancel"]
    assert app.values.port == 7777
    assert "Error: GPU mode must be one of: auto, none, all." == app.status


def test_textual_editor_input_noops_without_values() -> None:
    app = JovyKitConfigEditor()
    event = _FakeSubmitted("7777")

    app.on_value_submitted(cast(Any, event))

    assert event.input.cleared is False


def test_textual_editor_save_paths(
    monkeypatch: pytest.MonkeyPatch,
    create_project: Any,
) -> None:
    project = create_project()
    app = JovyKitConfigEditor()
    app.config = project.config
    app.values = values_from_config(project.config)
    exits: list[str | None] = []
    messages: list[str] = []
    saved: list[bool] = []
    monkeypatch.setattr(app, "exit", exits.append)
    monkeypatch.setattr(app, "_append", messages.append)
    monkeypatch.setattr(app, "_refresh", lambda: messages.append("refresh"))
    monkeypatch.setattr(
        "jovykit.config_editor.save_config_values",
        lambda *_args, **kwargs: saved.append(kwargs["apply_now"]),
    )

    app.action_save()
    app.action_apply()

    assert exits == ["saved", "applied"]
    assert saved == [False, True]

    def fail_save(*_args: object, **_kwargs: object) -> object:
        raise JovyKitError("bad save")

    monkeypatch.setattr("jovykit.config_editor.save_config_values", fail_save)
    app._save(apply_now=False)

    assert "Error: bad save" == app.status
    assert any("bad save" in message for message in messages)


def test_textual_editor_refresh_updates_widgets(
    monkeypatch: pytest.MonkeyPatch,
    create_project: Any,
) -> None:
    app = JovyKitConfigEditor()
    app.values = values_from_config(create_project().config)
    updated: list[object] = []

    class FakeStatic:
        def update(self, value: object) -> None:
            updated.append(value)

    class FakeInput:
        placeholder = ""

    command = FakeInput()

    def fake_query_one(selector: object, *_args: object, **_kwargs: object) -> object:
        return FakeStatic() if selector == "#fields" else command

    monkeypatch.setattr(app, "query_one", fake_query_one)

    app._refresh()

    assert updated
    assert command.placeholder.startswith("Project name:")


class _FakeInput:
    def __init__(self) -> None:
        self.cleared = False

    def clear(self) -> None:
        self.cleared = True


class _FakeSubmitted:
    def __init__(self, value: str) -> None:
        self.value = value
        self.input = _FakeInput()


def test_scalar_editor_validation_helpers(create_project: Any) -> None:
    values = values_from_config(create_project().config)

    with pytest.raises(JovyKitError, match="Unknown field"):
        _set_scalar_value(values, "missing", "value")
    with pytest.raises(JovyKitError, match="integer"):
        _set_scalar_value(values, "port", "not-a-number")
    with pytest.raises(JovyKitError, match="Boolean"):
        _parse_bool("maybe")

    assert _set_scalar_value(values, "watch_enabled", "off").watch_enabled is False


@pytest.mark.parametrize(
    ("key", "value", "attribute"),
    [
        ("project_name", "demo", "project_name"),
        ("workdir", "workspace", "workdir"),
        ("base_image", "python:3.11", "base_image"),
        ("image_name", "demo-image", "image_name"),
        ("image_tag", "dev", "image_tag"),
        ("gpus", "none", "gpus"),
        ("restart_policy", "always", "restart_policy"),
        ("jupyter_token", "secret", "jupyter_token"),
        ("jupyter_log_level", "DEBUG", "jupyter_log_level"),
        ("work_mount", "/workspace", "work_mount"),
        ("watch_workspace_mode", "sync", "watch_workspace_mode"),
        ("port", 9999, "port"),
        ("jupyter_lab", False, "jupyter_lab"),
        ("watch_enabled", False, "watch_enabled"),
        ("python_packages", ["numpy"], "python_packages"),
        ("runtime_env", {"API_URL": "https://example.invalid"}, "runtime_env"),
        ("runtime_volumes", {"./data": "/data"}, "runtime_volumes"),
    ],
)
def test_replace_editor_value_updates_supported_fields(
    create_project: Any,
    key: str,
    value: object,
    attribute: str,
) -> None:
    values = values_from_config(create_project().config)

    edited = _replace_editor_value(values, key, value)

    assert getattr(edited, attribute) == value


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("project_name", 123, "project_name"),
        ("port", "8888", "port"),
        ("jupyter_lab", "true", "jupyter_lab"),
        ("watch_enabled", "false", "watch_enabled"),
        ("python_packages", "numpy", "python_packages"),
        ("runtime_env", ["API_URL=value"], "runtime_env"),
        ("runtime_volumes", ["./data=/data"], "runtime_volumes"),
        ("missing", "value", "Unknown field"),
    ],
)
def test_replace_editor_value_rejects_invalid_values(
    create_project: Any,
    key: str,
    value: object,
    message: str,
) -> None:
    values = values_from_config(create_project().config)

    with pytest.raises(JovyKitError, match=message):
        _replace_editor_value(values, key, value)


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"project_name": ""}, "Project name"),
        ({"workdir": ""}, "Workdir"),
        ({"base_image": ""}, "Base image"),
        ({"image_name": ""}, "Image name"),
        ({"image_tag": ""}, "Image tag"),
        ({"port": 0}, "Port"),
        ({"work_mount": "relative"}, "Work mount"),
    ],
)
def test_validate_values_rejects_invalid_required_fields(
    create_project: Any,
    updates: dict[str, object],
    message: str,
) -> None:
    values = values_from_config(create_project().config)
    edited = ConfigEditorValues(**{**values.__dict__, **updates})

    with pytest.raises(JovyKitError, match=message):
        _validate_values(edited)


def test_read_key_maps_arrow_escape_and_empty_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeStdin:
        def __init__(self, chunks: list[str]) -> None:
            self.chunks = chunks

        def isatty(self) -> bool:
            return False

        def read(self, size: int) -> str:
            return self.chunks.pop(0)

    monkeypatch.setattr("jovykit.config_editor.sys.stdin", FakeStdin(["\x1b", "[A"]))
    assert _read_key() == "up"

    monkeypatch.setattr("jovykit.config_editor.sys.stdin", FakeStdin(["\x1b", "[B"]))
    assert _read_key() == "down"

    monkeypatch.setattr("jovykit.config_editor.sys.stdin", FakeStdin(["\x1b", "[C"]))
    assert _read_key() == "right"

    monkeypatch.setattr("jovykit.config_editor.sys.stdin", FakeStdin(["\x1b", "[D"]))
    assert _read_key() == "left"

    monkeypatch.setattr("jovykit.config_editor.sys.stdin", FakeStdin(["\x1b", "[Z"]))
    assert _read_key() == "escape"

    monkeypatch.setattr("jovykit.config_editor.sys.stdin", FakeStdin(["\n"]))
    assert _read_key() == "enter"

    monkeypatch.setattr("jovykit.config_editor.sys.stdin", FakeStdin([""]))
    assert _read_key() == "q"
