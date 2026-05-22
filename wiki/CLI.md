# CLI

`jovy` manages one project-local JupyterLab service.

With no arguments:

- in an empty folder, `jovy` runs `jovy init`
- in an existing project, `jovy` prints help

## Usage

Install:

```bash
pip install jovykit
# or
uv tool install jovykit
```

Smallest first run:

```bash
jovy init
jovy up -d
jovy open
```

```text
jovy
jovy init [--image-level LEVEL] [--python VERSION] [--gpu MODE] [--port PORT] [--token TOKEN]
jovy add PACKAGE [PACKAGE...]
jovy remove PACKAGE [PACKAGE...]
jovy up [ARGS...]
jovy down [ARGS...]
jovy start [ARGS...]
jovy stop [ARGS...]
jovy restart [ARGS...]
jovy status
jovy config [ARGS...]
jovy logs [ARGS...]
jovy shell [COMMAND...]
jovy run COMMAND [ARGS...]
jovy build [ARGS...]
jovy watch [ARGS...]
jovy open
jovy token show
jovy token rotate
jovy doctor
jovy install-docker [--dry-run] [--yes] [--skip-hello-world]
jovy compose COMMAND [ARGS...]
```

## install-docker

Linux helper for Docker Engine and Compose plugin setup.
Dry run is default.

```bash
jovy install-docker --dry-run
jovy install-docker --yes
jovy install-docker --yes --skip-hello-world
```

Supported Linux distros: Ubuntu, Debian, Fedora, RHEL, and CentOS.
macOS and Windows users should install Docker Desktop manually.

## init

```bash
jovy init --image-level base --python 3.13 --gpu none --port 8888
```

Options:

- `--image-level`: `minimal`, `base`, `extended`, or `full`
- `--python`: image Python tag, from `3.9` through `3.14`
- `--gpu`: `none` or `all`
- `--port`: host Jupyter port
- `--token`: optional Jupyter token override (default random)
- `--force`: overwrite generated files

`jovy init` writes `compose.yaml`, `Dockerfile`, `requirements.txt`,
`.devcontainer/devcontainer.json`, `work/`, and `.jupyter/`.

## add / remove

```bash
jovy add pandas scikit-learn
jovy remove scikit-learn
```

These commands edit `requirements.txt`.

## Compose Commands

These forward to Docker Compose and accept Compose args:

```bash
jovy up -d
jovy down --remove-orphans
jovy start
jovy stop
jovy config
jovy logs -f --tail 100
jovy build --no-cache
jovy restart
```

## Project Commands

```bash
jovy status
jovy open
jovy shell
jovy shell python --version
jovy run python script.py
jovy token show
jovy token rotate
jovy doctor
jovy install-docker --dry-run
```

Use `jovy compose ...` for raw Docker Compose access.

## token

```bash
jovy token show
jovy token rotate
```

`jovy token show` prints the current local Jupyter URL and token.
`jovy token rotate` writes a new random token into `compose.yaml`.
