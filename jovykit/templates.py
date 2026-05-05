"""Readable generated file templates."""

from __future__ import annotations

import yaml
from typing import Any

from jovykit.config import JovyConfig


def render_containerfile(config: JovyConfig) -> str:
    """Render the project overlay Containerfile."""
    return f"""FROM {config.base_image}

USER root
COPY requirements.txt /tmp/jovykit/requirements.txt
RUN --mount=type=cache,target=/root/.cache/uv \\
    UV_SYSTEM_PYTHON=1 UV_LINK_MODE=copy \\
    uv pip install --system -r /tmp/jovykit/requirements.txt && \\
    fix-permissions "${{CONDA_DIR}}" && \\
    fix-permissions "/home/${{NB_USER}}"

USER ${{NB_UID}}
WORKDIR ${{HOME}}/work
"""


def render_compose(config: JovyConfig) -> str:
    """Render the Docker Compose file for a JovyKit environment."""
    service: dict[str, Any] = {
        "image": config.image_ref,
        "build": {"context": ".", "dockerfile": "Containerfile"},
        "ports": [f"127.0.0.1:{config.port}:8888"],
        "environment": {
            "JUPYTER_ENABLE_LAB": "yes",
            "JUPYTER_LOG_LEVEL": config.jupyter_log_level,
        },
        "volumes": [
            f"{config.compose_workdir}:{config.work_mount}",
            "jovykit-home:/home/jovyan",
        ],
        "working_dir": config.work_mount,
        "stdin_open": True,
        "tty": True,
        "develop": {
            "watch": [
                {
                    "action": "sync",
                    "path": config.compose_workdir,
                    "target": config.work_mount,
                    "initial_sync": True,
                    "ignore": [
                        ".jovy/",
                        ".git/",
                        ".venv/",
                        "__pycache__/",
                        ".mypy_cache/",
                        ".pytest_cache/",
                        ".ruff_cache/",
                    ],
                },
                {"action": "rebuild", "path": "requirements.txt"},
                {"action": "rebuild", "path": "Containerfile"},
            ]
        },
    }
    if config.jupyter_token and config.jupyter_token.lower() != "auto":
        service["environment"]["JUPYTER_TOKEN"] = config.jupyter_token
    if config.gpus in {"auto", "all"}:
        service["deploy"] = {
            "resources": {
                "reservations": {
                    "devices": [
                        {
                            "driver": "nvidia",
                            "count": "all",
                            "capabilities": ["gpu"],
                        }
                    ]
                }
            }
        }

    compose = {"services": {"jovy": service}, "volumes": {"jovykit-home": None}}
    return yaml.safe_dump(compose, sort_keys=False)
