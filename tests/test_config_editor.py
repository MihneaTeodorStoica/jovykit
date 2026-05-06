from __future__ import annotations

from typing import Any

import pytest

from jovykit.config import JovyKitError, read_state, write_state
from jovykit.config_editor import (
    ConfigField,
    ConfigEditorValues,
    format_list_lines,
    format_mapping_lines,
    parse_list_lines,
    parse_mapping_lines,
    run_config_editor,
    save_config_values,
    values_from_config,
    _cycle_field,
    _edit_field,
    _parse_bool,
    _read_key,
    _replace_editor_value,
    _set_scalar_value,
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
            "down",
            "enter",
            "s",
        ]
    )
    inputs = iter(
        [
            "7777",
            "base",
            "numpy, pandas",
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
    assert 'packages = ["numpy", "pandas"]' in config_text
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


def test_inline_empty_values_clear_lists_and_mappings(create_project: Any) -> None:
    project = create_project()
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
