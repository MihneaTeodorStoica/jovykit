"""Readable generated file templates."""

from __future__ import annotations

from labkit.config import LabConfig


def render_containerfile(config: LabConfig) -> str:
    """Render the project overlay Containerfile."""
    return f"""FROM {config.base_image}

USER root
COPY requirements.txt /tmp/labkit/requirements.txt
RUN --mount=type=cache,target=/root/.cache/uv \\
    UV_SYSTEM_PYTHON=1 UV_LINK_MODE=copy \\
    uv pip install --system -r /tmp/labkit/requirements.txt && \\
    fix-permissions "${{CONDA_DIR}}" && \\
    fix-permissions "/home/${{NB_USER}}"

USER ${{NB_UID}}
WORKDIR ${{HOME}}/work
"""


def render_compose(config: LabConfig) -> str:
    """Render the Docker Compose file for a LabKit environment."""
    gpu_block = ""
    if config.gpus in {"auto", "all"}:
        gpu_block = """
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
"""

    return f"""services:
  lab:
    image: {config.image_ref}
    build:
      context: .
      dockerfile: Containerfile
    ports:
      - "127.0.0.1:{config.port}:8888"
    volumes:
      - "../:{config.work_mount}"
      - "labkit-home:/home/jovyan"
    working_dir: {config.work_mount}
    stdin_open: true
    tty: true{gpu_block}

volumes:
  labkit-home:
"""
