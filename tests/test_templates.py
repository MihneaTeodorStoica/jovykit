from __future__ import annotations

from typing import Any

import yaml

from jovykit.templates import render_compose, render_containerfile


def test_render_compose_disables_gpu_deploy_for_none(create_project: Any) -> None:
    project = create_project(gpus="none")

    service = yaml.safe_load(render_compose(project.config))["services"]["jovy"]

    assert "deploy" not in service


def test_render_compose_enables_gpu_deploy_for_auto(create_project: Any) -> None:
    project = create_project(gpus="auto")

    service = yaml.safe_load(render_compose(project.config))["services"]["jovy"]

    devices = service["deploy"]["resources"]["reservations"]["devices"]
    assert devices[0]["driver"] == "nvidia"
    assert devices[0]["capabilities"] == ["gpu"]


def test_render_compose_omits_develop_watch_when_disabled(create_project: Any) -> None:
    project = create_project(
        config_transform=lambda text: text.replace("enabled = true", "enabled = false")
    )

    service = yaml.safe_load(render_compose(project.config))["services"]["jovy"]

    assert "develop" not in service


def test_render_compose_sync_workspace_has_initial_sync_and_ignores(
    create_project: Any,
) -> None:
    project = create_project(
        config_transform=lambda text: text.replace(
            'workspace_mode = "bind"', 'workspace_mode = "sync"'
        )
    )

    service = yaml.safe_load(render_compose(project.config))["services"]["jovy"]

    assert f"../work:{project.config.work_mount}" not in service["volumes"]
    assert service["develop"]["watch"][0] == {
        "action": "sync",
        "path": "../work",
        "target": project.config.work_mount,
        "initial_sync": True,
        "ignore": project.config.watch_ignore,
    }


def test_render_containerfile_shell_quotes_apt_packages_and_pip_args(
    create_project: Any,
) -> None:
    project = create_project(
        config_transform=lambda text: text.replace(
            "packages = []",
            'packages = ["curl", "weird package"]',
        ).replace(
            "pip_args = []",
            'pip_args = ["--index-url", "https://example.test/simple path"]',
        )
    )

    containerfile = render_containerfile(project.config)

    assert "curl 'weird package'" in containerfile
    assert "--index-url 'https://example.test/simple path' --system" in containerfile
