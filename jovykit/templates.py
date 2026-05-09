"""Readable generated file templates."""

from __future__ import annotations

import shlex
import yaml
from typing import Any

from jovykit.config import JovyConfig


def render_containerfile(config: JovyConfig) -> str:
    """Render the project overlay Containerfile."""
    apt_block = ""
    if config.apt_packages:
        packages = " ".join(shlex.quote(package) for package in config.apt_packages)
        apt_block = f"""RUN apt-get update && \\
    apt-get install -y --no-install-recommends {packages} && \\
    rm -rf /var/lib/apt/lists/*

"""
    pip_args = " ".join(shlex.quote(arg) for arg in config.pip_args)
    pip_args_prefix = f"{pip_args} " if pip_args else ""
    uv_link_mode = shlex.quote(config.uv_link_mode)
    workdir = shlex.quote(config.effective_work_mount)
    return f"""FROM {config.base_image}

ARG NB_USER={config.image_username}
ARG NB_UID={config.image_uid}
ARG NB_GID={config.image_gid}
ENV NB_USER=${{NB_USER}} \\
    NB_UID=${{NB_UID}} \\
    NB_GID=${{NB_GID}} \\
    HOME=/home/${{NB_USER}}

USER root
{apt_block}\
COPY jovy.lock /tmp/jovykit/jovy.lock
RUN --mount=type=cache,target=/root/.cache/uv \\
    UV_SYSTEM_PYTHON=1 UV_LINK_MODE={uv_link_mode} \\
    uv pip install {pip_args_prefix}--system -r /tmp/jovykit/jovy.lock && \\
    fix-permissions "${{CONDA_DIR}}" && \\
    fix-permissions "/home/${{NB_USER}}"

USER ${{NB_UID}}
WORKDIR {workdir}
"""


def render_compose(config: JovyConfig) -> str:
    """Render the Docker Compose file for a JovyKit environment."""
    build: dict[str, Any] = {
        "context": config.compose_project_path("."),
        "dockerfile": f"{config.env_dir.name}/Containerfile",
    }
    if config.image_target:
        build["target"] = config.image_target
    if config.image_platform:
        build["platform"] = config.image_platform
    if config.effective_image_build_args:
        build["args"] = config.effective_image_build_args

    environment = {
        "JUPYTER_ENABLE_LAB": "yes" if config.jupyter_lab else "no",
        "JUPYTER_LOG_LEVEL": config.jupyter_log_level,
        "JUPYTER_TOKEN": config.jupyter_token,
        "NB_USER": config.image_username,
        "NB_UID": str(config.image_uid),
        "NB_GID": str(config.image_gid),
        **config.runtime_env,
    }

    volumes = [
        f"{_compose_bind_source(config.compose_home_path)}:{config.notebook_home}"
    ]
    if config.watch_workspace_mode == "bind":
        volumes.append(f"{config.compose_workdir}:{config.effective_work_mount}")
    volumes.extend(
        f"{host_path}:{container_path}"
        for host_path, container_path in config.runtime_volumes.items()
    )

    service: dict[str, Any] = {
        "image": config.image_ref,
        "build": build,
        "ports": ["127.0.0.1:22:22", f"127.0.0.1:{config.port}:8888"],
        "environment": environment,
        "volumes": volumes,
        "working_dir": config.effective_work_mount,
        "stdin_open": True,
        "tty": True,
    }
    if config.restart_policy:
        service["restart"] = config.restart_policy
    if config.image_pull_policy:
        service["pull_policy"] = config.image_pull_policy
    if config.image_labels:
        service["labels"] = config.image_labels
    if config.runtime_user:
        service["user"] = config.runtime_user
    elif (
        config.image_username != "jovyan"
        or config.image_uid != 1000
        or config.image_gid != 100
    ):
        # start.sh must run as root to apply NB_USER/NB_UID/NB_GID safely
        service["user"] = "root"
    service["command"] = shlex.split(config.jupyter_command or "start-notebook.py")
    if config.watch_enabled:
        watch_rules: list[dict[str, Any]] = []
        if config.watch_workspace_mode == "sync":
            watch_rules.append(
                {
                    "action": "sync",
                    "path": config.compose_workdir,
                    "target": config.effective_work_mount,
                    "initial_sync": True,
                    "ignore": config.watch_ignore,
                }
            )
        watch_rules.extend(
            {
                "action": "rebuild",
                "path": (
                    config.compose_project_path("jovy.lock")
                    if path == "jovy.lock"
                    else path
                ),
            }
            for path in config.watch_rebuild
        )
        watch_rules.extend(
            {
                "action": "sync+restart",
                "path": config.compose_project_path(path),
                "target": f"/tmp/jovykit-watch/{path.replace('/', '-')}",
                "initial_sync": True,
            }
            for path in config.watch_restart
        )
        service["develop"] = {"watch": watch_rules}
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

    compose = {"services": {"jovy": service}}
    return yaml.safe_dump(compose, sort_keys=False)


def _compose_bind_source(path: str) -> str:
    """Return a Compose bind source that cannot be parsed as a named volume."""
    if path.startswith(("/", "./", "../", "~")):
        return path
    return f"./{path}"
