from __future__ import annotations

import pytest
import yaml

from jovykit.config import JovyKitError
from jovykit.images import resolve_image_level
from jovykit.templates import render_compose, render_containerfile, render_requirements


def test_render_compose_is_small_and_watch_enabled() -> None:
    compose = yaml.safe_load(
        render_compose(
            project_name="My Project",
            level="base",
            python_version="3.13",
            gpu="none",
            port=8888,
            token="jovykit",
        )
    )

    service = compose["services"]["jovy"]
    assert set(service) == {
        "build",
        "image",
        "environment",
        "ports",
        "volumes",
        "working_dir",
        "stdin_open",
        "tty",
        "develop",
    }
    assert "gpus" not in service
    assert service["image"] == "my-project-jovy:local"
    assert service["environment"] == {"JUPYTER_TOKEN": "jovykit"}
    assert service["develop"]["watch"] == [
        {"action": "rebuild", "path": "./Dockerfile"},
        {"action": "rebuild", "path": "./requirements.txt"},
    ]


def test_render_containerfile_uses_requirements_txt_and_uv() -> None:
    text = render_containerfile(level="full", python_version="3.12")

    assert (
        "ARG JOVY_BASE_IMAGE=ghcr.io/mihneateodorstoica/jovykit-full:python-3.12"
        in text
    )
    assert "FROM ${JOVY_BASE_IMAGE}" in text
    assert "ARG PYTHON_VERSION" not in text
    assert "VIRTUAL_ENV=/opt/jovy" in text
    assert "NB_USER=jovyan" in text
    assert "uv" in text
    assert "source=requirements.txt,target=/tmp/jovy-requirements.txt,readonly" in text
    assert "/usr/local/share/jovykit/base-requirements.txt" not in text
    assert "mamba" not in text
    assert "conda" not in text
    assert "environment.yml" not in text
    assert "jovy-install-environment" not in text
    assert "required=false" not in text


def test_render_requirements_is_empty_by_default() -> None:
    assert render_requirements() == ""


def test_arbitrary_image_source_is_rejected() -> None:
    with pytest.raises(JovyKitError, match="Unknown image level"):
        resolve_image_level("quay.io/jupyter/minimal-notebook")


def test_python_version_must_be_published_for_image_level() -> None:
    with pytest.raises(
        JovyKitError, match="full images support Python versions: 3.11, 3.12, 3.13"
    ):
        resolve_image_level("full", "3.14")

    assert (
        resolve_image_level("minimal", "3.14")
        == "ghcr.io/mihneateodorstoica/jovykit-minimal:python-3.14"
    )
