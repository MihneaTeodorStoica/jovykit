"""Generated Compose, Dockerfile, and requirements templates."""

from __future__ import annotations

import re
from typing import Any

import yaml

from jovykit.images import DEFAULT_PYTHON_VERSION, resolve_image_level
from jovykit.paths import SERVICE_NAME


def slugify_name(value: str) -> str:
    """Create a Docker-friendly local image name."""
    slug = re.sub(r"[^a-z0-9_.-]+", "-", value.lower()).strip("-_.")
    return slug or "jovykit"


def render_requirements() -> str:
    """Render the project requirements file."""
    return ""


def render_containerfile(
    *, level: str, python_version: str = DEFAULT_PYTHON_VERSION
) -> str:
    """Render the user-editable project Dockerfile."""
    base_image = resolve_image_level(level, python_version)
    return f"""# syntax=docker/dockerfile:1.7
ARG JOVY_BASE_IMAGE={base_image}
FROM ${{JOVY_BASE_IMAGE}}

USER root
ARG NB_USER=jovyan
ARG NB_UID=1000
ARG NB_GID=100
ENV HOME=/home/${{NB_USER}} \\
    NB_GID=${{NB_GID}} \\
    NB_UID=${{NB_UID}} \\
    NB_USER=${{NB_USER}} \\
    UV_LINK_MODE=hardlink \\
    UV_PYTHON_DOWNLOADS=never \\
    VIRTUAL_ENV=/opt/jovy
ENV PATH="${{VIRTUAL_ENV}}/bin:${{PATH}}"

RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \\
    --mount=type=bind,source=requirements.txt,target=/tmp/jovy-requirements.txt,readonly \\
    if [ -s /tmp/jovy-requirements.txt ]; then \\
        uv pip install --only-binary=:all: --python "${{VIRTUAL_ENV}}/bin/python" -r /tmp/jovy-requirements.txt; \\
    fi

USER ${{NB_UID}}
WORKDIR /home/${{NB_USER}}/work
"""


def render_compose(
    *,
    project_name: str,
    level: str,
    python_version: str,
    gpu: str,
    port: int,
    token: str,
) -> str:
    """Render the Compose file that becomes the project source of truth."""
    service: dict[str, Any] = {
        "build": {
            "context": ".",
            "dockerfile": "Dockerfile",
            "args": {
                "JOVY_BASE_IMAGE": resolve_image_level(level, python_version),
            },
        },
        "image": f"{slugify_name(project_name)}-jovy:local",
        "pull_policy": "build",
        "environment": {
            "JUPYTER_TOKEN": token,
        },
        "ports": [f"127.0.0.1:{port}:8888"],
        "volumes": [
            "./work:/home/jovyan/work",
            "./.jupyter:/home/jovyan/.jupyter",
        ],
        "working_dir": "/home/jovyan/work",
        "stdin_open": True,
        "tty": True,
        "develop": {
            "watch": [
                {"action": "rebuild", "path": "./Dockerfile"},
                {"action": "rebuild", "path": "./requirements.txt"},
            ]
        },
    }
    if gpu == "all":
        service["gpus"] = "all"
    compose = {"services": {SERVICE_NAME: service}}
    return yaml.safe_dump(compose, sort_keys=False)
