# JovyKit

JovyKit runs a project-local JupyterLab environment with Docker Compose behind
the scenes.

The mental model is close to a Python virtual environment:

```text
.jovy is to JovyKit what .venv is to Python.
```

Each project gets a `jovy.toml` manifest, a generated `.jovy/` environment
directory, a `jovy.lock` lockfile, and a `work/` directory mounted into the
notebook container.

## Quick Start

Install JovyKit from a local checkout:

```bash
python -m pip install -e .
```

Create an environment:

```bash
jovy init .jovy --image base --gpus auto
```

Add project packages:

```bash
jovy add pandas scikit-learn plotly
```

Start JupyterLab:

```bash
jovy up
```

Open it:

```bash
jovy open
```

Or use the dashboard:

```bash
jovy
```

## The First Run

A good first run should feel like this:

1. `jovy init` creates the local files and tells you the next useful command.
2. `jovy add` updates `jovy.toml` and refreshes `jovy.lock`.
3. `jovy up` locks, builds when needed, starts Docker Compose, and prints the
   Jupyter URL.
4. `jovy open` opens the current Jupyter URL.
5. `jovy` opens the dashboard for status, logs, and queued commands.

The default Jupyter URL is:

```text
http://127.0.0.1:8888/lab?token=jovykit
```

JovyKit also exposes SSH on `127.0.0.1:22` by default.

## System Requirements

- Python 3.11 or newer.
- Docker Engine.
- Docker Compose plugin support.
- 2 CPU cores and 4 GiB RAM for `minimal` or `base`.
- 8 GiB RAM or more for `extended` or `full`.
- Disk space for the compressed image, unpacked layers, Docker cache, and the
  project overlay image.

Published `linux/amd64` `latest` image sizes checked on 2026-05-15:

| Image | Compressed pull size | Direct packages | Cumulative packages |
| --- | ---: | ---: | ---: |
| `minimal` | 659 MiB | 17 | 17 |
| `base` | 927 MiB | 36 | 53 |
| `extended` | 4.1 GiB | 44 | 97 |
| `full` | 5.8 GiB | 57 | 154 |

Use `base` first unless the project already needs the larger stack.
Published tag sizes can drift after rebuilds.

## Recommended Workflow

```bash
jovy init .jovy --image base --gpus auto
jovy add pandas scikit-learn plotly
jovy up
jovy open
```

Use the dashboard for interactive local work:

```bash
jovy
```

Use scriptable commands in terminals, shells, and automation:

```bash
jovy status
jovy add seaborn
jovy install
jovy up
jovy logs --tail 100
jovy shell
jovy down
```

## What Gets Created

After `jovy init` and the first lock/build cycle, the project contains:

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

Keep `jovy.toml` and `jovy.lock` in version control when you want the
environment definition to travel with the project.

Keep `.jovy/` out of version control.
It contains generated files, local build state, logs, and machine-local home
data.

`.jovy/home/` is mounted as `/home/jovyan` in the container.
It preserves `.ssh`, Jupyter config, shell history, and dotfiles across normal
`clean` and `destroy` runs.
Use `jovy destroy --purge` only when you want to delete that home data.

## Pick An Image Level

Use `--image` with a friendly level:

- `minimal`: Jupyter runtime plus the core scientific Python stack.
- `base`: everyday data science, classical machine learning, statistics, and
  local data access.
- `extended`: advanced ML, NLP, time series, distributed compute, and API
  tooling.
- `full`: heavier frameworks and specialized research tooling.

You can also pass a full image reference:

```bash
jovy init .jovy --image ghcr.io/example/custom-notebook:latest
```

## Dashboard

Run:

```bash
jovy
```

Enter commands without the `jovy` prefix:

```text
status
add numpy
install
up
open
down
```

The dashboard queues commands while another command is running.
It shows status, URL, recent logs, and progress for long work.

Dashboard-local helpers:

- `help`
- `clear`
- `open`
- `refresh`
- `quit`

Host shell escape:

```text
!pwd
!git status
```

See [CLI](CLI) for the full command guide and [Images](Images) for image
contents and build notes.
