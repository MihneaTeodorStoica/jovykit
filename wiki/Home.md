# JovyKit

Disposable JupyterLab environments that feel like Python virtualenvs.

JovyKit creates a project-local JupyterLab container project using normal
Docker Compose files. There is no hidden JovyKit config file: edit
`compose.yaml`, `Dockerfile`, or `requirements.txt` directly.

## Install

JovyKit requires Docker Engine and the Docker Compose plugin.
On macOS and Windows, install Docker Desktop first.
On supported Linux distros, JovyKit can print or run the Docker install plan.

```bash
pip install jovykit
# or
uv tool install jovykit

jovy install-docker --dry-run
jovy doctor
```

Run `jovy install-docker --yes` only after reading the dry run output.

## Quick Start

```bash
pip install jovykit

jovy init
jovy up -d
jovy open
```

![JovyKit demo](https://raw.githubusercontent.com/MihneaTeodorStoica/jovykit/main/site/assets/jovykit-demo.gif)

Use a pinned Python image or GPU mode when you need it:

```bash
jovy init --python 3.13
jovy init --gpu all --python 3.13
```

## Why?

Machine learning environments are annoying.

- Conda environments drift.
- Docker Compose is repetitive.
- Jupyter setup takes boilerplate.
- GPU configuration is fragile.
- Reproducing environments across machines is painful.

JovyKit makes Dockerized Jupyter environments feel lightweight and disposable.

## What You Get

- Persistent notebooks and Jupyter settings.
- Disposable container state.
- Readable generated Docker Compose files.
- Python-tagged image levels from `minimal` to `full`.
- Optional GPU support with `jovy init --gpu all`.
- A Compose escape hatch with `jovy compose ...`.

## Project Files

`jovy init` creates:

```text
compose.yaml
Dockerfile
requirements.txt
work/
.jupyter/
```

- `compose.yaml` owns runtime settings.
- `Dockerfile` builds the project overlay image.
- `requirements.txt` owns project Python packages.
- `work/` is mounted into the notebook.
- `.jupyter/` persists local Jupyter config.

Python version comes from the selected image tag, for example
`ghcr.io/mihneateodorstoica/jovykit:base-python-3.12`.

## Commands

These behave like Docker Compose:

```bash
jovy up -d
jovy down
jovy start
jovy stop
jovy config
jovy logs
```

These are JovyKit conveniences:

```bash
jovy add PACKAGE
jovy remove PACKAGE
jovy open
jovy shell
jovy doctor
```

## Images

Image levels:

- `minimal`: JupyterLab, add-ons, Nitro CLI, uv, and the runtime needed to start fast.
- `base`: everyday data science, statistics, and classical ML without extra apt tools.
- `extended`: lighter advanced stats, model inspection, APIs, visualization, spreadsheets, web scraping, and database clients.
- `full`: the huge batteries-included stack for ML, AI, cloud, distributed, apps, graph, geospatial, and research tooling.

Published tags use Python versions:

```text
ghcr.io/mihneateodorstoica/jovykit:base-python-3.12
```

`minimal` and `base` publish Python 3.9 through 3.14 tags.
`extended` and `full` publish Python 3.11 through 3.13 tags.
`latest` points at `base-python-3.11`. Scheduled images also get level-specific tags such as `base-nightly-python-3.11`, `base-weekly-python-3.11`, and `base-monthly-python-3.11`.

## GPU

`jovy init` enables GPU only when one is detected.

Explicit modes:

```bash
jovy init --gpu all
jovy init --gpu none
```

No GPU means no Compose `gpus` field.

See [CLI](CLI) and [Images](Images).
