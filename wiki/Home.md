# JovyKit

JovyKit is a small CLI for running a JupyterLab environment beside a project,
with Docker Compose doing the container work behind the scenes.

The intended mental model is close to a Python virtual environment:

```text
.jovy is to JovyKit what .venv is to Python.
```

Each project gets a `jovy.toml` manifest, a generated `.jovy/` environment
directory, and a `work/` directory that is mounted into the notebook container.
Project packages are recorded in TOML, locked with uv, and installed into a
local overlay image built from one of the published JovyKit base images.

## Quick start

Install JovyKit from a local checkout:

```bash
python -m pip install -e .
```

Create an environment in a project:

```bash
jovy init .jovy --image base --gpus auto
```

Add the packages this project needs:

```bash
jovy add pandas scikit-learn plotly
```

Build the overlay image and start JupyterLab:

```bash
jovy run
```

JovyKit prints the local Jupyter URL. By default it uses port `8888` and token
`jovykit`, so the browser URL is:

```text
http://127.0.0.1:8888/lab?token=jovykit
```

## What gets created

After `jovy init`, the project contains:

```text
jovy.toml
work/
.jovy/
  Containerfile
  compose.yaml
  state.json
```

After the first install or run, `.jovy/jovy.lock` is added.

Keep `jovy.toml` in version control when you want the environment definition to
travel with the project. Keep `.jovy/` out of version control; it contains
generated files, local build state, logs, and lock/build artifacts for this
machine.

## Pick an image level

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

## Daily workflow

Use the dashboard when you want a project console:

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

See [CLI](CLI) for the full command guide and [Images](Images) for image
contents and build notes.
