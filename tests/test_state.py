from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from jovykit.config import write_state
from jovykit.runtime import DockerError
from jovykit import state
from jovykit.state import discover_status, status_from_config


def test_status_not_initialized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    status = discover_status()

    assert status.initialized is False
    assert status.status == "not initialized"
    assert status.url == "unavailable"
    assert "No JovyKit environment found" in str(status.last_error)


def test_status_stopped_from_empty_compose_ps(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    monkeypatch.setattr("jovykit.state.compose_ps", lambda config: "")
    monkeypatch.setattr("jovykit.state.is_build_stale", lambda config: False)

    status = status_from_config(project.config)

    assert status.status == "stopped"
    assert status.build == "fresh"
    assert status.image == project.config.image_ref


def test_status_running_healthy_from_compose_json(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project(
        token="dev-token",
        config_transform=lambda text: text.replace(
            "packages = []", 'packages = ["numpy", "pandas"]'
        ),
    )
    output = json.dumps(
        [
            {
                "Service": "jovy",
                "State": "running",
                "Health": "healthy",
            }
        ]
    )
    monkeypatch.setattr("jovykit.state.compose_ps", lambda config: output)
    monkeypatch.setattr("jovykit.state.is_build_stale", lambda config: False)

    status = status_from_config(project.config)

    assert status.status == "healthy"
    assert status.health == "healthy"
    assert status.url.endswith("/lab?token=dev-token")
    assert status.package_count == 2


def test_status_running_from_compose_json_lines(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    output = (
        '{"Service": "helper", "State": "exited"}\n'
        "not-json\n"
        '{"Name": "project-jovy-1", "state": "running"}\n'
    )
    monkeypatch.setattr("jovykit.state.compose_ps", lambda config: output)
    monkeypatch.setattr("jovykit.state.is_build_stale", lambda config: False)

    status = status_from_config(project.config)

    assert status.status == "running"
    assert status.health == "unknown"
    assert status.is_running is True


def test_status_reports_stale_image(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    monkeypatch.setattr("jovykit.state.compose_ps", lambda config: "")
    monkeypatch.setattr("jovykit.state.is_build_stale", lambda config: True)

    status = status_from_config(project.config)

    assert status.status == "stopped"
    assert status.build == "stale"


def test_status_handles_invalid_compose_json_as_stopped(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    monkeypatch.setattr("jovykit.state.compose_ps", lambda config: "not-json")
    monkeypatch.setattr("jovykit.state.is_build_stale", lambda config: False)

    status = status_from_config(project.config)

    assert status.status == "stopped"


def test_status_normalizers_cover_dashboard_states() -> None:
    assert state._normalize_container_status("created", "") == "starting"
    assert state._normalize_container_status("exited", "") == "stopped"
    assert state._normalize_container_status("dead", "") == "error"
    assert state._normalize_container_status("something else", "") == "unknown"
    assert state._normalize_health("starting") == "starting"
    assert state._normalize_health("none") == "unknown"
    assert state._gpu_label("all") == "enabled"
    assert state._string_or_none(None) is None
    assert state._string_or_none("  ") is None


def test_status_counts_config_packages(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project(
        config_transform=lambda text: text.replace("packages = []", 'packages = ["x"]')
    )
    monkeypatch.setattr("jovykit.state.compose_ps", lambda config: "")
    monkeypatch.setattr("jovykit.state.is_build_stale", lambda config: False)

    assert status_from_config(project.config).package_count == 1


def test_status_error_includes_compact_last_error(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    monkeypatch.setattr(
        "jovykit.state.compose_ps",
        lambda config: (_ for _ in ()).throw(DockerError("Docker exploded")),
    )
    monkeypatch.setattr("jovykit.state.is_build_stale", lambda config: False)
    write_state(project.env_dir, {"last_error": "Docker build failed"})

    status = status_from_config(project.config)

    assert status.status == "error"
    assert status.last_error == "Docker build failed"
