# CLI

The `jovy` CLI manages one project-local Jupyter container environment. Most
commands find the nearest `jovy.toml` by walking upward from the current
directory. Use `--env PATH` when you want to target a specific project root or
`.jovy` directory.

Run `jovy` without a subcommand to open the terminal dashboard. The dashboard
shows environment status, recent logs, and a `jovy>` prompt that accepts the
same command model as the regular CLI. Closing the dashboard does not stop a
running container.

## Initialize

```bash
jovy init .jovy
jovy init .jovy --image base --gpus auto --port 8888
jovy init .jovy --token dev-token --log-level INFO
```

`jovy init` writes a project-level `jovy.toml`, creates `.jovy/`, creates the
configured work directory, and renders the first `Containerfile` and
`compose.yaml`.

Common options:

- `--image`: `minimal`, `base`, `extended`, `full`, or a full image reference.
- `--gpus`: `auto`, `none`, or `all`.
- `--port`: local port mapped to container port `8888`.
- `--token`: Jupyter token. The default is `jovykit`.
- `--log-level`: Jupyter server log level.
- `--name`: project name written into `jovy.toml`.
- `--image-name`: overlay image repository name.
- `--tag`: overlay image tag. The default is `local`.
- `--workdir`: project path mounted into the container. The default is `work`.
- `--force`: refresh an existing JovyKit environment.

## Add and remove packages

```bash
jovy add pandas scikit-learn plotly
jovy add -r requirements.txt
jovy add -r requirements.txt -r requirements-dev.txt
jovy remove plotly
```

Packages are stored as direct specs in `[python].packages` inside `jovy.toml`.
JovyKit avoids duplicate direct entries. Requirements imports preserve
constraint files as `[python].constraints`.

Package changes mark the overlay image stale. Apply them with:

```bash
jovy install
```

or let `jovy run` / `jovy up` install before starting the container.

## Install and build

```bash
jovy install
jovy install --upgrade
jovy install --no-build
jovy build
jovy build --no-cache --pull
```

`jovy install` regenerates `.jovy/Containerfile` and `.jovy/compose.yaml`,
compiles `.jovy/jovy.lock` with uv, and builds the overlay image when build
inputs are stale.

Use `--upgrade` to refresh pinned package versions in the lockfile. Use
`--no-build` when you only want to regenerate files and the lockfile.

`jovy build` builds the overlay image without starting Jupyter.

## Start, stop, and restart

```bash
jovy run
jovy run --watch
jovy run --no-watch
jovy up
jovy up --no-build
jovy restart
jovy down
jovy down --timeout 10
```

`jovy run` starts Jupyter in the foreground and streams logs. By default it uses
Docker Compose watch while attached.

`jovy up` starts the environment in the background. Detached `up` and `restart`
also start a lightweight config watcher. When `jovy.toml` changes, the watcher
regenerates the generated files, rebuilds the overlay image if needed, and
recreates the service.

Use `jovy down` to stop the background environment and its watcher.

## Inspect a running environment

```bash
jovy status
jovy status --json
jovy logs --tail 100
jovy logs --since 10m --timestamps
jovy logs --no-follow
```

`status --json` is useful for scripts that need the environment directory,
image reference, port, Jupyter URL, or running state.

## Work inside the container

```bash
jovy shell
jovy shell -c "python --version"
jovy exec python --version
jovy exec pip list
```

`jovy shell` opens bash in the running container. `jovy exec` runs a command in
the same service without opening an interactive shell.

## Edit configuration

```bash
jovy config
```

The config editor opens a keyboard-driven terminal editor for common
`jovy.toml` settings, including image, port, GPU mode, restart policy, Jupyter
settings, packages, runtime environment variables, and extra volumes. Use
up/down to move, left/right to cycle choices, Enter to edit, `s` to save, `a`
to apply, and `q` to quit.

You can also edit `jovy.toml` directly. Build-affecting changes should be
followed by:

```bash
jovy install
```

or a fresh `jovy run` / `jovy up`.

## Clean up

```bash
jovy clean
jovy destroy
jovy destroy --keep-image
jovy destroy --remove-dir
```

`jovy clean` removes generated files and local build state while preserving the
project manifest and lockfile.

`jovy destroy` stops the environment, removes Docker Compose resources, and
removes the project overlay image. Use `--keep-image` to preserve the image.
Use `--remove-dir` when you also want to delete `.jovy/`.

## Dashboard commands

Inside the dashboard, enter commands without the `jovy` prefix:

```text
status
up
down
add numpy pandas
exec python --version
```

Prefix host shell commands with `!`:

```text
!pwd
!docker ps
```

Dashboard-local commands are `help`, `clear`, `open`, `refresh`, `quit`, and
`exit`.

## Errors

JovyKit catches expected user-facing failures and prints clean messages instead
of Python tracebacks. Common examples are running outside a JovyKit project,
passing an invalid `jovy.toml`, or trying to initialize a non-empty directory
that is not already a JovyKit environment.
