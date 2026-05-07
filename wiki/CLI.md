# CLI

The `jovy` CLI manages one project-local Jupyter environment at a time.

Most commands operate by walking up from the current directory and finding the
nearest `jovy.toml`. Use `--env PATH` when targeting a specific project root or
`.jovy` path.

```bash
jovy            # open the dashboard
jovy status     # print project status
```

## Global pattern

Most subcommands accept `--env`:

```bash
jovy --env /path/to/project status
jovy --env .jovy logs --tail 100
```

## init

Create a new environment.

```bash
jovy init .jovy
jovy init .jovy --image base --gpus auto --port 8888
jovy init .jovy --token dev-token --log-level INFO
```

Common options:

- `--image`: `minimal`, `base`, `extended`, `full`, or a full image reference.
- `--gpus`: `auto`, `none`, or `all`.
- `--port`: local port mapped to container port `8888`.
- SSH is exposed on `127.0.0.1:22` to container port `22` by default.
- `--token`: token shown in the Jupyter URL (default `jovykit`).
- `--log-level`: Jupyter server log level.
- `--name`: project name to persist in `jovy.toml`.
- `--image-name`: overlay image repository name.
- `--tag`: overlay tag (default `local`).
- `--workdir`: mounted work directory (default `work`).
- `--force`: refresh an existing environment.

## add / remove

```bash
jovy add pandas scikit-learn plotly
jovy add -r requirements.txt
jovy add -r requirements.txt -r requirements-dev.txt
jovy remove plotly
```

`add` writes entries to `[python].packages` and `add -r` stores constraints under
`[python].constraints`. `add` and `remove` also refresh `jovy.lock` so the
project lockfile matches `jovy.toml`.

- `add` and `remove` update `jovy.toml` and `jovy.lock`.
- `jovy install` or `jovy run/up` apply those changes to the generated overlay.

## install and build

```bash
jovy install
jovy install --upgrade
jovy install --no-build
jovy build
jovy build --no-cache --pull
jovy build -v
```

`install` does three things:

- regenerate `.jovy/compose.yaml` and `.jovy/Containerfile`
- update `jovy.lock` through uv
- build the project overlay image when inputs are stale

Use `--upgrade` to refresh locked package versions.

Use `--no-build` when you only need local file refresh.

## run, up, start, down, stop, restart

```bash
jovy run
jovy run --watch
jovy run --no-watch
jovy up
jovy start      # alias for up
jovy down
jovy stop       # alias for down
jovy down --timeout 10
jovy restart
```

- `run` starts Jupyter in the foreground and streams logs.
- `up` (`start`) starts in the background.
- `down` (`stop`) stops the environment without deleting generated files,
  images, lockfiles, work files, or home data.
- `restart` restarts the background environment.

`start` is an alias for `up`, and `stop` is an alias for `down`.

## status and logs

```bash
jovy status
jovy status --json
jovy logs
jovy logs --tail 100
jovy logs --since 10m --timestamps
jovy logs --no-follow
```

`status --json` is convenient for scripts and contains image reference, URL,
home mount, work mount, package count, build state, and environment path.

## shell and exec

```bash
jovy shell
jovy shell --command "python --version"
jovy exec python --version
jovy exec pip list
```

`shell` opens an interactive shell inside the running container by default.
`exec` requires a command and runs directly in the container.

## config

```bash
jovy config
```

The interactive config editor manages common runtime options, including:

- images and ports
- GPU mode
- Jupyter arguments
- restart policy
- env vars and extra volumes
- packages and install tooling options

When editing `jovy.toml` by hand, run `jovy install` before restarting an
environment.

## clean and destroy

```bash
jovy clean
jovy destroy
jovy destroy --keep-image
jovy destroy --purge
jovy destroy --yes --purge
```

- `clean` removes generated local build state and keeps `jovy.toml`,
  `jovy.lock`, the work directory, and `.jovy/home/`.
- `destroy` removes runtime resources and the overlay image by default.
- `destroy` preserves home data at `.jovy/home/`.
- `destroy --keep-image` preserves the overlay image.
- `destroy --purge` also deletes `.jovy/home/` and asks for confirmation.
- `destroy --yes --purge` is the non-interactive purge path for automation.
- `destroy --remove-dir` is deprecated. It is skipped unless `--purge` is also
  passed so home data is not removed accidentally.

## Dashboard commands

Run `jovy` with no subcommand for the dashboard. Enter subcommands without the
`jovy` prefix:

```text
status
up
down
add numpy
install
config
```

Run host shell commands with `!`:

```text
!pwd
!git status
```

Dashboard-local helper commands:

- `help`, `clear`, `open`, `refresh`, `quit`, `exit`

Blocked commands:

- `run`: use `up` in-dashboard, or run `jovy run` in your terminal.
- `logs`: use `jovy logs` from your terminal.
- `destroy`: run `jovy destroy` from your shell so the confirmation prompt is
  visible.
- `sync`: no dedicated sync command exists; use `install` instead.

## Error handling

JovyKit wraps expected user-facing failures in clean messages and exits with a
non-zero code. Common issues include:

- running outside a JovyKit project
- invalid `jovy.toml`
- using `jovy init` in a non-empty directory that is not already managed
