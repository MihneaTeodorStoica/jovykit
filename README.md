<p align="center">
  <img src="site/assets/jovykit-logo-transparent.png" alt="JovyKit logo" width="140">
</p>

<h1 align="center">JovyKit</h1>

<p align="center">
  <a href="https://github.com/MihneaTeodorStoica/jovykit/actions/workflows/ci-release.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/MihneaTeodorStoica/jovykit/ci-release.yml?branch=main&label=ci"></a>
  <a href="pyproject.toml"><img alt="Version" src="https://img.shields.io/badge/version-7.0.0-ff5a00"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-0a9e9a">
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-2f3133"></a>
  <a href="https://mihneateodorstoica.github.io/jovykit/"><img alt="Website" src="https://img.shields.io/badge/site-live-ff5a00"></a>
</p>

Project-local JupyterLab containers with a venv-like CLI, layered notebook
images, uv-locked dependencies, and a terminal dashboard that keeps the local
workflow visible.

```text
.jovy is to JovyKit what .venv is to Python.
```

[Website](https://mihneateodorstoica.github.io/jovykit/) .
[Wiki](https://github.com/MihneaTeodorStoica/jovykit/wiki) .
[Issues](https://github.com/MihneaTeodorStoica/jovykit/issues) .
[GHCR Images](https://github.com/MihneaTeodorStoica/jovykit/pkgs/container/jovykit-base)

## Why JovyKit

JovyKit is for notebook-heavy data science and research projects that should be
easy to start, easy to repeat, and still clear when something needs debugging.

- Create a project-local `.jovy/` environment from one command.
- Track project packages in `jovy.toml`.
- Compile a deterministic `jovy.lock` with uv.
- Build a generated overlay image instead of mutating container state.
- Start JupyterLab through Docker Compose without making Compose the interface.
- Choose image layers from `minimal`, `base`, `extended`, and `full`.
- Use the dashboard for day-to-day work, status, logs, and queued commands.

## Requirements

- Python 3.11 or newer.
- Docker Engine.
- Docker Compose plugin support.
- 2 CPU cores and 4 GiB RAM for `minimal` or `base`.
- 8 GiB RAM or more for `extended` or `full`.
- Enough disk for the base image, unpacked layers, Docker cache, and the project
  overlay image.

Published `linux/amd64` `latest` image sizes checked on 2026-05-15:

| Image | Compressed pull size | Layers | Direct packages | Cumulative packages |
| --- | ---: | ---: | ---: | ---: |
| `minimal` | 659 MiB | 37 | 17 | 17 |
| `base` | 927 MiB | 41 | 36 | 53 |
| `extended` | 4.1 GiB | 45 | 44 | 97 |
| `full` | 5.8 GiB | 49 | 57 | 154 |

Start with `base` unless the project already needs the larger toolchains.
Image sizes can drift when published tags rebuild.

GPU support is optional.
`--gpus auto` uses a GPU only when Docker exposes one.

## Install

Install from a local checkout:

```bash
python -m pip install -e .
jovy --version
```

## Quick Start

Create the project environment:

```bash
jovy init .jovy --image base --gpus auto
```

Add packages:

```bash
jovy add pandas scikit-learn plotly
```

Start JupyterLab:

```bash
jovy up
```

Open the browser:

```bash
jovy open
```

Or use the dashboard:

```bash
jovy
```

The dashboard queues commands while another command is running.
Build and install steps show progress instead of a silent wait.

## Common Workflows

### Initialize And Add Packages

```bash
jovy init .jovy --image base --gpus auto --port 8888
jovy add pandas scikit-learn
jovy remove plotly
jovy install
```

`jovy add` and `jovy remove` update `jovy.toml` and refresh `jovy.lock`.
`jovy install` applies the lock to the generated overlay image.

### Start, Stop, And Iterate

```bash
jovy up        # detached/background
jovy open      # open the current Jupyter URL
jovy status    # quick health check
jovy restart   # rebuild if needed and restart
jovy down      # stop detached environment
```

Use foreground logs when you want a terminal-owned session:

```bash
jovy run
```

`jovy start` and `jovy stop` are aliases for `jovy up` and `jovy down`.

### Work Inside And Clean Up

```bash
jovy logs --tail 100 --since 10m --timestamps
jovy shell --command "python --version"
jovy exec python --version
jovy clean
jovy destroy --keep-image
```

When working outside the project directory, most commands accept `--env PATH`.

## What JovyKit Creates

```text
jovy.toml
jovy.lock
work/
.jovy/
  Containerfile
  compose.yaml
  home/
  state.json
```

`jovy.toml` is the project manifest.
`jovy.lock` is the deterministic Python lockfile.
`.jovy/` contains generated local environment files and should stay out of
version control.

`.jovy/home/` is mounted as `/home/jovyan`.
Normal `clean` and `destroy` runs preserve it.
Use `jovy destroy --purge` only when you want to remove SSH config, Jupyter
config, shell history, and other home data.

## Dashboard

Run `jovy` with no subcommand:

```bash
jovy
```

The dashboard is for local, interactive project work:

- command bar at the bottom
- status and URL in view
- recent logs in view
- queued commands while builds or starts are running
- local helpers: `help`, `clear`, `open`, `refresh`, `quit`
- host shell escape: `!pwd`, `!git status`

Use command names without the `jovy` prefix:

```text
add seaborn
install
up
open
status
down
```

`run`, `logs`, and `destroy` stay outside the dashboard.
That keeps foreground streams and destructive prompts in a normal terminal.

## Image Layers

Published images use this pattern:

```text
ghcr.io/mihneateodorstoica/jovykit-TYPE:latest
ghcr.io/mihneateodorstoica/jovykit-TYPE:nightly
ghcr.io/mihneateodorstoica/jovykit-TYPE:weekly
ghcr.io/mihneateodorstoica/jovykit-TYPE:monthly
```

`TYPE` is one of:

- `minimal`: Jupyter runtime plus the core scientific Python stack.
- `base`: everyday data science, classical machine learning, statistics, and
  local data access.
- `extended`: advanced ML, NLP, time series, distributed compute, and API
  tooling.
- `full`: heavier AI, graph, geospatial, big-data, and research tooling.

All image variants include `git`, OpenSSH client tools, `rsync`, `uv`, `uvx`,
`nvtop-nightly`, and a prepared `~/.ssh` directory.

Build the images locally from the repository root:

```bash
docker build -f image/minimal/Dockerfile -t jovykit-minimal ./image
docker build -f image/base/Dockerfile --build-arg BASE_IMAGE=jovykit-minimal -t jovykit-base ./image
docker build -f image/extended/Dockerfile --build-arg BASE_IMAGE=jovykit-base -t jovykit-extended ./image
docker build -f image/full/Dockerfile --build-arg BASE_IMAGE=jovykit-extended -t jovykit-full ./image
```

## Configuration

`jovy.toml` can customize runtime environment variables, extra volumes, home and
work mounts, restart policy, Jupyter command/logging, Compose Watch behavior,
image username/UID/GID, pull policy, labels, build arguments, build
target/platform, apt packages, and uv/pip install options.

Use the editor:

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
- `q` / `escape` cancel

## Testing And Contribution Checks

Stable check commands:

```bash
ruff check .
black --check .
mypy jovykit tests main.py
pytest --cov=jovykit --cov-report=term-missing --cov-fail-under=90
```

Docker-oriented checks are opt-in:

```bash
pytest -m docker --run-docker
```

## Repository Layout

```text
jovykit/              Python CLI package
image/                Dockerfile and layered image dependency manifests
site/                 GitHub Pages promotional website
wiki/                 GitHub Wiki page source
.github/workflows/    CI, security, website, wiki, and image automation
```

## Troubleshooting

- If `jovy` says "not a JovyKit project", run `jovy init` in the project root
  or pass `--env` to point at an existing `.jovy` path.
- If `jovy open` has no URL, start the environment with `jovy up`.
- If dependency changes do not appear in Jupyter, run `jovy install` or
  `jovy restart`.
- If a large image pull is slow, try `--image base` before `extended` or `full`.
- If a dashboard command is waiting, check the queue line before entering it
  again.

## Documentation

The website lives in `site/`.
Operational documentation lives in the
[GitHub Wiki](https://github.com/MihneaTeodorStoica/jovykit/wiki), with source
pages in `wiki/`.

## Contributing

Contributions are welcome.
See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community expectations.

## License

JovyKit is licensed under the MIT License.
See [LICENSE](LICENSE).
