<p align="center">
  <img src="site/assets/jovykit-logo-transparent.png" alt="JovyKit logo" width="140">
</p>

<h1 align="center">JovyKit</h1>

<p align="center">
  <a href="https://github.com/MihneaTeodorStoica/jovykit/actions/workflows/ci-release.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/MihneaTeodorStoica/jovykit/ci-release.yml?branch=main&label=ci"></a>
  <a href="pyproject.toml"><img alt="Version" src="https://img.shields.io/badge/version-5.0.1-ff5a00"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-0a9e9a">
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-2f3133"></a>
  <a href="https://mihneateodorstoica.github.io/jovykit/"><img alt="Website" src="https://img.shields.io/badge/site-live-ff5a00"></a>
</p>

Project-local JupyterLab containers with a venv-like CLI, layered notebook
images, uv-locked dependencies, and readable Docker Compose output.

```text
.jovy is to JovyKit what .venv is to Python.
```

[Website](https://mihneateodorstoica.github.io/jovykit/) ·
[Wiki](https://github.com/MihneaTeodorStoica/jovykit/wiki) ·
[Issues](https://github.com/MihneaTeodorStoica/jovykit/issues) ·
[GHCR Images](https://github.com/MihneaTeodorStoica/jovykit/pkgs/container/jovykit-base)

## Why JovyKit

JovyKit is for notebook-heavy data science and research projects that should be
easy to start, reproducible later, and still inspectable when something needs
debugging.

- Create a project-local `.jovy/` environment from one command.
- Track direct project packages in `jovy.toml`.
- Compile a deterministic `.jovy/jovy.lock` with uv.
- Build a generated overlay image instead of mutating container state.
- Run JupyterLab through Docker Compose without making Compose the user
  interface.
- Choose notebook image layers from `minimal`, `base`, `extended`, and `full`.
- Use a terminal dashboard for interactive project operations.

## Install

### Requirements

- Docker Engine and Docker Compose support
- Python 3.11+

### Local install

Install from a local checkout:

```bash
python -m pip install -e .
```

Verify the CLI is available:

```bash
python -m pip install -e .
jovy --version
```

## Quick Start

These commands are enough for your first environment:

```bash
jovy init .jovy --image base --gpus auto
jovy add pandas scikit-learn plotly
jovy install
jovy run
```

JovyKit prints the local JupyterLab URL. By default the token is `jovykit`.

## Common workflows

Use these command groups when moving day-to-day:

### Initialize + dependencies

```bash
jovy init .jovy --image base --gpus auto --port 8888
jovy add pandas scikit-learn
jovy remove plotly
jovy install
```

`jovy add` and `jovy remove` only update `jovy.toml`. `jovy install` is what
applies the manifest change to the generated overlay image.

### Start, stop, and iterate

```bash
jovy run       # foreground, logs streamed
jovy up        # detached/background
jovy down      # stop detached environment
jovy restart   # rebuild if needed and restart
jovy status    # quick health check
```

`jovy start` and `jovy stop` are aliases for `jovy up` and `jovy down`.

### Work inside and clean up

```bash
jovy logs --tail 100 --since 10m --timestamps
jovy shell --command "python --version"
jovy exec python --version
jovy clean              # remove generated state
jovy destroy --keep-image
```

When working outside the project directory, most commands accept `--env PATH` to
target a specific environment directory.

## What JovyKit creates

```text
jovy.toml
work/
.jovy/
  jovy.lock
  Containerfile
  compose.yaml
  state.json
```

`jovy.toml` is the project manifest. `.jovy/` contains generated local
environment files and should stay out of version control.

## Dashboard mode

Run `jovy` with no subcommand to open the terminal dashboard:

```bash
jovy
```

The dashboard is great for local, interactive operations. It supports command
entry, status refresh, log snapshots, and host shell escape (`!pwd`) commands.
`jovy run` and `jovy logs` are intentionally unavailable in the dashboard so
you can keep long-running sessions predictable.

## Image Layers

Published images use this pattern:

```text
ghcr.io/mihneateodorstoica/jovykit-TYPE:latest
ghcr.io/mihneateodorstoica/jovykit-TYPE:nightly
ghcr.io/mihneateodorstoica/jovykit-TYPE:lts
```

`TYPE` is one of:

- `minimal`: Jupyter runtime plus the core scientific Python stack.
- `base`: everyday data science, classical machine learning, statistics, and
  local data access.
- `extended`: advanced ML, NLP, time series, distributed compute, and API
  tooling.
- `full`: heavier AI, graph, geospatial, big-data, and research tooling.

All image variants include `git`, OpenSSH client tools, `rsync`, and a prepared
`~/.ssh` directory for SSH-backed remotes and file sync.

Build a target locally:

```bash
docker build --target minimal -t jovykit-minimal ./image
docker build --target base -t jovykit-base ./image
docker build --target extended -t jovykit-extended ./image
docker build --target full -t jovykit-full ./image
```

## Configuration

`jovy.toml` can customize runtime environment variables, extra volumes, home and
work mounts, restart policy, Jupyter command/logging, Compose Watch behavior,
image build arguments, build target/platform, apt packages, and uv/pip install
options.

JovyKit mounts `.jovy/home/` as `/home/jovyan` by default. Normal `clean` and
`destroy` runs preserve that folder, so SSH config, Jupyter config, shell
history, and other dotfiles are not thrown away by routine lifecycle commands.
Use `jovy destroy --purge` when you intentionally want to delete the persisted
home data.

Use the arrow-key editor:

```bash
jovy config
```

or open the dashboard and run:

```text
config
```

Textual config editor keys:

- `up` / `down` move between fields
- `left` / `right` cycle boolean and choice values
- `enter` edits or confirms a field
- `w` save in place and keep the editor open
- `q` / `escape` cancel (with discard confirmation when unsaved)

## Testing and contribution checks

Stable check commands:

```bash
ruff check .
black --check .
mypy jovykit tests main.py
pytest --cov=jovykit --cov-report=term-missing --cov-fail-under=90
```

Docker-oriented checks are intentionally opt-in:

```bash
pytest -m docker --run-docker
```

## Repository layout

```text
jovykit/              Python CLI package
image/                Dockerfile and layered image dependency manifests
site/                 GitHub Pages promotional website
wiki/                 GitHub Wiki page source
.github/workflows/    CI, security, website, wiki, and image automation
```

## Documentation

The website promotes the project and lives in `site/`. Operational
documentation lives in the
[GitHub Wiki](https://github.com/MihneaTeodorStoica/jovykit/wiki), with source
pages in `wiki/`.

## Troubleshooting

- If `jovy` says "not a JovyKit project", run `jovy init` in the project root
  or pass `--env` to point at an existing `.jovy` path.
- If Jupyter URL does not open, verify Docker is running and `jovy status` shows
  `running: true`.
- If dependency changes do not take effect, rerun `jovy install` after editing
  `jovy.toml`.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the
development workflow and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community
expectations.

## License

JovyKit is licensed under the MIT License. See [LICENSE](LICENSE).
