from __future__ import annotations

import asyncio
from typing import Any

import pytest
from textual.widgets import Input, Select, Switch, TextArea

from jovykit.config import JovyKitError, read_state, write_state
from jovykit.config_editor import (
    ConfigEditorApp,
    ConfigEditorValues,
    format_list_lines,
    format_mapping_lines,
    parse_list_lines,
    parse_mapping_lines,
    save_config_values,
    values_from_config,
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


def test_editor_uses_guided_controls(create_project: Any) -> None:
    project = create_project()
    app = ConfigEditorApp(env=project.env_dir)

    async def run() -> None:
        async with app.run_test():
            assert isinstance(app.query_one("#gpus"), Select)
            assert isinstance(app.query_one("#restart_policy"), Select)
            assert isinstance(app.query_one("#jupyter_log_level"), Select)
            assert isinstance(app.query_one("#watch_workspace_mode"), Select)
            assert isinstance(app.query_one("#jupyter_lab"), Switch)
            assert isinstance(app.query_one("#watch_enabled"), Switch)
            assert isinstance(app.query_one("#port"), Input)
            assert isinstance(app.query_one("#python_packages"), TextArea)
            app.exit("done")

    asyncio.run(run())
