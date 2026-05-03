# syntax=docker/dockerfile:1.7

ARG MINIMAL_NOTEBOOK_IMAGE=quay.io/jupyter/minimal-notebook:python-3.11
ARG BASE_NOTEBOOK_IMAGE=quay.io/jupyter/base-notebook:python-3.11
ARG UV_IMAGE=ghcr.io/astral-sh/uv:latest

FROM ${UV_IMAGE} AS uv-bin

FROM ${MINIMAL_NOTEBOOK_IMAGE} AS minimal

COPY --from=uv-bin /uv /uvx /usr/local/bin/

WORKDIR /tmp/requirements

COPY --chown=${NB_UID}:${NB_GID} requirements-minimal.txt ./

USER root

RUN --mount=type=cache,target=/root/.cache/uv \
    export UV_CACHE_DIR=/root/.cache/uv UV_LINK_MODE=copy UV_SYSTEM_PYTHON=1 && \
    uv pip install --upgrade pip setuptools wheel && \
    uv pip install --system -r requirements-minimal.txt && \
    fix-permissions "${CONDA_DIR}" && \
    fix-permissions "/home/${NB_USER}"

USER ${NB_UID}
WORKDIR "${HOME}"


FROM minimal AS base

WORKDIR /tmp/requirements

COPY --chown=${NB_UID}:${NB_GID} requirements-base.txt ./

USER root

RUN --mount=type=cache,target=/root/.cache/uv \
    export UV_CACHE_DIR=/root/.cache/uv UV_LINK_MODE=copy UV_SYSTEM_PYTHON=1 && \
    uv pip install --system -r requirements-base.txt && \
    fix-permissions "${CONDA_DIR}" && \
    fix-permissions "/home/${NB_USER}"

USER ${NB_UID}
WORKDIR "${HOME}"


FROM ${BASE_NOTEBOOK_IMAGE} AS extended

COPY --from=uv-bin /uv /uvx /usr/local/bin/

WORKDIR /tmp/requirements

COPY --chown=${NB_UID}:${NB_GID} \
    requirements-minimal.txt \
    requirements-base.txt \
    requirements-extended.txt \
    ./

USER root

RUN --mount=type=cache,target=/root/.cache/uv \
    export UV_CACHE_DIR=/root/.cache/uv UV_LINK_MODE=copy UV_SYSTEM_PYTHON=1 && \
    uv pip install --upgrade pip setuptools wheel && \
    uv pip install --system -r requirements-extended.txt && \
    fix-permissions "${CONDA_DIR}" && \
    fix-permissions "/home/${NB_USER}"

USER ${NB_UID}
WORKDIR "${HOME}"


FROM extended AS full

WORKDIR /tmp/requirements

COPY --chown=${NB_UID}:${NB_GID} requirements-full.txt ./

USER root

RUN --mount=type=cache,target=/root/.cache/uv \
    export UV_CACHE_DIR=/root/.cache/uv UV_LINK_MODE=copy UV_SYSTEM_PYTHON=1 && \
    uv pip install --system -r requirements-full.txt && \
    fix-permissions "${CONDA_DIR}" && \
    fix-permissions "/home/${NB_USER}"

USER ${NB_UID}
WORKDIR "${HOME}"
