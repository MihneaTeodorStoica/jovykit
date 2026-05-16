# syntax=docker/dockerfile:1.7

FROM ghcr.io/astral-sh/uv:0.11.12@sha256:3a59a3cdd5f7c217faa36e32dbc7fddbb0412889c2a0a5229f6d790e5a019dd7 AS uv-bin

FROM quay.io/jupyter/minimal-notebook:python-3.13@sha256:ed76b2d29fed80a73146efbf164d77e1f7e102e7481f4cd4a378311f01f7657b

LABEL org.opencontainers.image.description="JovyKit minimal Jupyter image with Python, uv, Git, OpenSSH, rsync, nvtop, and the core scientific Python stack."

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
