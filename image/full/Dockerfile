# syntax=docker/dockerfile:1.7

ARG BASE_IMAGE=ghcr.io/mihneateodorstoica/jovykit-extended:latest
FROM ${BASE_IMAGE}

WORKDIR /tmp/requirements

COPY --chown=${NB_UID}:${NB_GID} \
    requirements-minimal.txt \
    requirements-base.txt \
    requirements-extended.txt \
    requirements-full.txt \
    ./

USER root

RUN --mount=type=cache,target=/root/.cache/uv \
    apt-get update -o Acquire::Retries=3 && \
    apt-get install -y --no-install-recommends \
        build-essential && \
    mamba install --yes -c conda-forge "nodejs>=20,<23" && \
    export UV_CACHE_DIR=/root/.cache/uv UV_LINK_MODE=copy UV_SYSTEM_PYTHON=1 && \
    uv pip install --system -r requirements-full.txt && \
    jupyter lab build --dev-build=False --minimize=False && \
    apt-get purge -y --auto-remove \
        build-essential && \
    mamba clean --all -f -y && \
    rm -rf /var/lib/apt/lists/* && \
    fix-permissions "${CONDA_DIR}" && \
    fix-permissions "/home/${NB_USER}"

USER ${NB_UID}
WORKDIR "${HOME}"
