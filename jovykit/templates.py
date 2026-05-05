"""Readable generated file templates."""

from __future__ import annotations

import shlex
import yaml
from typing import Any

from jovykit.config import JovyConfig, hash_jupyter_password


def escape_compose_interpolation(value: str) -> str:
    """Escape dollar signs so Docker Compose does not expand them."""
    return value.replace("$", "$$")


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
    return f"""FROM {config.base_image}

USER root
{apt_block}\
COPY jovy.lock /tmp/jovykit/jovy.lock
RUN --mount=type=cache,target=/root/.cache/uv \\
    UV_SYSTEM_PYTHON=1 UV_LINK_MODE={uv_link_mode} \\
    uv pip install {pip_args_prefix}--system -r /tmp/jovykit/jovy.lock && \\
    fix-permissions "${{CONDA_DIR}}" && \\
    fix-permissions "/home/${{NB_USER}}"

USER ${{NB_UID}}
WORKDIR ${{HOME}}/work
"""


def render_compose(config: JovyConfig) -> str:
    """Render the Docker Compose file for a JovyKit environment."""
    build: dict[str, Any] = {"context": ".", "dockerfile": "Containerfile"}
    if config.image_target:
        build["target"] = config.image_target
    if config.image_platform:
        build["platform"] = config.image_platform
    if config.image_build_args:
        build["args"] = config.image_build_args

    environment = {
        "JUPYTER_ENABLE_LAB": "yes" if config.jupyter_lab else "no",
        "JUPYTER_LOG_LEVEL": config.jupyter_log_level,
        "JUPYTER_TOKEN": config.jupyter_token,
        **config.runtime_env,
    }

    volumes = ["jovykit-home:/home/jovyan"]
    if config.watch_workspace_mode == "bind":
        volumes.insert(0, f"{config.compose_workdir}:{config.work_mount}")
    volumes.extend(
        f"{host_path}:{container_path}"
        for host_path, container_path in config.runtime_volumes.items()
    )

    service: dict[str, Any] = {
        "image": config.image_ref,
        "build": build,
        "ports": [f"127.0.0.1:{config.port}:8888"],
        "environment": environment,
        "volumes": volumes,
        "working_dir": config.work_mount,
        "stdin_open": True,
        "tty": True,
    }
    if config.restart_policy:
        service["restart"] = config.restart_policy
    if config.runtime_user:
        service["user"] = config.runtime_user
    command = shlex.split(config.jupyter_command or "start-notebook.py")
    command_args = ["--ServerApp.token="]
    if config.jupyter_password:
        password_hash = escape_compose_interpolation(
            hash_jupyter_password(config.jupyter_password)
        )
        command_args.append(
            f"--PasswordIdentityProvider.hashed_password={password_hash}"
        )
    else:
        command_args.append("--PasswordIdentityProvider.hashed_password=")
    service["command"] = [*command, *command_args]
    if config.watch_enabled:
        watch_rules: list[dict[str, Any]] = []
        if config.watch_workspace_mode == "sync":
            watch_rules.append(
                {
                    "action": "sync",
                    "path": config.compose_workdir,
                    "target": config.work_mount,
                    "initial_sync": True,
                    "ignore": config.watch_ignore,
                }
            )
        watch_rules.extend(
            {"action": "rebuild", "path": path} for path in config.watch_rebuild
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

    compose = {"services": {"jovy": service}, "volumes": {"jovykit-home": None}}
    return yaml.safe_dump(compose, sort_keys=False)
