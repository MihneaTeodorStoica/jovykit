# Images

JovyKit publishes Python-tagged images to GitHub Container Registry.

## Published References

```text
ghcr.io/mihneateodorstoica/jovykit:minimal-python-3.13
ghcr.io/mihneateodorstoica/jovykit:base-python-3.12
ghcr.io/mihneateodorstoica/jovykit:extended-python-3.13
ghcr.io/mihneateodorstoica/jovykit:full-python-3.13
```

`minimal` and `base` publish Python 3.9 through 3.14 tags.
`extended` and `full` publish Python 3.11 through 3.13 tags.
`latest` points at `base-python-3.11`. Scheduled images also get level-specific tags such as `base-nightly-python-3.11`, `base-weekly-python-3.11`, and `base-monthly-python-3.11`.

## Levels

- `minimal`: JupyterLab, add-ons, Nitro CLI, uv, and the runtime needed to start fast.
- `base`: everyday data science, statistics, and classical ML without extra apt tools.
- `extended`: lighter advanced stats, model inspection, APIs, visualization, spreadsheets, web scraping, and database clients.
- `full`: the huge batteries-included stack for ML, AI, cloud, distributed, apps, graph, geospatial, big-data, and research tooling.

## Build Model

Images are built from one multi-stage Dockerfile:

```text
image/Dockerfile
```

Targets:

```text
minimal -> base -> extended -> full
```

Each image uses `ARG PYTHON_VERSION`.

## Build Locally

Build all targets for all default Python versions:

```bash
./build.sh
```

Build one target:

```bash
./build.sh --python-version 3.13 minimal
```

Build selected targets and versions:

```bash
./build.sh --python 3.13 --python 3.14 minimal base
./build.sh --python 3.11 --latest base
./build.sh --python 3.11 --channel nightly base
```

Output tags look like:

```text
ghcr.io/mihneateodorstoica/jovykit:base-python-3.12
```

## Project Overlay

`jovy init` creates a small project overlay:

```text
Dockerfile
requirements.txt
.devcontainer/devcontainer.json
```

The generated Dockerfile starts from the selected image:

```dockerfile
ARG JOVY_BASE_IMAGE=ghcr.io/mihneateodorstoica/jovykit:base-python-3.12
FROM ${JOVY_BASE_IMAGE}
```

Project packages are installed from `requirements.txt` with uv.
VS Code Dev Containers use `.devcontainer/devcontainer.json` to attach to the
generated Compose service.
No conda environment file is generated.
