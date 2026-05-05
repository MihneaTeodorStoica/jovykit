"""Readable generated file templates."""

from __future__ import annotations

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
  jovy:
    image: {config.image_ref}
    build:
      context: .
      dockerfile: Containerfile
    ports:
      - "127.0.0.1:{config.port}:8888"
    volumes:
      - "../:{config.work_mount}"
      - "jovykit-home:/home/jovyan"
    working_dir: {config.work_mount}
    stdin_open: true
    tty: true{gpu_block}

volumes:
  jovykit-home:
"""
