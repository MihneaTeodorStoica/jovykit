# Images

JovyKit publishes Python-tagged images to GitHub Container Registry.

## Published References

```text
ghcr.io/mihneateodorstoica/jovykit-minimal:python-3.13
ghcr.io/mihneateodorstoica/jovykit-base:python-3.13
ghcr.io/mihneateodorstoica/jovykit-extended:python-3.13
ghcr.io/mihneateodorstoica/jovykit-full:python-3.13
```

`minimal` and `base` publish `python-3.9` through `python-3.14`.
`extended` and `full` publish `python-3.11` through `python-3.13`.
Scheduled images also get `nightly-python-3.x`, `weekly-python-3.x`, and `monthly-python-3.x` tags.

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
```

Output tags look like:

```text
ghcr.io/mihneateodorstoica/jovykit-base:python-3.13
```

## Project Overlay

`jovy init` creates a small project overlay:

```text
Dockerfile
requirements.txt
```

The generated Dockerfile starts from the selected image:

```dockerfile
ARG JOVY_BASE_IMAGE=ghcr.io/mihneateodorstoica/jovykit-base:python-3.13
FROM ${JOVY_BASE_IMAGE}
```

Project packages are installed from `requirements.txt` with uv.
No conda environment file is generated.
