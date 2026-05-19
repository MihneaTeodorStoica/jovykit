# JovyKit

JovyKit creates a project-local JupyterLab container project using normal
Docker Compose files.

## Quick Start

```bash
python3 -m pip install -e .
jovy init --image-level base --python 3.13
jovy add pandas scikit-learn plotly
jovy up -d
jovy open
```

## Files

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
`ghcr.io/mihneateodorstoica/jovykit-base:python-3.13`.

## Commands

These behave like Docker Compose:

```bash
jovy up
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
ghcr.io/mihneateodorstoica/jovykit-base:python-3.13
```

`minimal` and `base` publish `python-3.9` through `python-3.14`.
`extended` and `full` publish `python-3.11` through `python-3.13`.
Scheduled images also get `nightly-python-3.x`, `weekly-python-3.x`, and `monthly-python-3.x` tags.

## GPU

`jovy init` enables GPU only when one is detected.

Explicit modes:

```bash
jovy init --gpu all
jovy init --gpu none
```

No GPU means no Compose `gpus` field.

See [CLI](CLI) and [Images](Images).
