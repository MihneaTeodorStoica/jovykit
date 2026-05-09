# syntax=docker/dockerfile:1.7

FROM ghcr.io/astral-sh/uv:0.11.12@sha256:3a59a3cdd5f7c217faa36e32dbc7fddbb0412889c2a0a5229f6d790e5a019dd7 AS uv-bin

FROM quay.io/jupyter/minimal-notebook:python-3.13@sha256:ed76b2d29fed80a73146efbf164d77e1f7e102e7481f4cd4a378311f01f7657b AS minimal

COPY --from=uv-bin /uv /uvx /usr/local/bin/

WORKDIR /tmp/requirements

COPY --chown=${NB_UID}:${NB_GID} requirements-minimal.txt ./

USER root

RUN sed -i \
        -e 's|http://archive.ubuntu.com/ubuntu/|https://archive.ubuntu.com/ubuntu/|' \
        -e 's|http://security.ubuntu.com/ubuntu/|https://security.ubuntu.com/ubuntu/|' \
        /etc/apt/sources.list.d/ubuntu.sources && \
    apt-get update -o Acquire::Retries=3 && \
    apt-get install -y --no-install-recommends \
        git \
        openssh-client \
        rsync \
        software-properties-common && \
    add-apt-repository -y ppa:quentiumyt/nvtop && \
    apt-get update -o Acquire::Retries=3 && \
    apt-get install -y --no-install-recommends \
        nvtop-nightly && \
    rm -rf /var/lib/apt/lists/* && \
    install -d -m 0700 -o "${NB_UID}" -g "${NB_GID}" "/home/${NB_USER}/.ssh"

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


FROM quay.io/jupyter/base-notebook:python-3.13@sha256:3171810d80d421edb7bfb93422d5587a763bfee505a603a91cb4f8babdac37ff AS extended

COPY --from=uv-bin /uv /uvx /usr/local/bin/

WORKDIR /tmp/requirements

COPY --chown=${NB_UID}:${NB_GID} \
    requirements-minimal.txt \
    requirements-base.txt \
    requirements-extended.txt \
    ./

USER root

RUN sed -i \
        -e 's|http://archive.ubuntu.com/ubuntu/|https://archive.ubuntu.com/ubuntu/|' \
        -e 's|http://security.ubuntu.com/ubuntu/|https://security.ubuntu.com/ubuntu/|' \
        /etc/apt/sources.list.d/ubuntu.sources && \
    apt-get update -o Acquire::Retries=3 && \
    apt-get install -y --no-install-recommends \
        git \
        openssh-client \
        rsync \
        software-properties-common && \
    add-apt-repository -y ppa:quentiumyt/nvtop && \
    apt-get update -o Acquire::Retries=3 && \
    apt-get install -y --no-install-recommends \
        nvtop-nightly && \
    rm -rf /var/lib/apt/lists/* && \
    install -d -m 0700 -o "${NB_UID}" -g "${NB_GID}" "/home/${NB_USER}/.ssh"

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
    jupyter lab build --dev-build=False --minimize=False && \
    fix-permissions "${CONDA_DIR}" && \
    fix-permissions "/home/${NB_USER}"

USER ${NB_UID}
WORKDIR "${HOME}"
