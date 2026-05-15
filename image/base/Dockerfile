# syntax=docker/dockerfile:1.7

ARG BASE_IMAGE=ghcr.io/mihneateodorstoica/jovykit-minimal:latest
FROM ${BASE_IMAGE}

WORKDIR /tmp/requirements

COPY --chown=${NB_UID}:${NB_GID} \
    requirements-minimal.txt \
    requirements-base.txt \
    ./

USER root

RUN --mount=type=cache,target=/root/.cache/uv \
    export UV_CACHE_DIR=/root/.cache/uv UV_LINK_MODE=copy UV_SYSTEM_PYTHON=1 && \
    uv pip install --system -r requirements-base.txt && \
    fix-permissions "${CONDA_DIR}" && \
    fix-permissions "/home/${NB_USER}"

USER ${NB_UID}
WORKDIR "${HOME}"
