# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.12
FROM ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-bookworm-slim AS minimal

LABEL org.opencontainers.image.description="JovyKit minimal Jupyter image with Python, uv, JupyterLab add-ons, and Nitro CLI."

ARG PYTHON_VERSION
ARG NB_USER=jovyan
ARG NB_UID=1000
ARG NB_GID=100

ENV DEBIAN_FRONTEND=noninteractive \
    HOME=/home/${NB_USER} \
    JUPYTER_PORT=8888 \
    NB_GID=${NB_GID} \
    NB_UID=${NB_UID} \
    NB_USER=${NB_USER} \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SHELL=/bin/bash \
    UV_COMPILE_BYTECODE=0 \
    UV_HTTP_TIMEOUT=120 \
    UV_LINK_MODE=hardlink \
    VIRTUAL_ENV=/opt/jovy
ENV PATH="${VIRTUAL_ENV}/bin:${HOME}/.local/bin:${PATH}"

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

WORKDIR /tmp/requirements
COPY requirements-minimal.txt ./

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update -o Acquire::Retries=3 && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        tini && \
    rm -rf /usr/share/doc/* /usr/share/man/* /usr/share/info/* /usr/share/lintian/* /usr/share/locale/* && \
    groupadd --gid "${NB_GID}" "${NB_USER}" || true && \
    useradd --uid "${NB_UID}" --gid "${NB_GID}" --create-home --shell /bin/bash "${NB_USER}" || true && \
    install -d -m 0755 -o "${NB_UID}" -g "${NB_GID}" /home/${NB_USER}/work && \
    install -d -m 0700 -o "${NB_UID}" -g "${NB_GID}" /home/${NB_USER}/.ssh

RUN install -d /usr/local/share/jovykit && \
    cp requirements-minimal.txt /usr/local/share/jovykit/base-requirements.txt

RUN cat > /usr/local/bin/jovy-prune-image <<'SH' && \
    chmod +x /usr/local/bin/jovy-prune-image
#!/usr/bin/env sh
set -eu
prefix="${1:-/opt/jovy}"
home_dir="${2:-/home/jovyan}"
rm -rf /root/.cache/pip "$home_dir/.cache/pip" "$home_dir/.cache/uv"
find "$prefix" -type d \( -name __pycache__ -o -name tests -o -name test \) -prune -exec rm -rf {} +
find "$prefix" -type f \( -name "*.pyc" -o -name "*.pyo" -o -name "*.a" -o -name "*.la" \) -delete
find "$prefix" -type d -path "*/share/jupyter/lab/staging" -prune -exec rm -rf {} +
SH

RUN cat > /usr/local/bin/jovy-remove-panel <<'SH' && \
    chmod +x /usr/local/bin/jovy-remove-panel
#!/usr/bin/env sh
set -eu
prefix="${1:-/opt/jovy}"
python_bin="${prefix}/bin/python"

if "$python_bin" -c "import importlib.metadata as m; m.version('panel')" >/dev/null 2>&1; then
    uv pip uninstall --python "$python_bin" panel
fi
SH

RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv venv --clear --python /usr/local/bin/python "${VIRTUAL_ENV}" && \
    if [[ "${PYTHON_VERSION}" == 3.9* ]]; then \
        uv pip install --python "${VIRTUAL_ENV}/bin/python" pip==26.0.1; \
    else \
        uv pip install --python "${VIRTUAL_ENV}/bin/python" pip==26.1.1; \
    fi && \
    uv pip install --python "${VIRTUAL_ENV}/bin/python" -r requirements-minimal.txt && \
    printf '#!/usr/bin/env sh\nexec "%s" -m pip "$@"\n' "${VIRTUAL_ENV}/bin/python" > "${VIRTUAL_ENV}/bin/pip" && \
    chmod +x "${VIRTUAL_ENV}/bin/pip" && \
    ln -sf pip "${VIRTUAL_ENV}/bin/pip3" && \
    ln -sf pip "${VIRTUAL_ENV}/bin/pip${PYTHON_VERSION}" && \
    ln -sf "${VIRTUAL_ENV}/bin/pip" /usr/local/bin/pip && \
    ln -sf "${VIRTUAL_ENV}/bin/pip3" /usr/local/bin/pip3 && \
    ln -sf "${VIRTUAL_ENV}/bin/pip${PYTHON_VERSION}" "/usr/local/bin/pip${PYTHON_VERSION}" && \
    ln -sf "${VIRTUAL_ENV}/bin/jupyter" /usr/local/bin/jupyter && \
    jovy-prune-image "${VIRTUAL_ENV}" "/home/${NB_USER}" && \
    chown -R "${NB_UID}:${NB_GID}" "${VIRTUAL_ENV}" "/home/${NB_USER}"

RUN cat >> "${HOME}/.bashrc" <<'SH' && \
    chown "${NB_UID}:${NB_GID}" "${HOME}/.bashrc"
# >>> vscode python
# version: 0.1.1
if [ -z "$VSCODE_PYTHON_AUTOACTIVATE_GUARD" ]; then
    export VSCODE_PYTHON_AUTOACTIVATE_GUARD=1
    if [ -n "$VSCODE_PYTHON_BASH_ACTIVATE" ] && [ "$TERM_PROGRAM" = "vscode" ]; then
        eval "$VSCODE_PYTHON_BASH_ACTIVATE" || true
    fi
fi
# <<< vscode python
SH

USER ${NB_UID}
WORKDIR "${HOME}"
EXPOSE 8888
ENTRYPOINT ["tini", "-g", "--"]
CMD ["sh", "-lc", "exec /opt/jovy/bin/jupyter lab --ip=0.0.0.0 --port=${JUPYTER_PORT} --no-browser --ServerApp.token=${JUPYTER_TOKEN:-jovykit} --ServerApp.password=''"]

FROM minimal AS base

LABEL org.opencontainers.image.description="JovyKit base Jupyter image for everyday data science, classical machine learning, and statistics."

WORKDIR /tmp/requirements
COPY requirements-base.txt ./

USER root
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    cat requirements-base.txt >> /usr/local/share/jovykit/base-requirements.txt && \
    uv pip install --python "${VIRTUAL_ENV}/bin/python" -r requirements-base.txt && \
    jovy-prune-image "${VIRTUAL_ENV}" "/home/${NB_USER}" && \
    chown -R "${NB_UID}:${NB_GID}" "${VIRTUAL_ENV}" "/home/${NB_USER}"

USER ${NB_UID}
WORKDIR "${HOME}"

FROM base AS extended

LABEL org.opencontainers.image.description="JovyKit extended Jupyter image for advanced statistics, model inspection, cloud files, experiment tracking, NLP, distributed data, APIs, visualization, and database clients."

WORKDIR /tmp/requirements
COPY requirements-extended.txt ./

USER root
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    cat requirements-extended.txt >> /usr/local/share/jovykit/base-requirements.txt && \
    uv pip install --python "${VIRTUAL_ENV}/bin/python" -r requirements-extended.txt && \
    jovy-remove-panel "${VIRTUAL_ENV}" && \
    jovy-prune-image "${VIRTUAL_ENV}" "/home/${NB_USER}" && \
    chown -R "${NB_UID}:${NB_GID}" "${VIRTUAL_ENV}" "/home/${NB_USER}"

USER ${NB_UID}
WORKDIR "${HOME}"

FROM extended AS full

LABEL org.opencontainers.image.description="JovyKit full Jupyter image with heavier ML, NLP, cloud files, distributed compute, AI, graph, geospatial, database, and research tooling."

WORKDIR /tmp/requirements
COPY requirements-full.txt ./

USER root
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    cat requirements-full.txt >> /usr/local/share/jovykit/base-requirements.txt && \
    uv pip install --python "${VIRTUAL_ENV}/bin/python" -r requirements-full.txt && \
    jovy-remove-panel "${VIRTUAL_ENV}" && \
    jovy-prune-image "${VIRTUAL_ENV}" "/home/${NB_USER}" && \
    chown -R "${NB_UID}:${NB_GID}" "${VIRTUAL_ENV}" "/home/${NB_USER}"

USER ${NB_UID}
WORKDIR "${HOME}"
