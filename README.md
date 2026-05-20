<p align="center">
  <img src="site/assets/jovykit-logo-transparent.png" alt="JovyKit logo" width="140">
</p>

<h1 align="center">JovyKit</h1>

<p align="center">
  <strong>Project-local JupyterLab environments, built and run through Docker Compose.</strong>
</p>

<p align="center">
  <a href="https://github.com/MihneaTeodorStoica/jovykit/actions/workflows/ci-release.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/MihneaTeodorStoica/jovykit/ci-release.yml?branch=main&label=ci"></a>
  <a href="pyproject.toml"><img alt="Version" src="https://img.shields.io/badge/version-8.1.1-ff5a00"></a>
  <img alt="CLI Python" src="https://img.shields.io/badge/cli-python%203.9%2B-2f3133">
  <img alt="Image Python" src="https://img.shields.io/badge/images-python%203.9--3.14-0a9e9a">
  <a href="https://github.com/MihneaTeodorStoica/jovykit/pkgs/container/jovykit"><img alt="GHCR" src="https://img.shields.io/badge/ghcr-python--tagged-151617"></a>
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-2f3133"></a>
</p>

## Model

`compose.yaml` is runtime.
`Dockerfile` is the project overlay.
`requirements.txt` is project Python packages.
Python comes from the selected image tag, for example `:base-python-3.13`.

- `jovy` initializes an empty directory, or prints help in an existing project.
- `jovy init` creates `compose.yaml`, `Dockerfile`, `requirements.txt`, `work/`, and `.jupyter/`.
- `jovy up`, `down`, `start`, `stop`, `restart`, `config`, `logs`, `build`, and `watch` pass through to Docker Compose.
- `jovy add` and `jovy remove` edit `requirements.txt`.
- `jovy status`, `shell`, `run`, `open`, and `doctor` add small Jupyter-focused conveniences.
- `jovy compose ...` is the Docker Compose escape hatch.

There is no JovyKit config file.
Edit `compose.yaml`, `Dockerfile`, or `requirements.txt` directly.

## Requirements

- Python 3.9 or newer on the host.
- Docker Engine.
- Docker Compose plugin support.
- Optional GPU runtime support for `gpus: all`.

## Install

```bash
python -m pip install -e .
jovy --version
```

## Quick Start

```bash
jovy init --image-level base --python 3.13 --port 8888
jovy add pandas scikit-learn
jovy up -d
jovy open
```

Common commands:

```bash
jovy build
jovy watch
jovy logs -f
jovy status
jovy shell
jovy down
jovy compose ps
```

## Images

Image levels map to published JovyKit images:

```text
ghcr.io/mihneateodorstoica/jovykit:minimal-python-3.13
ghcr.io/mihneateodorstoica/jovykit:base-python-3.13
ghcr.io/mihneateodorstoica/jovykit:extended-python-3.13
ghcr.io/mihneateodorstoica/jovykit:full-python-3.13
```

`minimal` and `base` publish Python 3.9 through 3.14 tags.
`extended` and `full` publish Python 3.11 through 3.13 tags.
`latest` points at `minimal-python-3.14`. Scheduled images also get level-specific tags such as `base-nightly-python-3.11`, `base-weekly-python-3.11`, and `base-monthly-python-3.11`.

`minimal`, `base`, and `extended` are curated cuts from the full stack.
`full` is intentionally huge and keeps heavyweight ML, AI, cloud, distributed,
and app runtimes in one batteries-included layer.

```bash
jovy init --image-level minimal --python 3.11
jovy init --image-level base --python 3.12
jovy init --image-level extended --python 3.13
jovy init --image-level full --python 3.13
```

The generated Compose file passes only `JOVY_BASE_IMAGE`.
It does not pass a Python version build argument.

Build published image targets from the single multi-stage Dockerfile:

```bash
./build.sh minimal
./build.sh --python-version 3.13 base
./build.sh --python 3.11 --python 3.12 --python 3.13 all
./build.sh --python 3.14 --latest minimal
./build.sh --python 3.11 --channel nightly base
```

With no args, `./build.sh` builds all supported image and Python tag pairs.

## Dependencies

Use `requirements.txt`.

```bash
jovy add pandas scikit-learn
jovy remove pandas
```

Compose Watch rebuilds when dependency files change:

```bash
jovy watch
```

## Persistent Files

Generated projects mount only the durable user paths:

```text
./work      -> /home/jovyan/work
./.jupyter  -> /home/jovyan/.jupyter
```

Project notebooks and Jupyter settings survive rebuilds and container removal.
Other container state is disposable.

## GPU

GPU support is explicit:

```bash
jovy init --gpu none
jovy init --gpu all
```

By default, `jovy init` uses `all` when a local GPU is detected.
`none` omits the Compose GPU field.
`all` writes Compose `gpus: all`.

## Repository Checks

```bash
ruff check .
black --check .
mypy jovykit tests main.py
pytest --cov=jovykit --cov-report=term-missing
```

Docker checks are opt-in:

```bash
pytest -m docker --run-docker
```

## Repository Layout

```text
jovykit/              Python CLI package
image/                Published image layers
site/                 GitHub Pages site
wiki/                 GitHub Wiki source
.github/workflows/    CI, release, docs, and image automation
```

## License

JovyKit is licensed under the MIT License.
See [LICENSE](LICENSE).
