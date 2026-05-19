# syntax=docker/dockerfile:1.7

FROM ghcr.io/astral-sh/uv:bookworm-slim AS minimal

LABEL org.opencontainers.image.description="JovyKit minimal Jupyter image with Python, uv, JupyterLab add-ons, and Nitro CLI."

ARG PYTHON_VERSION=3.13
ARG NB_USER=jovyan
ARG NB_UID=1000
ARG NB_GID=100

ENV DEBIAN_FRONTEND=noninteractive \
    HOME=/home/${NB_USER} \
    JUPYTER_PORT=8888 \
    NB_GID=${NB_GID} \
    NB_UID=${NB_UID} \
    NB_USER=${NB_USER} \
    UV_LINK_MODE=copy \
    UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    VIRTUAL_ENV=/opt/jovy
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

WORKDIR /tmp/requirements
COPY requirements-minimal.txt ./

RUN apt-get update -o Acquire::Retries=3 && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
        openssh-client \
        tini && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd --gid "${NB_GID}" "${NB_USER}" || true && \
    useradd --uid "${NB_UID}" --gid "${NB_GID}" --create-home --shell /bin/bash "${NB_USER}" || true && \
    install -d -m 0755 -o "${NB_UID}" -g "${NB_GID}" /home/${NB_USER}/work && \
    install -d -m 0700 -o "${NB_UID}" -g "${NB_GID}" /home/${NB_USER}/.ssh

RUN install -d /usr/local/share/jovykit && \
    cp requirements-minimal.txt /usr/local/share/jovykit/base-requirements.txt

RUN --mount=type=cache,target=/root/.cache/uv \
    uv python install "${PYTHON_VERSION}" && \
    uv venv --clear --python "${PYTHON_VERSION}" "${VIRTUAL_ENV}" && \
    uv pip install --python "${VIRTUAL_ENV}/bin/python" --upgrade pip setuptools wheel && \
    uv pip install --python "${VIRTUAL_ENV}/bin/python" -r requirements-minimal.txt && \
    find "${VIRTUAL_ENV}" -type d -name __pycache__ -prune -exec rm -rf {} + && \
    find "${VIRTUAL_ENV}" -type f -name "*.pyc" -delete && \
    chown -R "${NB_UID}:${NB_GID}" "${VIRTUAL_ENV}" "/home/${NB_USER}"

USER ${NB_UID}
WORKDIR "${HOME}"
EXPOSE 8888
ENTRYPOINT ["tini", "-g", "--"]
CMD ["sh", "-lc", "jupyter lab --ip=0.0.0.0 --port=${JUPYTER_PORT} --no-browser --ServerApp.token=${JUPYTER_TOKEN:-jovykit} --ServerApp.password=''"]

FROM minimal AS base

LABEL org.opencontainers.image.description="JovyKit base Jupyter image for everyday data science, classical machine learning, statistics, and local data access."

WORKDIR /tmp/requirements
COPY requirements-base.txt ./

USER root
RUN --mount=type=cache,target=/root/.cache/uv \
    cat requirements-base.txt >> /usr/local/share/jovykit/base-requirements.txt && \
    uv pip install --python "${VIRTUAL_ENV}/bin/python" -r requirements-base.txt && \
    chown -R "${NB_UID}:${NB_GID}" "${VIRTUAL_ENV}" "/home/${NB_USER}"

USER ${NB_UID}
WORKDIR "${HOME}"

FROM base AS extended

LABEL org.opencontainers.image.description="JovyKit extended Jupyter image for advanced machine learning, NLP, time series, distributed compute, and API work."

WORKDIR /tmp/requirements
COPY requirements-extended.txt ./

USER root
RUN --mount=type=cache,target=/root/.cache/uv \
    cat requirements-extended.txt >> /usr/local/share/jovykit/base-requirements.txt && \
    uv pip install --python "${VIRTUAL_ENV}/bin/python" -r requirements-extended.txt && \
    chown -R "${NB_UID}:${NB_GID}" "${VIRTUAL_ENV}" "/home/${NB_USER}"

USER ${NB_UID}
WORKDIR "${HOME}"

FROM extended AS full

LABEL org.opencontainers.image.description="JovyKit full Jupyter image with heavier AI, graph, geospatial, big-data, database, and research tooling."

WORKDIR /tmp/requirements
COPY requirements-full.txt ./

USER root
RUN --mount=type=cache,target=/root/.cache/uv \
    apt-get update -o Acquire::Retries=3 && \
    apt-get install -y --no-install-recommends \
        build-essential && \
    cat requirements-full.txt >> /usr/local/share/jovykit/base-requirements.txt && \
    uv pip install --python "${VIRTUAL_ENV}/bin/python" -r requirements-full.txt && \
    apt-get purge -y --auto-remove \
        build-essential && \
    rm -rf /var/lib/apt/lists/* && \
    chown -R "${NB_UID}:${NB_GID}" "${VIRTUAL_ENV}" "/home/${NB_USER}"

USER ${NB_UID}
WORKDIR "${HOME}"
